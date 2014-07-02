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
    nm = nmap.PortScanner()         # creates an'instance of nmap.PortScanner
except nmap.PortScannerError:
    print('Nmap not found', sys.exc_info()[0])
    sys.exit(0)
except:
    print("Unexpected error:", sys.exc_info()[0])
    sys.exit(0)

def seek():                        # defines a function to analize the network
    count = 0
    nm.scan(hosts='192.168.1.0/24', arguments='-n -sP -PE -T5')
    # executes a ping scan

    hosts_list = [(nm[x]['addresses']) for x in nm.all_hosts()]
    # saves the host list

    localtime = time.asctime(time.localtime(time.time()))
    print('============ {0} ============'.format(localtime))
    # print out system time
    
    for addresses in hosts_list:
        count = count + 1
        print('FOUND {0}'.format(addresses))
    return count                   # returns the host number

def beep():                        # no sound dependency
    print ('\a')            
    
if __name__ == '__main__':
    count = new_count = seek()

    # check if the number of addresses is still the same
    while (new_count <= count):
        new_count = seek()
        time.sleep(1);

    # DANGER!!!
    print('OHSHITOHSHITOHSHITOHSHITOHSHIT!')
    beep()
