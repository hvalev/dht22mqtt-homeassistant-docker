#!/usr/bin/python3
from datetime import datetime
import time
import os
import statistics
import csv
import adafruit_dht
# import RPi.GPIO as GPIO
from gpiomapping import gpiomapping
import paho.mqtt.client as mqtt

# Begin
dht22mqtt_start_ts = datetime.now()

###############
# MQTT Params
###############
mqtt_topic = os.getenv('topic', 'zigbee2mqtt/')
mqtt_device_id = os.getenv('device_id', 'dht22')
mqtt_brokeraddr = os.getenv('broker', '192.168.1.10')
if not mqtt_topic.endswith('/'):
    mqtt_topic = mqtt_topic + "/"
mqtt_topic = mqtt_topic + mqtt_device_id + '/'

###############
# GPIO params
###############
# TODO check if we can use the GPIO test https://github.com/kgbplus/gpiotest to autodetect pin
# Problems with multiple sensors on the same device
dht22mqtt_refresh = int(os.getenv('poll', '2'))
dht22mqtt_pin = int(os.getenv('pin', '4'))
dht22mqtt_device_type = str(os.getenv('device_type', 'dht22')).lower()
dht22mqtt_temp_unit = os.getenv('unit', 'C')

###############
# MQTT & Logging params
###############
dht22mqtt_mqtt_chatter = str(os.getenv('mqtt_chatter', 'essential|ha|full')).lower()
dht22mqtt_logging_mode = str(os.getenv('logging', 'None')).lower()
dht22mqtt_sensor_tally = dict()

###############
# Filtering & Sampling Params
###############
dht22_temp_stack = []
dht22_temp_stack_errors = 0
dht22_hum_stack = []
dht22_hum_stack_errors = 0

dht22_stack_size = 10
dht22_std_deviation = 3
dht22_error_count_stack_flush = 3


###############
# Logging functions
###############
def log2file(filename, params):
    if('log2file' in dht22mqtt_logging_mode):
        ts_filename = dht22mqtt_start_ts.strftime('%Y-%m-%dT%H-%M-%SZ')+'_'+filename+".csv"
        with open("/log/"+ts_filename, "a+") as file:
            w = csv.DictWriter(file, delimiter=',', lineterminator='\n', fieldnames=params.keys())
            if file.tell() == 0:
                w.writeheader()
            w.writerow(params)


def log2stdout(timestamp, msg):
    if('log2stdout' in dht22mqtt_logging_mode):
        print(datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%SZ'), str(msg))


###############
# Polling & Processing functions
###############
def getTemperatureJitter(temperature):
    return getTemperature(temperature-0.3), getTemperature(temperature+0.3)


def getTemperature(temperature):
    if(dht22mqtt_temp_unit == 'F'):
        temperature = temperature * (9 / 5) + 32
    return temperature


def getHumidity(humidity):
    return humidity


###############
# Polling & Processing functions
###############
def processSensorValue(stack, error, value, value_type):
    # flush stack on accumulation of errors
    if(error >= dht22_error_count_stack_flush):
        stack = []
        error = 0

    # init stack
    if(len(stack) <= dht22_error_count_stack_flush):
        if(value not in stack):
            stack.append(value)
        # use jitter for bootstrap temperature stack
        if(value_type == 'temperature'):
            low, high = getTemperatureJitter(value)
            stack.append(low)
            stack.append(high)
        return stack, error, None

    # get statistics
    std = statistics.pstdev(stack)
    mean = statistics.mean(stack)

    # compute if outlier or not
    if(mean-std*dht22_std_deviation < value < mean+std*dht22_std_deviation):
        outlier = False
        if(value not in stack):
            stack.append(value)
        error = 0
    else:
        outlier = True
        error += 1

    # remove last element from stack
    if(len(stack) > 10):
        stack.pop(0)
    return stack, error, outlier


###############
# MQTT update functions
###############
def updateEssentialMqtt(temperature, humidity, detected):
    if('essential' in dht22mqtt_mqtt_chatter):
        if(detected == 'accurate'):
            payload = '{ "temperature": '+str(temperature)+', "humidity": '+str(humidity)+' }'
            client.publish(mqtt_topic + 'value', payload, qos=1, retain=True)
            client.publish(mqtt_topic + "detected", str(detected), qos=1, retain=True)
        else:
            client.publish(mqtt_topic + "detected", str(detected), qos=1, retain=True)
        client.publish(mqtt_topic + "updated", str(datetime.now()), qos=1, retain=True)


def registerWithHomeAssitant():
    if('ha' in dht22mqtt_mqtt_chatter):
        ha_temperature_config = '{"device_class": "temperature",' + \
                                ' "name": "'+mqtt_device_id+'_temperature",' + \
                                ' "state_topic": "'+mqtt_topic+'value",' + \
                                ' "unit_of_measurement": "°'+dht22mqtt_temp_unit+'",' + \
                                ' "value_template": "{{ value_json.temperature}}" }'
        ha_humidity_config = '{"device_class": "humidity",' + \
                             ' "name": "'+mqtt_device_id+'_humidity",' + \
                             ' "state_topic": "'+mqtt_topic+'value",' + \
                             ' "unit_of_measurement": "%",' + \
                             ' "value_template": "{{ value_json.humidity}}" }'
        client.publish('homeassistant/sensor/'+mqtt_device_id+'Temperature/config', ha_temperature_config, qos=1, retain=True)
        client.publish('homeassistant/sensor/'+mqtt_device_id+'Humidity/config', ha_humidity_config, qos=1, retain=True)
        log2stdout(datetime.now().timestamp(), 'Registering sensor with home assistant success...')


def updateFullSysInternalsMqtt():
    if('full' in dht22mqtt_mqtt_chatter):
        client.publish(mqtt_topic + "sys/temperature_stack_size", len(dht22_temp_stack), qos=1, retain=True)
        client.publish(mqtt_topic + "sys/temperature_error_count", dht22_temp_stack_errors, qos=1, retain=True)
        client.publish(mqtt_topic + "sys/humidity_stack_size", len(dht22_hum_stack), qos=1, retain=True)
        client.publish(mqtt_topic + "sys/humidity_error_count", dht22_hum_stack_errors, qos=1, retain=True)
        client.publish(mqtt_topic + "updated", str(datetime.now()), qos=1, retain=True)


def updateFullSensorTallyMqtt(key):
    if('full' in dht22mqtt_mqtt_chatter):
        if key in dht22mqtt_sensor_tally:
            dht22mqtt_sensor_tally[key] += 1
        else:
            dht22mqtt_sensor_tally[key] = 1
        client.publish(mqtt_topic + "sys/tally/" + key, dht22mqtt_sensor_tally[key], qos=1, retain=True)
        client.publish(mqtt_topic + "updated", str(datetime.now()), qos=1, retain=True)


###############
# Setup dht22 sensor
###############
log2stdout(dht22mqtt_start_ts.timestamp(), 'Starting dht22mqtt...')
if(dht22mqtt_device_type == 'dht22' or dht22mqtt_device_type == 'am2302'):
    dhtDevice = adafruit_dht.DHT22(gpiomapping[dht22mqtt_pin], use_pulseio=False)
elif(dht22mqtt_device_type == 'dht11'):
    dhtDevice = adafruit_dht.DHT11(gpiomapping[dht22mqtt_pin], use_pulseio=False)
else:
    log2stdout(datetime.now().timestamp(), 'Unsupported device '+dht22mqtt_device_type+'...')
    log2stdout(datetime.now().timestamp(), 'Devices supported by this container are DHT11/DHT22/AM2302')

log2stdout(datetime.now().timestamp(), 'Setup dht22 sensor success...')

###############
# Setup mqtt client
###############
if('essential' in dht22mqtt_mqtt_chatter):
    client = mqtt.Client('DHT22', clean_session=True, userdata=None)

    # set last will for a disgraceful exit
    client.will_set(mqtt_topic + "state", "OFFLINE", qos=1, retain=True)

    # keep alive for 60 times the refresh rate
    client.connect(mqtt_brokeraddr, keepalive=dht22mqtt_refresh*60)

    client.loop_start()

    client.publish(mqtt_topic + "type", "sensor", qos=1, retain=True)
    client.publish(mqtt_topic + "device", "dht22", qos=1, retain=True)

    client.publish(mqtt_topic + "env/pin", dht22mqtt_pin, qos=1, retain=True)
    client.publish(mqtt_topic + "env/brokeraddr", mqtt_brokeraddr, qos=1, retain=True)
    client.publish(mqtt_topic + "env/refresh", dht22mqtt_refresh, qos=1, retain=True)
    client.publish(mqtt_topic + "env/logging", dht22mqtt_logging_mode, qos=1, retain=True)
    client.publish(mqtt_topic + "env/mqtt_chatter", dht22mqtt_mqtt_chatter, qos=1, retain=True)

    client.publish(mqtt_topic + "sys/dht22_stack_size", dht22_stack_size, qos=1, retain=True)
    client.publish(mqtt_topic + "sys/dht22_std_deviation", dht22_std_deviation, qos=1, retain=True)
    client.publish(mqtt_topic + "sys/dht22_error_count_stack_flush", dht22_error_count_stack_flush, qos=1, retain=True)

    client.publish(mqtt_topic + "updated", str(datetime.now()), qos=1, retain=True)

    log2stdout(datetime.now().timestamp(), 'Setup mqtt client success...')

    client.publish(mqtt_topic + "state", "ONLINE", qos=1, retain=True)

    registerWithHomeAssitant()

log2stdout(datetime.now().timestamp(), 'Begin capture...')


while True:
    try:
        dht22_ts = datetime.now().timestamp()
        temperature = getTemperature(dhtDevice.temperature)
        humidity = getHumidity(dhtDevice.humidity)

        temp_data = processSensorValue(dht22_temp_stack,
                                       dht22_temp_stack_errors,
                                       temperature,
                                       'temperature')
        dht22_temp_stack = temp_data[0]
        dht22_temp_stack_errors = temp_data[1]
        temperature_outlier = temp_data[2]

        hum_data = processSensorValue(dht22_hum_stack,
                                      dht22_hum_stack_errors,
                                      humidity,
                                      'humidity')
        dht22_hum_stack = hum_data[0]
        dht22_hum_stack_errors = hum_data[1]
        humidity_outlier = hum_data[2]

        # Since the intuition here is that errors in humidity and temperature readings
        # are heavily correlated, we can skip mqtt if we detect either.
        detected = ''
        if(temperature_outlier is False and humidity_outlier is False):
            detected = 'accurate'
        else:
            detected = 'outlier'

        updateEssentialMqtt(temperature, humidity, detected)
        updateFullSysInternalsMqtt()
        updateFullSensorTallyMqtt(detected)

        data = {'timestamp': dht22_ts,
                'temperature': temperature,
                'humidity': humidity,
                'temperature_outlier': temperature_outlier,
                'humidity_outlier': humidity_outlier}
        log2stdout(dht22_ts, data)
        log2file('recording', data)

        time.sleep(dht22mqtt_refresh)

    except RuntimeError as error:
        # DHT22 throws errors often. Keep reading.
        detected = 'error'
        updateEssentialMqtt(None, None, detected)
        updateFullSensorTallyMqtt(error.args[0])

        data = {'timestamp': dht22_ts, 'error_type': error.args[0]}
        log2stdout(dht22_ts, data)
        log2file('error', data)

        time.sleep(dht22mqtt_refresh)
        continue

    except Exception as error:
        if('essential' in dht22mqtt_mqtt_chatter):
            client.disconnect()
        dhtDevice.exit()
        raise error

# Graceful exit
if('essential' in dht22mqtt_mqtt_chatter):
    client.publish(mqtt_topic + "state", "OFFLINE", qos=2, retain=True)
    client.publish(mqtt_topic + "updated", str(datetime.now()), qos=2, retain=True)
    client.disconnect()
dhtDevice.exit()
