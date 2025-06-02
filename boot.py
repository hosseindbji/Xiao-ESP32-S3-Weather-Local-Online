# boot.py
try:
  import usocket as socket
except:
  import socket
from machine import Pin, PWM, I2C

import dht
import time
import gc
import network
gc.collect()

import esp
esp.osdebug(None)

import urequests

try :
    import ujson as json
except :
    import json
    


city='Hangzhou'
country_code='CN'

open_weather_map_api_key ='c1aef1acd53c97a5e0db512936cc6b6b'

ssid = 'CMCC-VH6T' 
password = 'XMQZY7M6' 
station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)
while station.isconnected() == False:
  pass
print('Connection successful')
print(station.ifconfig())
led = Pin(21, Pin.OUT)