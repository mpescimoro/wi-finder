#!/usr/bin/env python

"""
Author : pescimoro.mattia@gmail.com
Licence : GPL v3 or any later version

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.
 
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
 
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import sys
import nmap                         # import nmap.py
import time

try:
    nm = nmap.PortScanner()         # instance of nmap.PortScanner
except nmap.PortScannerError:
    print('Nmap not found', sys.exc_info()[0])
    sys.exit(0)
except:
    print("Unexpected error:", sys.exc_info()[0])
    sys.exit(0)

def seek():                         # function to scan the network
    nm.scan(hosts = '192.168.1.0/24', arguments = '-n -sP -PE -T5')
    # executes a ping scan

    localtime = time.asctime(time.localtime(time.time()))
    print('============ {0} ============'.format(localtime))
    # system time
    
    for host in nm.all_hosts():
        try:
            mac = nm[host]['addresses']['mac']
        except:
            mac = 'no data'
        host_list = (host, mac)
        print('Host: %s [%s]' % (host, mac))
        
    return host_list                # returns host_list(ipv4, mac)

def beep():                         # no sound dependency
    print('\a')            
    
if __name__ == '__main__':
    old_list = new_list = seek()
    
    # are there any new hosts?
    while (new_list <= old_list):
        time.sleep(1)               # increase to slow down the speed
        new_list = seek()

    # DANGER!!!
    print('OHSHITOHSHITOHSHITOHSHITOHSHIT!')
    beep()
