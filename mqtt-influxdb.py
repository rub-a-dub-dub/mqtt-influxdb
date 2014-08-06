#!/usr/bin/env python

import argparse
import sys
import signal
import influxdb
import json
import urllib

def processArgs():
    '''This function processes command line arguments'''
    parser = argparse.ArgumentParser(description="This script will subscribe to messages from an MQTT server and store the data in an influxdb server. Messages are assumed to contain just the single value data to be saved. This script does not support connecting to SSL MQTT servers (at the moment).")
    parser.add_argument("--dbhost", help="InfluxDB server name/IP (default localhost)", default="localhost")
    parser.add_argument("--dbport", help="InfluxDB server port (default 8086)", default=8086, type=int)
    parser.add_argument("--dbuser", help="InfluxDB user name (default None)", default=None)
    parser.add_argument("--dbpwd", help="InfluxDB password (default None)", default=None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dbhttp", help="Uses http to connect to InfluxDB (default)", action="store_true", default=True)
    group.add_argument("--dbhttps", help="Uses https to connect to InfluxDB", action="store_true")
    parser.add_argument("--db", help="InfluxDB database name", default="mqtt")
    parser.add_argument("--series", help="InfluxDB series to store data into (default mqtt)", default="mqtt")
    parser.add_argument("--colname", help="InfluxDB column name (default reading)", default="reading")
    parser.add_argument("--topic", help="MQTT topic to susbcribe to (default #)", default="#")
    parser.add_argument("--mqtthost", help="MQTT server name/IP (default localhost)", default="localhost")
    parser.add_argument("--mqttport", help="MQTT server port (default 1883)", type=int, default=1883)
    parser.add_argument("--mqttuser", help="MQTT user name (default None)", default=None)
    parser.add_argument("--mqttpwd", help="MQTT password (default None)", default=None)
    return parser.parse_args()

def main():
    processArgs()

if __name__ == "__main__":
    main()