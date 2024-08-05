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
shIntCON = "show interface description | inc CON|con"

shutdownInt = [
    f'interface {interface}',
    'shutdown'
]
noShutInt = [
    f'interface {interface}',
    'no shutdown'
]
reachableDevices = []
unreachableDevices = []

lock = threading.Lock()

# Regex Patterns
intPatt = r'[a-zA-Z]+\d+\/(?:\d+\/)*\d+'
domainPatt = '.mgmt.internal.das'

def testCON(validIPs, username, netDevice, reachableDevices, unreachableDevices):
    # This function is test the connectivity to the INET network of the Opengear devices
    reachableDevices = []
    unreachableDevices = []

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

                    siteCode = re.sub(domainPatt, '', validDeviceIP)
                    authLog.info(f"The following Site Code was found: {siteCode}")
                    OpengearConn = siteCode + '-con-20-inet.anthem.com'

                    for interface in shIntCONOut1:
                        shutdownInt[0] = f'interface {interface}'
                        shutdownIntOut = sshAccess.send_config_set(shutdownInt)
                        authLog.info(f"Interface {interface} on device {validDeviceIP} was shutdown\n{shutdownIntOut}")
                    retries = 0
                    while retries <= maxRetries:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connTest:
                            startTime = time.time()
                            try:
                                authLog.info(f"Resolving hostname {OpengearConn}")
                                opengearIP = socket.gethostbyname(OpengearConn)
                                authLog.info(f"Hostname: {OpengearConn} resolves to: {opengearIP}")
                            except socket.gaierror as error:
                                authLog.error(f"DNS resolution failed for {OpengearConn}: {error}")
                                authLog.error(traceback.format_exc())
                                print(f"ERROR: Failed the DNS resolution for {OpengearConn}, error: {error}\n", traceback.format_exc())
                                unreachableDevices.append(OpengearConn)
                                break
                            try:
                                connTest.settimeout(retryInterval)
                                connResult = connTest.connect_ex((opengearIP, 22))
                                authLog.info(f"Test number: {retries + 1}, testing TCP Port 22 connectivity for address: {opengearIP}, device: {validDeviceIP}")
                                authLog.info(f"TCP Port 22 connectivity results: {connResult}")
                                if connResult == 0:
                                    print(f"Device {OpengearConn} is reachable on port TCP 22.")
                                    authLog.info(f"Device {OpengearConn} is reachable on port TCP 22.")
                                    reachableDevices.append(OpengearConn)
                                    break
                                else:
                                    print(f"Device {OpengearConn} is not reachable on port TCP 22.")
                                    authLog.error(f"Device: {OpengearConn}, is not reachable on port TCP 22.")
                                    authLog.error(f"Retry number: {retries + 1}, connectivity code error:{connResult}")
                                    retries += 1
                                    connResult = 0 

                            except socket.timeout:
                                print(f"INFO: Attempt {retries + 1}: Connection attempt timed out to device: {OpengearConn}, retrying now...")    
                                authLog.info(f"Attempt {retries + 1}: Connection attempt timed out to device: {OpengearConn}, retrying now...")
                                authLog.error(f"Retry number: {retries + 1}")
                                retries += 1
                                connResult = 0 

                            except socket.error as error:
                                print(f"ERROR: An error occurred: {error}\n", traceback.format_exc())
                                authLog.error(f"User {username} connected to {validDeviceIP} got an error: {error}")
                                authLog.error(traceback.format_exc(),"\n")

                            finally:
                                connTest.close()
                                time.sleep(retryInterval)
                    else:
                        print(f"Device {OpengearConn} is not reachable on port TCP 22 after {maxRetries} retries.")
                        authLog.error(f"Device: {OpengearConn}, is not reachable on port TCP 22.")
                        authLog.error(traceback.format_exc())
                        unreachableDevices.append(OpengearConn)

                    for interface in shIntCONOut1:
                        noShutInt[0] = f'interface {interface}'
                        noShutIntOut = sshAccess.send_config_set(noShutInt)
                        authLog.info(f"Interface {interface} on device {validDeviceIP} was brought up\n{noShutIntOut}")

                    writeMemOut = sshAccess.send_command('write')
                    print(f"INFO: Running configuration saved for device {validDeviceIP}")
                    authLog.info(f"Running configuration saved for device {validDeviceIP}\n{shHostnameOut}'write'\n{writeMemOut}")

                    with lock:
                        if OpengearConn in reachableDevices:
                            with open(f"Outputs/Reachable devices - INET - Opengear.txt", "a") as file:
                                file.write(f"The below devices were reachable on port TCP 22:\n{'\n'.join(reachableDevices)}\n")
                                authLog.info(f"File Reachable devices - INET - Opengear.txt was created successfully.")
                        else:
                            with open(f"Outputs/Unreachable devices - INET - Opengear.txt", "a") as file:
                                file.write(f"The below devices were unreachable on port TCP 22:\n{'\n'.join(unreachableDevices)}\n")
                                authLog.info(f"File Unreachable devices - INET - Opengear.txt was created successfully.")

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

def testConThread(validIPs, username, netDevice):
    threads = []

    for validDeviceIP in validIPs:
        thread = threading.Thread(target=testCON, args=(validDeviceIP, username, netDevice, reachableDevices, unreachableDevices))
        thread.start()
        authLog.info(f"Thread {thread} started.")
        threads.append(thread)
        authLog.info(f"Thread {thread} appended to threads: {threads}")

    for thread in threads:
        thread.join()