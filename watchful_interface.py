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

@app.route("/",methods=['GET'])
def index():
    logging.info("rendering index.html")
    return render_template("index.html")

@app.route("/dashboard",methods=['GET'])
def dashboard():
    sensors = json.loads(redis_connection.get('sensors'))
    logging.info("found sensors " + str(sensors))
    logging.info("rendering dashboard.html")
    return render_template("dashboard.html", sensors = sensors)

@app.route("/<sensor>/eventsview",methods=['GET'])
def eventsview(sensor):
    logging.info("rendering eventsview.html")
    return render_template("eventsview.html", events = event_collection.find({"sensor": sensor}))

@app.route("/<sensor>/streamview",methods=['GET'])
def streamview(sensor):
    logging.info("rendering streamview.html")
    return render_template("streamview.html", sensor=json.loads(redis_connection.get('sensors'))[sensor])

@app.route("/api/<sensor>/stream",methods=['GET'])
def stream(sensor):
    logging.info("Changing device mode to streaming")
    redis_connection.publish('watchful_commands', sensor + ':STREAM')
    return '{"sensor":"' + sensor + '","mode":"streaming"}'

@app.route("/api/<sensor>/sense",methods=['GET'])
def sense(sensor):
    logging.info("Changing device mode to sensing")
    redis_connection.publish('watchful_commands', sensor + ':SENSE')
    return '{"sensor":"' + sensor + '","mode":"sensing"}'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)