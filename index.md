# Watchful Pi

Watchful Pi is an internet-connected, extensible, multi-device home security system that uses Raspberry Pi SBCs, cameras, and PIR sensors for home security monitoring.

## Overview

![Device description](/docs/assets/images/devices.png)
![Process description](/docs/assets/images/process.png)

## Installation guide

This explains how to set up Watchful Pi

### Requirements

#### Hardware

- Hub device: A Raspberry Pi or Raspberry Pi Zero 2 W, no additional hardware required.
- Sensor devices: A single hub can support up to 10 sensor devices in the current implementation. Sensors must have a Raspberry Pi Camera connected on the camera port, and a passive infrared sensor connected on one of the GPIO pins. 

#### Software

The hub device requires:
- Redis installed and running locally on the hub device (https://redis.io/topics/quickstart)
- A remote MongoDB server to connect to (https://docs.mongodb.com/manual/installation/)
- Python modules: logging, socket, redis, subprocess, json, ast, requests, base64, smtplib, email, PIL/Pillow, io, dotenv, pymongo, time

The sensor devices require:
- Raspberry Pi OS Buster 32-bit for compatibility with raspicam and the picamera Python module (https://www.raspberrypi.com/software/operating-systems/)
- mjpg_streamer (https://github.com/jacksonliam/mjpg-streamer)
- Python modules: datetime, logging, redis, base64, socket, struct, subprocess, bson, io, gpiozero, picamera, time

#### Additional requirements

- The hub device must be on the same local area network as the sensor devices in order to discover them
- You must have credentials for an Azure Face API endpoint and a mailgun account (or other SMTP server)
- The watchful_hub.py program requires a .env file in the same directory, from which it will load environmental variables (MongoDB server hostname, Azure Face API endpoint URL and key, mailgun credentials)

### Instructions

1. Install the above listed software dependencies according to the linked instructions.
2. Use pip to install the above listed Python modules (`sudo apt-get install python3-pip` if not already installed)
3. Clone the Watchful Pi repository on the hub device (`git clone https://github.com/htkelly/watchfulpi.git`)
4. The repo can also be cloned on the sensor device(s), or alternatively just download or copy the watchful_sensor.py program to the sensor device(s), as this is the only code that will need to run on the sensor device (the hub device requires all the other files)
5. Create a .env file in the same directory as watchful_hub.py and populate it with the following environmental variables:
   - mongoServerHost=[MongoDB server hostname or IP]
   - subscription_key=[Subscription key for Azure Face API]
   - face_api_endpoint=[URL for Azure Face API endpoint]
   - smtpServer=[mailgun SMTP server]
   - smtpPassword=[mailgun SMTP password]
   - testEmail=[Email address to receive email alerts]
6. Connect all devices to the same local area network
7. At this point, you can run watchful_sensor.py on the sensors to bring them online, followed by hub_quickstart.sh on the hub to start the discovery process and bring the hub interface up. See the usage section for more details.
  
## Usage

Usage instructions will go here
