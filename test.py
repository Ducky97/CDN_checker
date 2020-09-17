from nslookup import Nslookup
import sys
import requests
import time
import socket
import dns.resolver
import queue
import re
import os
import json


# 使用Json保存结果
class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)


# 取消反爬虫技能,test
headers = {
    'Content-Type': 'text/plain; charset=UTF-8',
    'Origin':'https://maoyan.com',
    'Referer':'https://maoyan.com/board/4',
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
}

# 获取cname记录
def get_dns_item(domain_name, crawl_re, item):
    print(domain_name, crawl_re, crawl_re.url, item)
    checked_dn = domain_name
    if domain_name.count('.') > 1:
        try:
            dns_result = dns.resolver.query(domain_name, item)
            r = set()
            if item == "A":
                for i in dns_result:
                    r.add(i.address)
                dns_result = r
            else:
                for i in dns_result:
                    r.add(i.to_text())
                dns_result = r
        except Exception as e:
            dns_result  = e
    elif domain_name.count('.') == 1:
        try:
            url = crawl_re.url
            # relocated_domain = re.match('http.?://(.*)?/?.*', url).group(1)
            relocated_domain = url.split("/")[2]
            if "?" in relocated_domain:
                relocated_domain = relocated_domain.split("?")[0]
            print("!!!!!!!!!!!!!!!!!relocated_domain", relocated_domain)
            # 看看重定位的网页是不是多级域名
            if relocated_domain.count('.') > 1:
                # CNAME
                try:
                    checked_dn = relocated_domain
                    r = set()
                    dns_result = dns.resolver.query(relocated_domain, item)
                    if item == "A":
                        for i in dns_result:
                            r.add(i.address)
                        dns_result = r
                    else:
                        for i in dns_result:
                            r.add(i.to_text())
                        dns_result = r
                except Exception as e:
                    dns_result = e
            else:
                # 重定位域名还是一级域名
                checked_dn = domain_name
                dns_result = "still a low_level domain_name"
        except:
            checked_dn = domain_name
            dns_result = "domain name invalid"
    else:
        checked_dn = domain_name
        dns_result = "domain name invalid"

    return checked_dn, dns_result


# 获取ping结果
def get_ping(domain):
    ip_set = set()
    try:
        for i in range(15):
            ip_set.add(socket.gethostbyname(domain))
        return domain, ip_set
    except Exception as e:
        return domain, e
    # line = domain + '\t' + '\t'.join(ip_set) + '\n'
    # # print("!!!", line)
    # with open('ping.txt', 'a') as f:
    #     f.write(line)
    #     f.close()


# 获取nslookup结果
def get_nslookup(domain):
    dns_query = Nslookup(dns_servers=['8.8.8.8'])
    try:
        ips_record = dns_query.dns_lookup(domain)
        return domain, ips_record.answer
    except Exception as e:
        return domain, e


def save(domain, result):
    path = "top-1m"
    with open(path+"/"+domain+".json", "w") as f:
        json.dump(result, f, indent=4, cls=MyEncoder)
    

# 还是要保存header
def crawl_one_page(domain):
    total_result = dict()
    # 开始爬取页面
    protocol_s = ["http", "https"]
    # 结果保存在total_result_s里面
    total_result = dict()
    for protocol in protocol_s:
        url = protocol + "://" + domain
        try:
            requests_re = requests.get(url, headers = headers)
            # 记录headers
            if protocol not in total_result:
                total_result[protocol] = dict()
                total_result[protocol]['header'] = dict(requests_re.headers)

                # 检查现在要测的domain(nslookup,ping项目)
                nslookup_result = get_nslookup(domain)
                ping_result = get_ping(domain)

                d,r = nslookup_result[0], nslookup_result[1]
                total_result[protocol]['nslookup'] = dict()
                total_result[protocol]['nslookup'][d] = r

                d,r = ping_result[0], ping_result[1]
                total_result[protocol]['ping'] = dict()
                total_result[protocol]['ping'][d] = r
                # 可能会有跳转
                try:
                    # relocated_domain = re.match('http.?://(.*)?/?.*', requests_re.url).group(1)
                    relocated_domain = requests_re.url.split("/")[2]
                    if "?" in relocated_domain:
                        relocated_domain = relocated_domain.split("?")[0]
                    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!SSSSSSSSSSSSSSSSSSSS", relocated_domain, domain)
                    if relocated_domain != domain:
                        nslookup_result = get_nslookup(relocated_domain)
                        ping_result = get_ping(relocated_domain)

                        d,r = nslookup_result[0], nslookup_result[1]
                        total_result[protocol]['nslookup'][d] = r

                        d,r = ping_result[0], ping_result[1]
                        total_result[protocol]['ping'][d] = r
                except:
                    pass

                # DNS 检查
                item_list = ['CNAME', 'A']
                for item in item_list:
                    dns_result = get_dns_item(domain_name=domain, crawl_re=requests_re, item=item)
                    total_result[protocol][item] = dict()
                    total_result[protocol][item][dns_result[0]] = dns_result[1]
        except Exception as e:
            if protocol not in total_result:
                total_result[protocol] = e
            pass
    save(domain, total_result)
  
      


if __name__ == "__main__":
    path = "top-1m.csv"
    cmd = "mkdir " + path.split('.')[0]
    os.system(cmd)
    with open(path, 'r') as f:
        line = f.readline()
        num = 0
        while line and num<500:
            domain = line.strip().split(',')[1]
            # print(line.strip(), domain)
            crawl_one_page(domain)
            line = f.readline()
            num += 1
    # while True:
    #     domain = input("domain: ")
    #     crawl_one_page(domain)
