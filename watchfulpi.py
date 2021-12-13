#!/usr/bin/python3
import subprocess
import logging
from subprocess import DEVNULL

#enable informational logging
logging.basicConfig(level=logging.INFO)

#launch the redis server
logging.info("Launching redis server")
redis_server = subprocess.Popen('exec redis-server --save ""', shell=True)

#launch the sensor
logging.info("Launching the sensor process")
watchful_sensor = subprocess.Popen('./watchful_sensor.py')

#launch the interace
logging.info("Launching the web interface")
watchful_interface = subprocess.Popen('./watchful_interface.py')

print("Watchful Pi is running on this device. Press enter to close.")
input()
watchful_sensor.terminate()
watchful_interface.terminate()
redis_server.terminate()