#!/usr/bin/python3

import datetime
import logging
import subprocess
import base64
import redis
from subprocess import DEVNULL
from dotenv import dotenv_values
from pymongo import MongoClient
from bson.objectid import ObjectId
from gpiozero import MotionSensor
from picamera import PiCamera
from io import BytesIO

#load config from .env file
config = dotenv_values(".env")

#enable informational logging
logging.basicConfig(level=logging.INFO)

#define the SecurityEvent class used to log events
class SecurityEvent:
    event_data = {}
    def __init__(self, captured_image):
        self.event_data["_id"] = ObjectId()
        self.event_data["timestamp"] = datetime.datetime.utcnow()
        self.event_data["captured_image"] = captured_image

#connect to redis server and subscribe to 'watchful_commands' channel with a pubsub interface
redis_broker = redis.StrictRedis(host=config["redisServerHost"], port=6379, db=0)
subscription = redis_broker.pubsub()
subscription.subscribe('watchful_commands')

#connect to mongodb database
client = MongoClient(config["mongoServerHost"], 27017)
db = client.watchfulpi
event_collection = db.security_events

#intialise PIR sensor
pirSensor = MotionSensor(17)

#variable to track whether the system is sensing or streaming (intial state is sensing)
motionSensingActive = True
videoStreamingActive = False

#variable that will be used to manage video streams
videoStream = None

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

#watching function waits for motion, captures images, and logs events to mongodb
def watching():
    if pirSensor.motion_detected:
        logging.info("Motion has been detected")
        event = event_occurred()
        event_collection.insert_one(event.event_data)
        logging.info("Event id " + str(event.event_data["_id"]) + " has been logged to the database")
        pirSensor.wait_for_no_motion()

#function to get messages from redis and change system state
def getMessage():
    global motionSensingActive
    global videoStreamingActive
    global videoStream
    message = subscription.get_message()
    if message and message["data"] == b'STREAM' and not videoStreamingActive:
        motionSensingActive = False
        videoStreamingActive = True
        logging.info("Launching the stream process")
        videoStream = subprocess.Popen('exec mjpg_streamer -i "input_raspicam.so"', shell=True, stdout=DEVNULL, stderr=DEVNULL)
    if message and message["data"] == b'SENSE' and not motionSensingActive:
        videoStreamingActive = False
        motionSensingActive = True
        if videoStream:
            videoStream.terminate()

#main loop, calls watching function if system is armed
def main():
    global motionSensingActive
    global videoStreamingActive
    while True:
        getMessage()
        if motionSensingActive:
            watching()

if __name__ == "__main__":
    main()