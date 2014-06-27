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

import sys
import os
import nmap                         # importa nmap.py
import time                         
import winsound

try:
    nm = nmap.PortScanner()         # crea un'istanza di nmap.PortScanner
except nmap.PortScannerError:
    print('Nmap not found', sys.exc_info()[0])
    sys.exit(0)
except:
    print("Unexpected error:", sys.exc_info()[0])
    sys.exit(0)

def seek():                        # definisce una funzione per analizzare della rete
    count = 0
    nm.scan(hosts='192.168.1.0/24', arguments='-n -sP -T4')
    # effettua un ping sweep veloce

    hosts_list = [(x) for x in nm.all_hosts()]
    # salva la lista degli host

    localtime = time.asctime(time.localtime(time.time()))
    print('Local current time :', localtime)
    # stampa l'orario di sistema
    
    for host in hosts_list:        # conta e stampa gli indirizzi attivi
        count = count + 1
        print('IP: {0}'.format(host))
    print('-----------------')
    return count                   # ritorna il numero di indirizzi

count = new_count = seek()

# controlla che il numero di indirizzi attivi rimanga invariato
while (new_count <= count):
    new_count = seek()

# DANGER!!!
print('OHSHITOHSHITOHSHITOHSHITOHSHIT!')
winsound.Beep(1750,1000)
