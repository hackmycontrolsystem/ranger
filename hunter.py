#!/usr/bin/env python
'''
Author: Christopher Duffy
Date: July 2015
Name: hunter.py
Purpose: To scan a network for a smb ports and validate if credentials work on the target host

Copyright (c) 2015, Christopher Duffy All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met: * Redistributions
of source code must retain the above copyright notice, this list of conditions and
the following disclaimer. * Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution. * Neither the
name of the nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL CHRISTOPHER DUFFY BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

import os, argparse, sys, time, logging
import utilities.network as network
import utilities.nmap as nmap_parser
try:
    import msfrpc
except ImportError as e:
    msg = "[!] Install the msfrpc library that can be found here: https://github.com/SpiderLabs/msfrpc.git"
    if "msgpack" in e.message.lower():
        # Library that msfrpc depends on but not installed by the msfrpc installer
        msg = "[!] Install the msgpack library: pip install msgpack-python"
    sys.exit(msg)
try:
    import nmap
except:
    sys.exit("[!] Install the nmap library: pip install python-nmap")

def target_identifier(dir, user, passwd, ips, port_num, ifaces, ipfile, logger=logging.getLogger()):
    hostlist = []
    pre_pend = "smb"
    service_name = 'microsoft-ds'
    service_name2 = 'netbios-ssn'
    protocol = 'tcp'
    port_state = 'open'
    bufsize = 0
    hosts_output = "%s/%s_hosts" % (dir, pre_pend)
    scanner = nmap.PortScanner()
    if ipfile != None:
        logger.info("[*] Extracting hosts from file: %s") % (ipfile)
        with open(ipfile) as f:
            hostlist = f.read().replace('\n',' ')
        scanner.scan(hosts=hostlist, ports=port_num)
    else:
        logger.info("[*] Scanning for port: %s within %s") % (str(port_num), str(ips))
        scanner.scan(hosts=ips, ports=port_num)
    open(hosts_output, 'w').close()
    hostlist=[]
    if scanner.all_hosts():
        e = open(hosts_output, 'a', bufsize)
    else:
        sys.exit("[!] No viable targets were found!")
    for host in scanner.all_hosts():
        for k,v in ifaces.iteritems():
            if v['addr'] == host:
                print("[-] Removing %s from target list since it belongs to your interface!") % (host)
                host = None
        if host != None:
            e = open(hosts_output, 'a', bufsize)
            if service_name or service_name2 in scanner[host][protocol][int(port_num)]['name']:
                if port_state in scanner[host][protocol][int(port_num)]['state']:
                    logger.info("[+] Adding host %s to %s since the service is active on %s" % (host, hosts_output, port_num))
                    hostdata=host + "\n"
                    e.write(hostdata)
                    hostlist.append(host)
                else:
                    logger.info("[-] Host %s was not added to %s due to there being no open service on %s" % (host, hosts_output, port_num))
    if not hostlist:
        logger.info("[!] No open services found")
    if not scanner.all_hosts():
        e.closed
    if hosts_output:
        return hosts_output, hostlist

def build_command(user, passwd, dom, port, ip):
    module = "auxiliary/scanner/smb/smb_enumusers_domain"
    command = '''use ''' + module + '''
set RHOSTS ''' + ip + '''
set SMBUser ''' + user + '''
set SMBPass ''' + passwd + '''
set SMBDomain ''' + dom +'''
run
'''
    return command, module

def run_commands(iplist, user, passwd, dom, port, file, logger=logging.getLogger()):
    bufsize = 0
    e = open(file, 'a', bufsize)
    done = False
    client = msfrpc.Msfrpc({})
    client.login('msf','msfrpcpassword')
    try:
        result = client.call('console.create')
    except:
        sys.exit("[!] Creation of console failed!")
    console_id = result['id']
    console_id_int = int(console_id)
    for ip in iplist:
        logger.info("[*] Building custom command for: %s" % (str(ip)))
        command, module = build_command(user, passwd, dom, port, ip)
        logger.info("[*] Executing Metasploit module %s on host: %s" % (module, str(ip)))
        client.call('console.write',[console_id, command])
        time.sleep(1)
        while done != True:
            result = client.call('console.read',[console_id_int])
            if len(result['data']) > 1:
                if result['busy'] == True:
                    time.sleep(1)
                    continue
                else:
                    console_output = result['data']
                    e.write(console_output)
                    logger.info(console_output)
                    done = True
    e.closed
    client.call('console.destroy',[console_id])

def main():
    # If script is executed at the CLI
    usage = '''usage: %(prog)s [-u username] [-p password] [-d domain] [-t IP] [-l IP_file] [-r ports] [-o output_dir] [-f filename] -q -v -vv -vvv'''
    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument("-u", action="store", dest="username", default="Administrator", help="Accepts the username to be used, defaults to 'Administrator'")
    parser.add_argument("-p", action="store", dest="password", default="admin", help="Accepts the password to be used, defalts to 'admin'")
    parser.add_argument("-d", action="store", dest="domain", default="WORKGROUP", help="Accepts the domain to be used, defalts to 'WORKGROUP'")
    parser.add_argument("-t", action="store", dest="targets", default=[], nargs="+", help="Accepts the IP  to be used, can provide a range, single IP or CIDR")
    parser.add_argument("-l", action="store", dest="targets_file", default=None, help="Accepts a file with IP addresses, ranges, and CIDR notations delinated by new lines")
    parser.add_argument("-r", action="store", dest="ports", default="135", help="Accepts the port to be used, defalts to '135'")
    parser.add_argument("-o", action="store", dest="home_dir", default="/root", help="Accepts the dir to store any results in, defaults to /root")
    parser.add_argument("-f", action="store", dest="filename", default="results", help="Accepts the filename to output relevant results")
    parser.add_argument("-v", action="count", dest="verbose", default=1, help="Verbosity level, defaults to one, this outputs each command and result")
    parser.add_argument("-q", action="store_const", dest="verbose", const=0, help="Sets the results to be quiet")
    parser.add_argument("-s", action="store_true", dest="should_scan", default=False, help="Performs port scan")
    parser.add_argument("-x", action="store", dest="nmap_xml_filenames", default=[], nargs="+", help="Accepts the comma separated filenames of NMap XML files to use for host list")
    parser.add_argument('--version', action='version', version='%(prog)s 0.42b')
    args = parser.parse_args()

    # Argument Validator
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    if (args.targets == None) and (args.targets_file == None):
        parser.print_help()
        sys.exit(1)

    # Set Constructors
    verbose = args.verbose             # Verbosity level
    password = args.password           # Password or hash to test against default is admin
    username = args.username           # Username to test against default is Administrator
    domain = args.domain               # Domain default is WORKGROUP
    ports = args.ports                 # Port to test against Default is 445
    targets = args.targets             # Hosts to test against
    targets_file = args.targets_file   # Hosts to test against loaded by a file
    home_dir = args.home_dir           # Location to store results
    filename = args.filename           # A file that will contain the final results
    should_scan = args.should_scan     # Should perform port scan default is False
    nmap_xml_filenames = args.nmap_xml_filenames
    gateways = {}
    network_ifaces={}
    target_list = []

    # Configure logger
    logger = logging.getLogger()
    if verbose == 0:
        level = logging.ERROR
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG
    logger.setLevel(level)
    stream_handler = logging.StreamHandler()
    log_format = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s") # Log format
    stream_handler.setFormatter(log_format)
    logger.addHandler(stream_handler)

    # Set filename
    if not filename:
        if os.name != "nt":
             filename = home_dir + "/msfrpc_smb_output"
        else:
             filename = home_dir + "\\msfrpc_smb_output"
    else:
        if filename:
            if "\\" or "/" in filename:
                logger.info("[*] Using filename: %s" % (filename))
        else:
            if os.name != "nt":
                filename = home_dir + "/" + filename
            else:
                filename = home_dir + "\\" + filename
                logger.info("[*] Using filename: %s") % (filename)

    # Populate list of targets
    if targets:
        target_list += targets
    if targets_file:
        with open(targets_file, "r") as ifh:
            lines = [line.rstrip() for line in ifh.readlines()]
            target_list += lines

    gateways = network.get_gateways()
    network_ifaces = network.get_networks(gateways)
    if should_scan:
        hosts_file, hostlist = target_identifier(home_dir, username, password, target_list, ports, network_ifaces, targets_file)
    elif nmap_xml_filenames:
        hosts = map(nmap_parser.parse2, nmap_xml_filenames)
        hosts = sum(hosts, [])  # flatten
        hostlist = [host.hostname for host in hosts]
    elif targets:
        hostlist = target_list
    run_commands(hostlist, username, password, domain, ports, filename)

if __name__ == '__main__':
    main()
