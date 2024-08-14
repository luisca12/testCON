from netmiko import ConnectHandler
from log import authLog

import traceback
import threading
import socket
import time
import re
import os

interface = ''
retryInterval = 5
maxRetries = 180
retries = 0

shHostname = "show run | i hostname"
shIntCON = "show interface description | inc CON|con|NET|Net|net"
shMac = [
    f'show mac address-table interface {interface}',
]

# Regex Patterns
intPatt = r'[a-zA-Z]+\d+\/(?:\d+\/)*\d+'

def showOpenMAC(validIPs, username, netDevice):
    # This function is test the connectivity to the INET network of the Opengear devices

    validIPs = [validIPs]
    for validDeviceIP in validIPs:
        try:
            validDeviceIP = validDeviceIP.strip()
            currentNetDevice = {
                'device_type': 'cisco_xe',
                'ip': validDeviceIP,
                'username': username,
                'password': netDevice['password'],
                'secret': netDevice['secret'],
                'global_delay_factor': 2.0,
                'timeout': 120,
                'session_log': 'netmikoLog.txt',
                'verbose': True,
                'session_log_file_mode': 'append'
            }

            print(f"Connecting to device {validDeviceIP}...")
            with ConnectHandler(**currentNetDevice) as sshAccess:
                try:
                    sshAccess.enable()
                    shHostnameOut = sshAccess.send_command(shHostname)
                    authLog.info(f"User {username} successfully found the hostname {shHostnameOut}")
                    shHostnameOut = shHostnameOut.replace('hostname', '').strip() + "#"

                    print(f"INFO: Taking a \"{shIntCON}\" for device: {validDeviceIP}")
                    shIntCONOut = sshAccess.send_command(shIntCON)
                    authLog.info(f"Automation successfully ran the command:{shIntCON}\n{shHostnameOut}{shIntCON}\n{shIntCONOut}")

                    shIntCONOut1 = re.findall(intPatt, shIntCONOut)
                    authLog.info(f"The following interfaces were found under the command: {shIntCON}: {shIntCONOut1}")

                    for interface in shIntCONOut1:
                        shMac[0] = f'show mac address-table interface {interface}'
                        shMacOut = sshAccess.send_config_set(shMac)

                except Exception as error:
                    print(f"ERROR: An error occurred: {error}\n", traceback.format_exc())
                    authLog.error(f"User {username} connected to {validDeviceIP} got an error: {error}")
                    authLog.error(traceback.format_exc(),"\n")
                    os.system("PAUSE")
       
        except Exception as error:
            print(f"ERROR: An error occurred: {error}\n", traceback.format_exc())
            authLog.error(f"User {username} connected to {validDeviceIP} got an error: {error}")
            authLog.error(traceback.format_exc(),"\n")
            with open(f"failedDevices.txt","a") as failedDevices:
                failedDevices.write(f"User {username} connected to {validDeviceIP} got an error.\n")
        
        finally:
            print(f"Outputs and files successfully created for device {validDeviceIP}.\n")
            print("For any erros or logs please check Logs -> authLog.txt\n")