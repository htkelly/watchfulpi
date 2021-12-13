#!/usr/bin/python3

import logging
import redis
from dotenv import dotenv_values
from flask import Flask, request, render_template
from flask_cors import CORS
from pymongo import MongoClient

#load config from .env file
config = dotenv_values(".env")

#enable informational logging
logging.basicConfig(level=logging.INFO)

#connect to redis
redis_broker = redis.StrictRedis(host=config["redisServerHost"], port=6379, db=0)

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

@app.route("/eventsview",methods=['GET'])
def eventsview():
    logging.info("rendering eventsview.html")
    return render_template("eventsview.html", events = event_collection.find())

@app.route("/streamview",methods=['GET'])
def streamview():
    logging.info("rendering streamview.html")
    return render_template("streamview.html")

@app.route("/stream",methods=['GET'])
def stream():
    logging.info("Changing device mode to streaming")
    redis_broker.publish('watchful_commands', 'STREAM')
    return '{"mode":"streaming"}'

@app.route("/sense",methods=['GET'])
def sense():
    logging.info("Changing device mode to sensing")
    redis_broker.publish('watchful_commands', 'SENSE')
    return '{"mode":"sensing"}'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)