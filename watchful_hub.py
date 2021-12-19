import logging
import socket
import redis
import subprocess
import json
import ast
import requests
import base64
from PIL import Image, ImageDraw
from io import BytesIO
from subprocess import DEVNULL
from dotenv import dotenv_values
from pymongo import MongoClient

#load config from .env file
config = dotenv_values('.env')

#enable informational logging
logging.basicConfig(level=logging.INFO)

#Open the redis server as a subprocess (uses exec rather than running directly, so that this Popen object can be closed cleanly)
redis_server_process = subprocess.Popen('exec redis-server --save "" --protected-mode no', shell=True)

#Initialise the connection to the local redis server and create a pubsub interface
redis_connection = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)
redis_pubsub = redis_connection.pubsub()

#Connect to mongodb database
client = MongoClient(config["mongoServerHost"], 27017)
db = client.watchfulpi
event_collection = db.security_events

#SSDP M-SEARCH request, to be sent over HTTPU for device discovery
msg = \
    'M-SEARCH * HTTP/1.1\r\n' \
    'HOST:239.255.255.250:5007\r\n' \
    'ST:urn:watchful_pi\r\n' \
    'MX:2\r\n' \
    'MAN:"ssdp:discover"\r\n' \
    '\r\n'

SSDP_MCAST_IP = '239.255.255.250'
SSDP_PORT = 5007
maxDiscoveryRequests = 3
discovering = True

#Function to send SSDP M-SEARCH requests and receive responses
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

#Function that takes a dict object of sensor devices and subscribes to their channels on the Redis message broker
def subscribe(sensors):
    global subscription
    if len(sensors) > 0:
        for key in sensors:
            #logging.info("subscribing to " + str(key))
            redis_pubsub.subscribe(str(key))
            message = redis_pubsub.get_message()
            logging.info("Subscribed: " + str(message))
    else:
        logging.info("No sensors discovered")

#Function to send images to Azure Face API for analysis. Returns an updated image and notes, or original image and "None" notes if no face detected
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
    response = requests.post(config['face_api_endpoint'], params=params, headers=headers, data=image)
    if len(response.json()) > 0:    
        top = response.json()[0].get("faceRectangle").get("top")
        left = response.json()[0].get("faceRectangle").get("left")
        bottom = response.json()[0].get("faceRectangle").get("top") + response.json()[0].get("faceRectangle").get("height")
        right = response.json()[0].get("faceRectangle").get("left") + response.json()[0].get("faceRectangle").get("width")
        returned_image = BytesIO()
        with Image.open(BytesIO(image)) as im:
            draw = ImageDraw.Draw(im)
            draw.line([top,left,top,right,top,left,bottom,left,bottom,left,bottom,right,bottom,right,top,right], fill=(255,255,0), width=2)
            im.save(returned_image, format="jpeg")
            returned_image.seek(0)
        return base64.b64encode(returned_image.read()),"Subject appears to be a " + str(int(response.json()[0].get("faceAttributes").get("age"))) + " year old "  + response.json()[0].get("faceAttributes").get("gender") + "."
    else:
        return base64.b64encode(image), "None"


def main():
    while True:
        if discovering:
            logging.info("Discovering")
            sensors = discover()
            logging.info("Subscribing")
            subscribe(sensors)
            redis_connection.set('sensors', json.dumps(sensors))
        else:
            message = redis_pubsub.get_message()
            if message:
                if isinstance(message['data'], int):
                    logging.info("Looks like we got a delayed subscription confirmation message" + str(message))
                    continue
                event = ast.literal_eval(message['data'].decode('UTF-8'))
                logging.info("Logging a security event from sensor " + event['sensor'])
                event['captured_image'], event['notes'] = azureFaceDetection(base64.b64decode(event['captured_image']))
                event_collection.insert_one(event)

if __name__ == "__main__":
    main()