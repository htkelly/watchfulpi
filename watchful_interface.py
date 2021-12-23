#!/usr/bin/python3

import logging
import redis
import json
from dotenv import dotenv_values
from flask import Flask, request, render_template
from flask_cors import CORS
from pymongo import MongoClient

#load config from .env file
config = dotenv_values(".env")

#enable informational logging
logging.basicConfig(level=logging.INFO)

#connect to redis
redis_connection = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)

#connect to database
client = MongoClient(config["mongoServerHost"], 27017)
db = client.watchfulpi
event_collection = db.security_events

#create Flask app and allow cross-origin resource sharing
app = Flask(__name__)
CORS(app)

#Render the index/landing page
@app.route("/",methods=['GET'])
def index():
    logging.info("rendering index.html")
    return render_template("index.html")

#Render the dashboard
@app.route("/dashboard",methods=['GET'])
def dashboard():
    logging.info("rendering dashboard.html")
    return render_template("dashboard.html")

#Render the events view page for <sensor> (uses the sensor id to pull the results from the correct sensor from MongoDB)
@app.route("/<sensor>/eventsview",methods=['GET'])
def eventsView(sensor):
    logging.info("rendering eventsview.html")
    return render_template("eventsview.html", sensor=sensor, events = event_collection.find({"sensor": sensor}))

#Render the streamview page for <sensor> (uses the sensor id to pull the sensor's IP address from Redis, which is then passed into the html template)
@app.route("/<sensor>/streamview",methods=['GET'])
def streamView(sensor):
    logging.info("rendering streamview.html")
    return render_template("streamview.html", sensor=sensor, ip=json.loads(redis_connection.get('sensors'))[sensor])

#API endpoint to return a JSON object with all sensor devices and their ip addresses and current modes (this is called by an XMLHttpRequest in client-side javascript to populate the dashboard page)
#GET returns the JSON object, POST is used to update mode for all devices (this is done by publishing a message on Redis) and also returns the JSON object
@app.route("/api/sensor/all", methods=['GET', 'POST'])
def allSensors():
    sensors = json.loads(redis_connection.get('sensors'))
    if request.method == 'GET':
        logging.info("Getting all sensors, their IPs, and modes")
        if len(sensors) == 0:
            response = "{}"
        else:
            response = '{"sensors":{'
            for sensor_id, ip in sensors.items():
                response += '"' + sensor_id + '":{"ip":"' + ip + '","mode":"' +  redis_connection.get(sensor_id).decode('UTF-8') + '"},'
            response = response[:-1] #remove trailing comma for valid JSON
            response += "}}"
        return response
    elif request.method == 'POST':
        new_mode = request.args.get('mode')
        logging.info("Command received: " + new_mode)
        if len(sensors) == 0:
            response = "{}"
        if new_mode not in ['0','1','2']:
            response = '{"sensors":{'
            for sensor_id, ip in sensors.items():
                response += '"' + sensor_id + '":{"ip":"' + ip + '","mode":"' +  new_mode + '"},'
            response = response[:-1] #remove trailing comma for valid JSON
            response += "}}"
        else:
            redis_connection.publish('watchful_commands', 'all' + ':' + new_mode)
            response = '{"sensors":{'
            for sensor_id, ip in sensors.items():
                response += '"' + sensor_id + '":{"ip":"' + ip + '","mode":"' +  new_mode + '"},'
            response = response[:-1] #remove trailing comma for valid JSON
            response += "}}"
        return response

#API endpoint to return a JSON object with details for a specific sensor device
#GET returns the JSON object, POST updates the device mode (this is done by publishing a message on Redis) and also returns the JSON object 
@app.route("/api/sensor/<sensor_id>",methods=['GET', 'POST'])
def oneSensor(sensor_id):
    sensors = json.loads(redis_connection.get('sensors'))
    if request.method == 'GET':
        logging.info("Getting sensor mode and ip")
        sensor_ip = sensors[sensor_id]
        sensor_mode = redis_connection.get(sensor_id).decode('UTF-8')
        return '{"' + sensor_id + '":{"ip":"' + sensor_ip + '","mode":"' + sensor_mode + '"}}'
    elif request.method == 'POST':
        sensor_ip = sensors[sensor_id]
        sensor_mode = redis_connection.get(sensor_id).decode('UTF-8')
        new_mode = request.args.get('mode')
        logging.info("Command received: " + new_mode)
        if new_mode not in ['0','1','2']:
            return '{"' + sensor_id + '":{"ip":"' + sensor_ip + '","mode":"' + sensor_mode + '"}}'
        else:
            redis_connection.publish('watchful_commands', sensor_id + ':' + new_mode)
            return '{"' + sensor_id + '":{"ip":"' + sensor_ip + '","mode":"' + new_mode + '"}}'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)