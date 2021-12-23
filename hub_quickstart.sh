#!/bin/bash

# Start the hub program in background mode
./watchful_hub.py &

#Wait 20 seconds (the maximum amount of time discovery could take with current settings)
sleep 20

#Start the Flask web interface/API app
./watchful_interface.py