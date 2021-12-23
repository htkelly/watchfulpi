#!/usr/bin/python3

import datetime
import logging
import redis
import base64
import socket
import struct
import subprocess
from subprocess import DEVNULL
from bson.objectid import ObjectId
from io import BytesIO
from gpiozero import MotionSensor
from picamera import PiCamera
from time import sleep

#Define the SecurityEvent class used to log events.
class SecurityEvent:
    event_data = {}
    def __init__(self, captured_image):
        self.event_data["_id"] = str(ObjectId())
        self.event_data["sensor"] = str(sensorId)
        self.event_data["timestamp"] = str(datetime.datetime.utcnow())
        self.event_data["captured_image"] = captured_image

#Enable informational logging.
logging.basicConfig(level=logging.INFO)

#Declaring variables used for Redis interface (will be assigned later).
redis_connection = None
redis_pubsub = None

#generating a unique id for this sensor device.
sensorId = str(ObjectId())
logging.info("This sensor is identified as " + str(sensorId))

#Intialise PIR sensor (this prototype has it connected on GPIO 17).
pirSensor = MotionSensor(17)

#Variable to track whether the system is discoverable, initial state is true.
discoverable = True

#Variable to track system mode (0=standby, 1=sensing, 2=streaming).
sensorMode = 0

#Variable that will be used to manage video stream processes (needs to be global so we can terminate these processes when we want to switch back to 'sense' mode).
videoStream = None

#SSDP multicast IP and Port.
SSDP_MCAST_IP = '239.255.255.250'
SSDP_PORT = 5007

#Define the function that will be used to capture from the camera and return a base64 encoded image. Uses BytesIO to store a file-like stream in memory rather than writing the image to storage.
def captureImage():
    with BytesIO() as stream:
        with PiCamera() as camera:
            camera.capture(stream, format='jpeg', resize=(640, 480))
        stream.seek(0)
        encoded_image = base64.b64encode(stream.read())
    return encoded_image
	
#Define the function to return a SecurityEvent object when an event occurs, calls the captureImage() method to include an image.
def eventOccurred():
    event = SecurityEvent(captureImage())
    return event

#Define the fuction that will be called from the main loop when the system is set to 'sense'. Will record a security event when motion is detected, then wait until motion has stopped + 5 seconds.
#The recorded events (including base64 encoded image) are published to a messaging channel with the same name as the sensorId, which the hub will be subscribed to.
def watching():
    if pirSensor.motion_detected:
        logging.info("Motion has been detected")
        event = eventOccurred()
        logging.info("Publishing event to " + str(sensorId))
        redis_connection.publish(str(sensorId), str(event.event_data))
        pirSensor.wait_for_no_motion()
        sleep(5)

#Define the function used to check header values in SSDP requests (this is adapted from week 7 lab 2).
def headerValue(response, header):
    source = response.splitlines()
    for line in source:
        if line.startswith(header):
            return line[line.find(":")+1:]

#Define the function that will be called from the main loop when the system is discoverable.
#This is adapted from week 7 lab 2 and adds logic to connect to the redis server on the device that sent the SSDP request (since it).
#Since the IP of the hub device is known once the request is received, we can use this information to connect to redis on the hub, and subscribe to the messaging channel we will use to receive commands.
#The SSDP request is acknowledged by sending back the identifier of the sensor device and its IP address. Finally, the function sets the 'discoverable' variable to false.
def discoveryResponse():
    global discoverable
    global redis_connection
    global redis_pubsub
    ssdpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    ssdpSocket.setsockopt(socket.SOL_SOCKET,  socket.SO_REUSEPORT, 1)
    ssdpSocket.bind((SSDP_MCAST_IP, SSDP_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(SSDP_MCAST_IP), socket.INADDR_ANY)
    ssdpSocket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while discoverable:
        data, address = ssdpSocket.recvfrom(4096)
        data = str(data.decode('UTF-8'))
        logging.info('Received ' + str(len(data)) + ' bytes from ' + str(address))
        if headerValue(data,"ST") == 'urn:watchful_pi':
            logging.info("Responding to discovery request and connecting to messaging server")
            redis_connection = redis.StrictRedis(host=address[0], port=6379, db=0)
            redis_pubsub = redis_connection.pubsub()
            logging.info("Subscribing to commands channel")
            redis_pubsub.subscribe('watchful_commands')
            sleep(5)

            #Redis sends an initial confirmation message when we subscribe to a channel -- get that message before doing anything else so it doesn't cause any issues.
            message = redis_pubsub.get_message()    
            logging.info("Response from channel received: " + str(message))
            ssdpSocket.sendto(str(sensorId).encode(), address)
            discoverable = False

#Define the function that will be used to get commands from the redis messaging channel we are using for commands, and respond to them.
#If the command message includes this device's id or 'all', the device's current mode will be updated.
def getCommand():
    global redis_pubsub
    global sensorMode
    global videoStream
    message = redis_pubsub.get_message()

    #Sometimes the subscribtion confirmation comes in late from Redis for some reason -- return to the main loop without doing anything if this happens.
    if message:
        if isinstance(message['data'], int):
            logging.info("Looks like we got a delayed subscription confirmation message:" + str(message))
            return None     

        #If we get a command message, split it at ':' to separate the sensor id (or 'all') from the command. We only update the device mode if the command is targeted at this device or 'all'.
        split_message = message['data'].decode('UTF-8').split(":") 
        id = split_message[0]
        command = split_message[1]
        if id == str(sensorId) or id == 'all':
            if command == '0' and sensorMode != 0:
                sensorMode = 0
                if videoStream:
                    videoStream.terminate() #Note: when changing mode to 0 or 1, we need to kill the videoStream process if active (so it doesn't block access to the camera, among other reasons). This is why we use a global variable to identify this process.
                logging.info("Sensor is now in standby mode")
            if command == '1' and sensorMode != 1:
                sensorMode = 1
                if videoStream:
                    videoStream.terminate()
                logging.info("Sensor is now in motion sensing mode")
            if command == '2' and sensorMode != 2:
                sensorMode = 2
                logging.info("Sensor is now in streaming mode")
                
                #Runs a bash command to start mjpg_streamer, send the output to /dev/null, and use the videoStream variable to track the process. 
                #Interesting note: we need to use 'exec' to start mjpg_streamer, because if we run mjpg_streamer directly the PID tracked in the variable will be the bash shell used to execute mjpg_streamer, not the mjpg_streamer process itself.
                videoStream = subprocess.Popen('exec mjpg_streamer -i "input_raspicam.so"', shell=True, stdout=DEVNULL, stderr=DEVNULL)

    #We also use the core key-value storage functionality of redis to store the current sensor mode.
    #We use the sensorId as the key and the current mode as the value. This is simpler than using the message broker functionality to publish the device mode and track that in a separate variable in the hub program. 
    redis_connection.set(sensorId, sensorMode)
        

#Main loop that runs when the program is executed. While the device is discoverable, it will respond to discovery requests. Following discovery, calls getCommand() to get commands and update mode.
#If in mode 1, calls watching() to detect security events and publish them to a messaging channel with the same name as the sensorId, which the hub will be subscribed to.
def main():
    global discoverable
    while True:
        if discoverable:
            discoveryResponse()
        else:
            getCommand()
            if sensorMode == 1:
                watching()

if __name__ == "__main__":
    main()