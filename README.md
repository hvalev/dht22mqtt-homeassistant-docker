# dht22 temperature/humidity sensor in a docker container
![build](https://github.com/hvalev/dht22mqtt-homeassistant/workflows/build/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/hvalev/dht22mqtt-homeassistant)
![Docker Stars](https://img.shields.io/docker/stars/hvalev/dht22mqtt-homeassistant)
![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/hvalev/dht22mqtt-homeassistant)

This docker container enables you to use the DHT11, DHT22 or AM2302 temperature and humidity sensors on a GPIO enabled device such as raspberry pi. The container features a robust scheme to detect outlier and filter data in real-time. Additionally, this container can communicate with an MQTT broker and relay the sensors' values and integrates with home assistants' [auto-discovery](https://www.home-assistant.io/docs/mqtt/discovery/) protocol. Discovery will automatically detects the sensor and makes it available for visualizations, automations, etc.

## How to run it
The following docker run command or docker-compose service will get you up and running with the minimal configuration.
```docker run --device=/dev/gpiomem:/dev/gpiomem -e topic=zigbee2mqtt -e device_id=dht22 -e broker=192.168.X.X -e pin=4 hvalev/dht22mqtt-homeassistant```
```
version: "3.8"
services:
  dht22mqtt:
    image: hvalev/dht22mqtt-homeassistant
    container_name: dht22mqtt
    devices:
      - /dev/gpiomem:/dev/gpiomem
    environment:
      - topic=zigbee2mqtt
      - device_id=dht22
      - broker=192.168.X.X
      - pin=4
```
```/dev/gpiomem:/dev/gpiomem``` is required to access the GPIO and communicate with your DHT22 sensor. If it doesn't work, you can try to run the container in priviledged mode ```priviledged:true```.

## Parameters
The container offers the following configurable environment variables:</br>
| Parameter | Possible values | Description | Default |
| --------- | --------------- | ----------- | ------- |
| ```topic``` |  | MQTT topic to submit to. | ```zigbee2mqtt```  |
| ```device_id``` |  | Unique identifier for the device. \*If you have multiple, you could use something like ```bedroom_dht22```. | ```dht22``` |
| ```broker``` |  | MQTT broker ip address. | ```192.168.1.10``` |
| ```pin``` |  | GPIO data pin your sensor is hooked up to. | ```4``` |
| ```poll``` |  | Sampling rate in seconds. Recommended is the range between 2 to 30 seconds. Further information: [*DHT11/DHT22/AM2302 spec sheet.*](https://lastminuteengineers.com/dht11-dht22-arduino-tutorial/) | ```2``` |
| ```device_type``` | ```dht11``` or ```dht22``` | Sensor type. ```dht22``` also also works for AM2302 | ```dht22``` |
| ```unit``` | ```C``` or ```F``` | Measurement unit for temperature in Celsius or Fahrenheit. | ```C``` |
| ```mqtt_chatter``` | ```essential\|ha\|full``` | Controls how much information is relayed over to the MQTT broker. Possible ***non-mutually exclusive*** values are: ```essential``` - enables basic MQTT communications required to connect and transmit data to the zigbee broker; ```ha``` enables home assistant discovery protocol; ```full``` enables sending information about the outlier detection algorithm internals over to the MQTT broker. | ```essential\|ha``` |
| ```logging``` | ```log2stdout\|log2file``` | Logging strategy. Possible ***non-mutually exclusive*** values are: ```log2stdout``` - forwards logs to stdout, inspectable through ```docker logs dht22mqtt``` and ```log2file``` which logs temperature and humidity readings to files timestamped at containers' start. | ```none``` |
| ```filtering``` | ```enabled``` or ```none``` | Enables outlier filtering. Disabling this setting will transmit the raw temperature and humidity values to MQTT and(or) the log. | ```enabled``` |
----------------------------------

*If you end up using ```log2file```, make sure to add this volume in your docker run or docker-compose commands ```- ~/yourfolderpath:/log``` to be able to access the logs from your host os.* </br> 
*If you want to run this container to simply record values to files with no MQTT integration, you need to explicitly set ```mqtt_chatter``` to a blank string. In that case, you can also omit all MQTT related parameters from your docker run or compose configurations.*

## Connecting your sensor 
To connect your sensor you can look at the following pinout. Typically each sensor needs to be connected to a power, ground and data pin. The data pin needs to be indicated in the ```pin``` parameter in order to read the sensor readings.
| ![Raspberry-Pi-GPIO-Header.png](/res/Raspberry-Pi-GPIO-Header.png) | 
|:--:|
| [Image Source.](https://www.raspberrypi-spy.co.uk/2012/06/simple-guide-to-the-rpi-gpio-header-and-pins/) A depiction of the Raspberry Pi GPIO pin header. ```pin``` is the number following the GPIO label. |

## Outlier detection scheme
To detect outliers, I'm using the [68–95–99.7 rule](https://en.wikipedia.org/wiki/68%E2%80%9395%E2%80%9399.7_rule), where I'm using 3 standard deviations from the mean. 
In order to have a scheme, which is adaptive to rapid changes, I'm using two [FILO](https://everythingcomputerscience.com/discrete_mathematics/Stacks_and_Queues.html) stacks of length 10 for temperature and humidity.
This allows the algorithm to adapt to gradual changes in received sensor readings, while discarding implausible ones.
Furthermore, when reading new measurements, only those which are not contained in the stack are added in, in order to prevent the stack from homogenizing.
This approach ensures that the std calculation will never return 0.
Finally, the algorithm keeps track on successive outlier detections and flushes the stack when 3 such readings are detected. This prevents the stack from fitting on outliers if we presume that we get abnormal values less than half the time. 
Then again, perhaps the temperature really is 97°C.
Most of the time, outliers detected for temperature and humidity are heavily correlated.
As such a conservative approach is implemented, where only non-outliers for both temperature and humidity and forwarded. The following plots depict the temperature and humidity values at different sampling rates, where the first plot represents the original data and subsequent ones - simulating sparser sampling frequencies. The black vertical lines signify when the stack has been flushed.

| ![temperature.png](/plots/2021-01-30T20-08-36Z_recording_temperature.png) | ![humidity.png](/plots/2021-01-30T20-08-36Z_recording_humidity.png) | 
|:--:|:--:| 
| Temperature | Humidity |

## Visualize your own data and/or contribute!
If you'd like visualize and check your own data (provided you have used the ```-logging=log2file``` option) to perhaps tweak the sampling rate (or stack size, if you're building it yourself), you can take a look at the ```dht22mqtt_visualize.py``` script. As long as you change the filename to your own, it will plot your data at the original sampling rate and simulate sparser ones for comparison. I'm also open to the idea of accepting pull requests with novel datasets **with interesting features** to this repository, where the outlier detection scheme fails. This can help me adapt and tune the algorithm. If you'd like to do that, please crop the part where the algorithm fails with some pre- and postamble data and avoid sending me weeks worth of temperature and humidity. Ideally, the pre- and postamble should be only a couple of hours in length. 

## Aknowledgements
The following resources have been very helpful in getting this project up and running: </br>
https://github.com/jumajumo/dht22-docker-arm/blob/master/publish.py </br>
https://forum.dexterindustries.com/t/solved-dht-sensor-occasionally-returning-spurious-values/2939/5
