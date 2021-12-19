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


#define the SecurityEvent class used to log events
class SecurityEvent:
    event_data = {}
    def __init__(self, captured_image):
        self.event_data["_id"] = str(ObjectId())
        self.event_data["sensor"] = str(sensor_id)
        self.event_data["timestamp"] = str(datetime.datetime.utcnow())
        self.event_data["captured_image"] = captured_image

#enable informational logging
logging.basicConfig(level=logging.INFO)

#declaring variables used for Redis interface (will be assigned later)
redis_connection = None
redis_pubsub = None

#generating a unique id for this sensor device
sensor_id = ObjectId()
logging.info("This sensor is identified as " + str(sensor_id))

#intialise PIR sensor
pirSensor = MotionSensor(17)

#variable to track whether the system is discoverable
discoverable = True

#variable to track whether the system is sensing or streaming (intial state is sensing)
motionSensingActive = True
videoStreamingActive = False

#variable that will be used to manage video streams
videoStream = None

#SSDP multicast IP and Port	
SSDP_MCAST_IP = '239.255.255.250'
SSDP_PORT = 5007

def headerValue(response, header):
    source = response.splitlines()
    for line in source:
        if line.startswith(header):
            return line[line.find(":")+1:]

#define the function that will be used to capture from the camera and return a base64 encoded image
def capture_image():
    stream = BytesIO()
    with PiCamera() as camera:
        camera.capture(stream, format='jpeg', resize=(320, 240))
    stream.seek(0)
    encoded_image = base64.b64encode(stream.read())
    return encoded_image
	
#define the function to return a SecurityEvent object when an event occurs
def event_occurred():
    event = SecurityEvent(capture_image())
    return event
	
def watching():
    if pirSensor.motion_detected:
        logging.info("Motion has been detected")
        event = event_occurred()
        logging.info("Publishing event to " + str(sensor_id))
        redis_connection.publish(str(sensor_id), str(event.event_data))

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
            message = redis_pubsub.get_message()
            logging.info("Response from channel received: " + str(message))
            ssdpSocket.sendto(str(sensor_id).encode(), address)
            discoverable = False
			
def getCommand():
    global redis_pubsub
    global videoStreamingActive
    global motionSensingActive
    global videoStream
    message = redis_pubsub.get_message()
    if message:
        if isinstance(message['data'], int):
            logging.info("Looks like we got a confirmation that the messaging channel is active:" + str(message))
            return None
        split_message = message['data'].decode('UTF-8').split(":")
        id = split_message[0]
        command = split_message[1]
        if id == str(sensor_id):
            if command == 'STREAM' and not videoStreamingActive:
                motionSensingActive = False
                videoStreamingActive = True
                logging.info("Launching the stream process")
            videoStream = subprocess.Popen('exec mjpg_streamer -i "input_raspicam.so"', shell=True, stdout=DEVNULL, stderr=DEVNULL)
            if command == 'SENSE' and not motionSensingActive:
                videoStreamingActive = False
                motionSensingActive = True
                if videoStream:
                    videoStream.terminate()

#main loop, calls watching function if system is armed
def main():
    global discoverable
    while True:
        if discoverable:
            discoveryResponse()
        else:
            getCommand()
            if motionSensingActive:
                watching()

if __name__ == "__main__":
    main()