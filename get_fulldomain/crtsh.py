# -*- coding: UTF-8 -*-
import psycopg2
import re
import sys
import tldextract
from datetime import datetime
from threading import Thread
from queue import Queue
from logger import logger 
import os

# db_name: lb, template0, certwatch, postgres, template1 (SELECT datname FROM pg_database)
# table_name: select * from pg_tables
# version: show server_version -> '9.5.15'



class crtsh_db():
    def __init__(self):
        self.dbname = "certwatch"
        self.user = "guest"
        self.host = "crt.sh"
        self.conn = psycopg2.connect("dbname={} user={} host={}".format(self.dbname,self.user,self.host))
        self.thread_num = 5
        self.queue = Queue()
        self.domain_set = set() 
        self.level_1 = set()

    def __del__(self):
        self.conn.close()

    def play_db(self, sql):
        conn = self.conn
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(sql)
        res = cursor.fetchall()
        return res

    def desc_table(self, table_name):
        conn = self.conn
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("SELECT a.attnum,a.attname AS field,t.typname AS type,a.attlen AS length,a.atttypmod AS lengthvar,a.attnotnull AS notnull\
                        FROM pg_class c,pg_attribute a,pg_type t\
                        WHERE c.relname = '{}' and a.attnum > 0 and a.attrelid = c.oid and a.atttypid = t.oid\
                        ORDER BY a.attnum;".format(table_name))
        res = cursor.fetchall()
        return res

    def select_table(self, column_name, table_name):
        conn = self.conn
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("SELECT {} FROM {}".format(column_name, table_name))
        res = cursor.fetchall()
        return res

    def lookup_domain(self, domain):
        try: #connecting to crt.sh postgres database to retrieve subdomains in case API fails
            unique_domains = set()
            domain = domain.replace('%25.', '')
            conn = self.conn
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute("SELECT ci.NAME_VALUE NAME_VALUE\
                            FROM certificate_identity ci WHERE ci.NAME_TYPE = 'dNSName'\
                            AND reverse(lower(ci.NAME_VALUE)) LIKE reverse(lower('%{}'));".format(domain))
            for result in cursor.fetchall():
                unique_domains.add(result[0])
                # self.lookup_domain(result[0])
            return sorted(unique_domains)
        except Exception as e:
            logger.info(e)
    
    def select_valid_cert(self, domain, time, commonName):
        conn = self.conn
        conn.autocommit = True
        cursor = conn.cursor()
        if commonName:
            line = "AND ci.NAME_TYPE = 'commonName'"
        else:
            line = ""
        cursor.execute("SELECT  c.ID CERT_ID,\
                                encode(x509_serialNumber(c.CERTIFICATE), 'hex') SERIAL_NUM,\
                                ca.NAME ISSUER_NAME,\
                                ci.NAME_VALUE CN,\
                                x509_notBefore(c.CERTIFICATE) NOT_BEFORE,\
                                x509_notAfter(c.CERTIFICATE) NOT_AFTER,\
                                x509_altnames(c.CERTIFICATE) SAN\
                        FROM ca, certificate_identity ci, certificate c\
                        WHERE ci.ISSUER_CA_ID = ca.ID\
                            AND lower(ci.NAME_VALUE) like lower('{}')\
                            {}\
                            AND ci.CERTIFICATE_ID = c.ID\
                            AND x509_notAfter(c.CERTIFICATE) > '{}'\
                        GROUP BY CERT_ID, ISSUER_NAME, CN\
                        ORDER BY NOT_BEFORE DESC;".format(domain, line, time))
        res = cursor.fetchall()
        return res

    def write_table_info(self, column_name, table_name):
        with open("file/crtshdb/"+column_name+"_"+table_name+".txt","w") as f:
            res = self.select_table(column_name, table_name)
            f.write(str(res))

    def dedup_cert(self, res):
        valid_cert = list()
        serial_num_set = set()
        for item in res:
            serial_num = item[1]
            if serial_num not in serial_num_set:
                serial_num_set.add(serial_num)
                valid_cert.append([item[:-1], set([item[-1]])])
            else:
                for cert in valid_cert:
                    if cert[0][1] == serial_num:
                        cert[1].add(item[-1])
        return valid_cert

    def write_valid_cert(self, domain, time, commonName):
        with open("file/valid_cert/valid_cert_"+domain+"_"+str(commonName)+".txt","w",encoding="utf-8") as f:
            res = self.dedup_cert(self.select_valid_cert(domain, time, commonName))
            for item in res:
                f.write(str(item)+'\n')

    def write_all_valid_cert(self, time):
        while not self.queue.empty():
            domain = self.queue.get()
            self.get_domain(domain, time)  
        with open("file/valid_cert/all_cert.txt", "w", encoding="utf-8") as f:
            f.write('\n'.join(self.domain_set))             

    def write_domain(self, domain):
        path_t = sys.path[0] + "/get_fulldomain/output/domain/crtsh/"+domain+".txt"
        # with open(sys.path + "/get_fulldomain/output/domain/crtsh/"+domain+".txt","w") as f:
        with open(path_t,"w") as f:
            res = self.lookup_domain(domain)
            for item in res:
                f.write(str(item)+'\n')
    
    def find_Level_1_domain(self, domain_list):
        Level_1 = set()
        for domain in domain_list:
            res = tldextract.extract(domain)
            d = "{}.{}".format(res.domain, res.suffix)
            Level_1.add(d)
        return Level_1
    
    def get_domain(self, domain, time):
        domain_set = set()
        entry_domain = list(self.find_Level_1_domain([domain]))[0]
        print("[+] Searching for certificate at domain %s" % entry_domain)
        certs = self.select_valid_cert(entry_domain, time, False)+self.select_valid_cert("*."+entry_domain, time, False)
        res = self.dedup_cert(certs)
        for item in res:
            for i in item[-1]:
                domain_set.add(i)
        Level1 = self.find_Level_1_domain(domain_set - self.domain_set)
        self.domain_set = self.domain_set | domain_set
        for l in Level1:
            if l not in self.level_1:
                self.level_1.add(l)
                self.queue.put(l)

    def get_all_valid_cert(self, domain, time):
        self.get_domain(domain, time)
        ths = []
        for i in range(self.thread_num):

            th = Thread(target=self.write_all_valid_cert, args=(time,))
            th.start()
            print("[+] Thread %d started.." % i)
            ths.append(th)
        for th in ths:
            th.join()
          
  

if __name__ == "__main__":
    domain = sys.argv[1]
    time = datetime.now()
    crt = crtsh_db()

    #get all subdomains logged in crt.sh
    crt.write_domain(domain)

    #thumbprint = 'ec02a2bafdddd9628dc3c3fe217a4c7a09167fdb'
    #crt.fcert_by_thumbprint(thumbprint)

    #crt.write_valid_cert(domain, time, False)
    # crt.get_all_valid_cert(domain, time)
    # res = crt.get_domain(domain, time)
    # print(res)
    # crt.write_table_info("name_type", "certificate_identity")
    # print(crt.select_table("name_type", "certificate_identity"))
    # print(crt.desc_table("certificate_identity"))
    
