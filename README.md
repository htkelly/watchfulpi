# Watchful Pi

## Purpose
Watchful Pi is an internet-connected, extensible, multi-device home security system that uses Raspberry Pi SBCs, cameras, and PIR sensors for home security monitoring.

## Features
Watchful Pi sensor devices can operate in 'sensing' or 'streaming' mode. Streaming mode allows the user to view a live video stream from the device via a web interface that runs on the hub device. Sensing mode waits until motion is detected by the passive infrared sensor, then captures an image and reports the event to the hub device.

The Watchful Pi hub device can discover and control multiple sensor devices on the network. When a sensor device reports a security event to the hub, the hub logs the event in a MongoDB database, as well as sending an email alert and reaching out to the Azure Face API to check if a person is detected in the captured image. Leveraging cloud services like Azure allows our lightweight IoT solution to include computationally expensive features that would not be possible on the local device.

The Watchful Pi hub device also runs a web-based user interface, for end-user device management, event viewing, and stream viewing. The web app also exposes API endpoints that adhere to RESTful design principles. Device management in the web-based UI is implemented using a combination of client-side Javascript and the API endpoints.

## Implementation
As well as the above-mentioned hardware components, to implement this solution we utilised Redis for inter-process communication and lightweight messaging, Flask for web application functionality, MongoDB for data logging and storage, Azure Face for face detection, mjpg_streamer for video streaming, and mailgun for email alerts. The final implementation differs from our original proposal in some respects, as we opted to utilise MongoDB instead of a relational SQL database, and we chose not to use Blynk as we found it unsuitable for use with our web API. We considered the possibility that we might have been able to use only one database/data store solution (i.e., MongoDB or Redis) for both event logging and inter-process communication/messaging, and while this would have been possible, we ultimately decided that Redis was a better solution for messaging and inter-process communication, and MongoDB was more suitable as a database for the web app component of our solution, so we used both. We also leveraged a number of Python libraries.

## Further Information
The project's software dependencies are described in more detail on our project website, where we have also made an installation guide available. The project website is at https://htkelly.github.io/watchfulpi/

## References
In addition to numerous Stack Overflow answers and W3Schools tutorials, we referred to the following resources:

* Computer Systems & Networks module content (code adapted from module labs has been commented to note this)
* Database module content
* Interprocess Communication with Redis: https://www.nicholasnadeau.com/post/2018/7/interprocess-communication-with-redis-pubsub/
* Jinja documentation: https://jinja.palletsprojects.com/en/3.0.x/
* Pillow module documentation: https://pillow.readthedocs.io/en/stable/reference/
* Azure Face API documentation: https://docs.microsoft.com/en-us/rest/api/face/
