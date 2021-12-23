#!/usr/bin/python3

import logging
import socket
import redis
import subprocess
import json
import ast
import requests
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from PIL import Image, ImageDraw
from io import BytesIO
from subprocess import DEVNULL
from dotenv import dotenv_values
from pymongo import MongoClient
from time import sleep

#Load config/environmental variables from .env file.
config = dotenv_values('.env')

#Enable informational logging.
logging.basicConfig(level=logging.INFO)

#Open the redis server as a subprocess (uses exec rather than running directly, so that this Popen object can be closed cleanly).
redis_server_process = subprocess.Popen('exec redis-server --save "" --protected-mode no', shell=True)

#Give redis a moment to start (this prevents issues with discovered sensors attempting to connect too early).
sleep(1)

#Initialise the connection to the local redis server and open a pubsub interface for messaging.
redis_connection = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)
redis_pubsub = redis_connection.pubsub()

#Connect to mongodb database where security events received from sensors will be stored.
client = MongoClient(config["mongoServerHost"], 27017)
db = client.watchfulpi
event_collection = db.security_events

#SSDP M-SEARCH request, to be sent over HTTPU for device discovery (adapted from week 7 lab 2)
msg = \
    'M-SEARCH * HTTP/1.1\r\n' \
    'HOST:239.255.255.250:5007\r\n' \
    'ST:urn:watchful_pi\r\n' \
    'MX:2\r\n' \
    'MAN:"ssdp:discover"\r\n' \
    '\r\n'

#Port and IP for SSDP multicast group
SSDP_MCAST_IP = '239.255.255.250'
SSDP_PORT = 5007

#The hub will send out 10 discovery requests to the multicast group (in a future version, this might run continuously/asynchronously). On execution, the hub will be in 'discoverable' mode, and will change mode after 10 requests.
maxDiscoveryRequests = 10
discovering = True

#Function to send mail alerts using mailgun. This is adapted from week 9 lab 2. Uses BytesIO to read the image from an in-memory stream rather than a file on storage.
def send_mail(from_, to, subject, text, image):
    smtpServer = "smtp.mailgun.org"
    smtpUser = config['smtpUser']
    smtpPassword = config['smtpPassword']
    port = 587

    with BytesIO(base64.b64decode(image)) as stream:
        stream.seek(0)
        msgImage = MIMEImage(stream.read())
    
    msg = MIMEMultipart()
    msg.attach(MIMEText(text))
    msgImage['Content-Disposition'] = 'attachment; filename="image.jpg"'
    msg.attach(msgImage)
    msg['Subject'] = subject

    s = smtplib.SMTP(smtpServer, port)
    s.login(smtpUser, smtpPassword)
    s.sendmail(from_, to, msg.as_string())
    s.quit()


#Function to send SSDP M-SEARCH requests and receive responses. Returns a dict of discovered sensors (key will be the sensor id, value will be its IP address).
#Adapted from Week 7 lab 2. Some changes were needed as the lab example worked in a Packet Tracer simulation, not on a real device. 
#Need to use a try/except block to catch exceptions when reading from the socket times out (i.e. when there's no response from a sensor device).
def discover():
    global discovering
    discovered_sensors = {}
    ssdpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ssdpSocket.settimeout(2)
    count = 0 
    while discovering:
        ssdpSocket.sendto(msg.encode(), (SSDP_MCAST_IP, SSDP_PORT))
        try:
            message, address = ssdpSocket.recvfrom(512)
            discovered_sensors[message.decode()] = str(address[0])
            logging.info("Found a sensor")
        except:
            logging.info("Socket timed out (no response message)")
        finally:
            count += 1
            if count == maxDiscoveryRequests:
                discovering = False
                if len(discovered_sensors) == 0:
                    logging.info("No sensors discovered. Exiting.")
                    exit()
    return discovered_sensors

#Function that takes a dict object of sensor devices (as returned by discover()) and subscribes to their channels on the Redis message broker.
#This is how the hub will receive security events from the sensors.
def subscribeToSensors(sensors):
    global subscription
    if len(sensors) > 0:
        for key in sensors:
            #logging.info("subscribing to " + str(key))
            redis_pubsub.subscribe(str(key))
            message = redis_pubsub.get_message()
            logging.info("Subscribed: " + str(message))
    else:
        logging.info("No sensors discovered")

#Function to send images to Azure Face API for analysis. Returns an updated image and notes, or original image and "None" notes if no face detected.
#In its current implementation this is a proof-of-concept that will work for one face. In later versions we can add support for multiple faces.
def azureFaceDetection(image):
    headers = {
    'Ocp-Apim-Subscription-Key': config['subscription_key'],
    'Content-Type': 'application/octet-stream'
    }
    params = {
    'detectionModel': 'detection_01',
    'returnFaceId': 'true',
    'returnFaceAttributes': 'age,gender'
    }

    #Send a POST request with the headers specifying the Azure subscription key and Content-Type we will use to send the image, and params specifying what data we want to get back.
    #The JSON response from the Azure Face API is stored in the 'response' variable.
    response = requests.post(config['face_api_endpoint'], params=params, headers=headers, data=base64.b64decode(image))
    
    #If exactly one face is detected by Azure Face API
    if len(response.json()) == 1:
        logging.info("A face was detected by Azure Face API:" + str(response.json()))

        #Get the coordinates of the rectangle around the face detected    
        top = response.json()[0].get("faceRectangle").get("top")
        left = response.json()[0].get("faceRectangle").get("left")
        bottom = response.json()[0].get("faceRectangle").get("top") + response.json()[0].get("faceRectangle").get("height")
        right = response.json()[0].get("faceRectangle").get("left") + response.json()[0].get("faceRectangle").get("width")
        
        #We can use those coordinates together with the PIL module to draw a rectangle on our image, write the new image to an in-memory stream, re-encode it to base64 and return it.
        #We also return a string with the age and gender of the detected face, as guessed by Azure.
        returned_image = BytesIO()
        with Image.open(BytesIO(base64.b64decode(image))) as im:
            draw = ImageDraw.Draw(im)
            draw.line([left,top,right,top,left,top,left,bottom,left,bottom,right,bottom,right,bottom,right,top], fill=(0,223,0), width=3)
            im.save(returned_image, format="jpeg")
            returned_image.seek(0)
        return base64.b64encode(returned_image.read()),"Subject appears to be a " + str(int(response.json()[0].get("faceAttributes").get("age"))) + " year old "  + response.json()[0].get("faceAttributes").get("gender") + "."
    
    #If zero or multiple faces are returned, for now we return the original image with "None" for the notes.
    else:
        return image, "None"

#Main loop, first runs in 'discovery' mode, then once subscribed to the messaging channels for the discovered sensors, waits for events, sends images to Azure for facial analysis, sends an email alert, and logs the event to mongoDB.
def main():
    while True:
        if discovering:
            logging.info("Discovering")
            sensors = discover()
            logging.info("Subscribing")
            subscribeToSensors(sensors)

            #The dict with the discovered sensors is stored in a Redis with the key 'sensors' -- this is where the web interface can access it from.
            redis_connection.set('sensors', json.dumps(sensors))
        else:
            message = redis_pubsub.get_message()
            if message:

                #Sometimes the subscribtion confirmation comes in late from Redis for some reason -- continue from the start of the next iteration if this happens
                if isinstance(message['data'], int):
                    logging.info("Looks like we got a delayed subscription confirmation message" + str(message))
                    continue
                
                #Need to use ast.literal_eval to parse the message and return a Python dict
                event = ast.literal_eval(message['data'].decode('UTF-8'))
                logging.info("Logging a security event from sensor " + event['sensor'])

                #call azureFaceDetection() to do the image analysis
                event['captured_image'], event['notes'] = azureFaceDetection(event['captured_image'])

                #Log the event in mongoDB
                event_collection.insert_one(event)

                #Send an email alert. For this protoype the alert goes to a test email predefined in an environmental variable, but this will be user updateable in future.
                alert_message = "Hi, this alert fired at " + event['timestamp'] + "\n\nNotes: " + event['notes'] 
                send_mail("watchfulpi@watchfulpi.io", config['testEmail'], 'An alert from watchful Pi', alert_message, event['captured_image'])

if __name__ == "__main__":
    main()
