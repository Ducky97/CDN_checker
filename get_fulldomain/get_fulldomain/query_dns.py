import re
import sys
import os
import dns.resolver

def sort_domains(domain):
    out_domains = []

    sorting = set()
    path_t = sys.path[0]+"/get_fulldomain/output/domain/fulldomain/"+domain+".txt"
    f1 = open(path_t)
    ds = f1.read().split('\n')
    for d in ds:
        d = '.'.join(d.split(".")[::-1])
        out_domains.append(d)
    out_domains.sort()
    for i in range(len(out_domains)):
        out_domains[i] = '.'.join(out_domains[i].split(".")[::-1])
    f1.close()
    return out_domains

def read_domains(filename):
    with open(filename) as f:
        text = f.read()
        return re.findall('(.*)\n', text)

def write_DNSres(domain, domain_names):
    path_t = sys.path[0] + "/get_fulldomain/output/domain/dnsres/"+domain+"_DNSres.txt"
    # with open("../output/domain/dnsres/"+domain+"_DNSres.txt", "w") as f:
    with open(path_t, "w") as f:
        for domain in domain_names:
            try:
                A = dns.resolver.query(domain, "A")
                for i in A.response.answer:
                    f.write(str(i)+'\n')
                    print("Resolved! "+ str(i) )
                f.write('\n')
            except Exception as e:
                 print(e)
                 f.write("NXDOMAIN for "+domain+'\n\n')

def get_resolved_domains(domain):
    count = 0
    path_t = sys.path[0] + "/get_fulldomain/output/domain/dnsres/"+domain+"_DNSres.txt"
    # f1 = open('../output/domain/dnsres/'+domain+'_DNSres.txt')
    f1 = open(path_t)
    path_t = sys.path[0] + '/get_fulldomain/output/domain/resolved_domain/'+domain+'.txt'
    # f2 = open('../output/domain/resolved_domain/'+domain+".txt", "w")
    f2 = open(path_t, "w")
    lines = f1.read().split('\n\n')
    for line in lines:
        if re.findall('NXDOMAIN', line) or not line:
            continue
        else:
            count += 1
            f2.write(line.split('. ')[0]+'\n')
    f1.close()
    f2.close()
    return count

if __name__=='__main__':
    domains = sys.argv[1:]
    for domain in domains:
        sort_domains(domain)
        print("Finding DNS record for domian %s" % domain)
        write_DNSres(domain, read_domains("sorted/"+domain+".sorted.txt"))
        print("DNS records have been written, finding resolved domains")
        count = get_resolved_domains(domain)
        print("Done! Total %d resolved domains for %s found!"%(count,domain))

