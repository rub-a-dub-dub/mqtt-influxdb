#!/usr/bin/env python

import argparse
import sys
import signal
from influxdb import *
import json
import urllib
import logging
import paho.mqtt.client as mqtt

# This holds the parsed arguments for the entire script
parserArgs = None
# This lets the message received event handler know that the DB connection is ready
dbConn = None
# This is the MQTT client object
client = None

def processArgs():
    '''This function processes command line arguments'''
    parser = argparse.ArgumentParser(description="This script will subscribe to messages from an MQTT server and store the data in an influxdb server. Messages are assumed to contain just the single value data to be saved. This script does not support connecting to SSL MQTT servers (at the moment).")
    parser.add_argument("--dbhost", help="InfluxDB server name/IP (default localhost)", default="localhost")
    parser.add_argument("--dbport", help="InfluxDB server port (default 8086)", default=8086, type=int)
    parser.add_argument("--dbuser", help="InfluxDB user name (default None)", default=None)
    parser.add_argument("--dbpwd", help="InfluxDB password (default None)", default=None)
    parser.add_argument("--dbname", help="InfluxDB database name", default="mqtt")
    parser.add_argument("--dbseries", help="InfluxDB series to store data into (default mqtt)", default="mqtt")
    parser.add_argument("--dbcolname", help="InfluxDB column name (default reading)", default="reading")
    parser.add_argument("--mqtthost", help="MQTT server name/IP (default localhost)", default="localhost")
    parser.add_argument("--mqttport", help="MQTT server port (default 1883)", type=int, default=1883)
    parser.add_argument("--mqttuser", help="MQTT user name (default None)", default=None)
    parser.add_argument("--mqttpwd", help="MQTT password (default None)", default=None)
    parser.add_argument("--mqttqos", help="MQTT QoS value (default: 0)", type=int, default=0)
    parser.add_argument("--mqttclient", help="MQTT Client ID (default: auto generated, sets clean session to false)", default=None)
    parser.add_argument("topic", help="MQTT topic to susbcribe to (required)")
    parser.add_argument("--logfile", help="If specified, will log messages to the given file (default log to terminal)", default=None)
    parser.add_argument("-v", help="Increase logging verbosity (can be used up to 5 times)", action="count", default=0)
    return parser.parse_args()

def _sigIntHandler(signum, frame):
    '''This function handles Ctrl+C for graceful shutdown of the programme'''
    logging.info("Received Ctrl+C. Exiting.")
    stopMQTT()
    stopInfluxDB()
    exit(0)

def setupLogging():
    '''Sets up logging'''
    global parserArgs
    if parserArgs.v > 5:
        verbosityLevel = 5
    else:
        verbosityLevel = parserArgs.v
    verbosityLevel = (5 - verbosityLevel)*10
    if parserArgs.logfile is not None:
        logging.basicConfig(filename=parserArgs.logfile, level=verbosityLevel, format='%(asctime)s %(message)s')
    else:
        logging.basicConfig(level=verbosityLevel, format='%(asctime)s %(message)s')

def setupSigInt():
    '''Sets up our Ctrl + C handler'''
    signal.signal(signal.SIGINT, _sigIntHandler)
    logging.debug("Installed Ctrl+C handler.")

def _mqttOnConnect(client, userdata, rc):
    '''This is the event handler for when one has connected to the MQTT broker. Will exit() if connect is not successful.'''
    global parserArgs
    if rc == 0:
        logging.info("Connected to MQTT broker successfully.")
        client.subscribe(parserArgs.topic, qos=parserArgs.mqttqos)
        startInfluxDB()
        return
    elif rc == 1:
        logging.critical("Connection to broker refused - incorrect protocol version.")
    elif rc == 2:
        logging.critical("Connection to broker refused - invalid client identifier.")
    elif rc == 3:
        logging.critical("Connection to broker refused - server unavailable.")
    elif rc == 4:
        logging.critical("Connection to broker refused - bad username or password.")
    elif rc == 5:
        logging.critical("Connection to broker refused - not authorised.")
    elif rc >=6 :
        logging.critical("Reserved code received!")
    client.close()
    exit(1)

def _mqttOnMessage(client, userdata, message):
    '''This is the event handler for a received message from the MQTT broker.'''
    logging.debug("Received message: " + str(message.payload))
    if dbConn is not None:
        sendToDB(message.payload)
    else:
        logging.warning("InfluxDB connection not yet available. Received message dropped.")

def sendToDB(payload):
    '''This function will transmit the given payload to the InfluxDB server'''
    global parserArgs
    writeData = dict()
    try:
        # first assume we have an int
        writeData["points"] = [[int(float(payload))]] 
    except ValueError:
        # okay, just store it as a string
        writeData["points"] = [[payload]]
    writeData["name"] = parserArgs.dbseries
    writeData["columns"] = [parserArgs.dbcolname]

    jsonData = json.dumps([writeData])
    try:
        dbConn.write_points(jsonData)
        logging.debug("Wrote " + jsonData + "to InfluxDB.")
    except Exception as e:
        try:
            logging.critical("Couldn't write to InfluxDB: " + e.message)
        except TypeError as e2:
            logging.critical("Couldn't write to InfluxDB.")

def startInfluxDB():
    '''This function sets up our InfluxDB connection'''
    global dbConn
    global parserArgs
    try:
        dbConn = InfluxDBClient(parserArgs.dbhost, parserArgs.dbport, parserArgs.dbuser, parserArgs.dbpwd, parserArgs.dbname)
        logging.info("Connected to InfluxDB.")
    except InfluxDBClientError as e:
        logging.critical("Could not connect to Influxdb. Message: " + e.content)
        stopMQTT()
        exit(1)
    except:
        logging.critical("Could not connect to InfluxDB.")
        stopMQTT()
        exit(1) 

def stopInfluxDB():
    '''This functions closes our InfluxDB connection'''
    dbConn = None
    logging.info("Disconnected from InfluxDB.") 

def startMQTT():
    '''This function starts the MQTT connection and listens for messages'''
    global client
    if parserArgs.mqttclient is not None:
        client = mqtt.Client(parserArgs.mqttclient, clean_session=False)
    else:
        client = mqtt.Client()
    client.on_connect = _mqttOnConnect
    client.on_message = _mqttOnMessage
    if parserArgs.mqttuser is not None:
        client.username_pw_set(parserArgs.mqttuser, parserArgs.mqttpwd)
    client.connect(parserArgs.mqtthost, parserArgs.mqttport, 60)
    #client.loop_start()

def stopMQTT():
    '''This function stops the MQTT client service'''
    global client
    if client is not None:
        #client.loop_stop()
        client.disconnect()
        logging.info("Disconnected from MQTT broker.")
        client = None
    else:
        logging.warning("Attempting to disconnect without first connecting to MQTT broker.")

def main():
    # Process our command line arguments first
    global parserArgs
    parserArgs = processArgs()

    # Now setup logging
    setupLogging()

    # Setup our interrupt handler
    setupSigInt()

    # Open up a connection to our MQTT server and subscribe
    startMQTT()

    # Stay here forever
    global client
    while True:
        client.loop()

    # Got here somehow? Okay, clean-up and exit.
    stopInfluxDB()
    stopMQTT()

if __name__ == "__main__":
    main()