# dht22 temperature/humidity sensor in a docker container
![build](https://github.com/hvalev/dht22mqtt-homeassistant/workflows/build/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/hvalev/dht22mqtt-homeassistant)
![Docker Stars](https://img.shields.io/docker/stars/hvalev/dht22mqtt-homeassistant)
![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/hvalev/dht22mqtt-homeassistant)

This docker container enables you to use the DHT11, DHT22 or AM2302 temperature and humidity sensors with a GPIO enabled device such as raspberry pi and relay its readings to an MQTT broker. Additionally, it integrates with home assistants' [auto-discovery](https://www.home-assistant.io/docs/mqtt/discovery/) feature. Discovery automatically detects the presence of the sensor and makes it available for visualizations, automations, etc. Finally, the container implements a robust outlier detection scheme, which filters outliers before they are sent to the MQTT broker (and subsequently home assistant) resulting in clean and consistent graphs.

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
```topic``` - MQTT topic to submit to. Default: ```zigbee2mqtt```. </br>
```device_id``` - Unique identifier for the device. Default: ```dht22```. *If you have multiple, you could use something like ```bedroom_dht22```.* </br>
```broker``` - MQTT broker ip address. Default: ```192.168.1.10```. </br>
```pin``` - GPIO data pin your sensor is hooked up to. Default is ```4```. </br>
```poll``` - DHT22 sampling rate in seconds. Default is ```2```. [*For further information: DHT11/DHT22/AM2302 spec sheet.*](https://lastminuteengineers.com/dht11-dht22-arduino-tutorial/) </br> 
```device_type``` - Sensor type. Possible values are ```dht11``` or ```dht22```, which also works for AM2302. Default: ```dht22``` </br>
```unit``` - Measurement unit for temperature. Either ```C```elsius or ```F```ahrenheit. Default: ```C```. </br>
```mqtt_chatter``` - Controls how much information is relayed over to the MQTT broker. Possible *non-mutually exclusive* values are ```essential|ha|full```. Default: ```essential|ha```. </br>
&emsp;&emsp;```essential``` - Enables basic MQTT communications. </br>
&emsp;&emsp;```ha``` - Enables home assistant discovery. </br>
&emsp;&emsp;```full``` - Enables sending information about the outlier detection algorithm internals over to the MQTT broker. </br>

```logging``` - Logging strategy. Possible values are ```log2stdout|log2file```. Default is ```None```. </br>
&emsp;&emsp;```log2stdout``` - Forwards logs to stdout, inspectable through ```docker logs dht22mqtt```. </br>
&emsp;&emsp;```log2file``` - Logs temperature and humidity readings to files timestamped at containers' start. </br>

*If you end up using ```log2file```, make sure to add this volume in your docker run or docker-compose commands ```- ~/dht22mqttlog:/log``` to be able to access the logs from your host os.* </br> 
*If you want to run this container to simply record values to files with no MQTT integration, you need to explicitly set ```mqtt_chatter``` to a blank string. In that case, you can also omit all MQTT related parameters from your docker run or compose configurations.*

## Outlier detection scheme
To detect outliers, I'm using the [68–95–99.7 rule](https://en.wikipedia.org/wiki/68%E2%80%9395%E2%80%9399.7_rule), where I'm using 3 standard deviations from the mean. 
In order to have a scheme, which is adaptive to rapid changes, I'm using two [FILO](https://everythingcomputerscience.com/discrete_mathematics/Stacks_and_Queues.html) stacks of length 10 for temperature and humidity.
This allows the algorithm to adapt to gradual changes in received sensor readings, while discarding implausible ones.
Furthermore, when reading new measurements, only those which are not contained in the stack are added in, in order to prevent the stack from homogenizing.
This approach ensures that the std calculation will never return 0.
Finally, the algorithm keeps track on successive outlier detections and flushes the stack when 3 such readings are detected. This prevents the stack from fitting on outliers if we presume that we get abnormal values less than half the time. 
Then again, perhaps the temperature really is 97°C.
Most of the time, outliers detected for temperature and humidity are heavily correlated.
As such a conservative approach is implemented, where only non-outliers for both temperature and humidity and forwarded.

## Visualize your own data and/or contribute!
If you'd like visualize and check your own data (provided you have used the ```-logging=log2file``` option) to perhaps tweak the sampling rate (or stack size, if you're building it yourself), you can take a look at the ```dht22mqtt_visualize.py``` script. As long as you change the filename to your own, it will plot your data at the original sampling rate and simulate sparser ones for comparison. I'm also open to the idea of accepting pull requests with novel datasets **with interesting features** to this repository, where the outlier detection scheme fails. This can help me adapt and tune the algorithm. If you'd like to do that, please crop the part where the algorithm fails with some pre- and postamble data and avoid sending me weeks worth of temperature and humidity. Ideally, the pre- and postamble should be only a couple of hours in length. 

## Aknowledgements
The following resources have been very helpful in getting this project up and running: </br>
https://github.com/jumajumo/dht22-docker-arm/blob/master/publish.py </br>
https://forum.dexterindustries.com/t/solved-dht-sensor-occasionally-returning-spurious-values/2939/5