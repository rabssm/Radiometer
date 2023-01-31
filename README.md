# Radiometer for measuring fireball light intensities using an Adafruit TSL2591 digital light sensor

## Hardware
A Raspberry Pi Zero or Raspberry Pi 4 running the latest release of Raspbian. The TSL2591 is connected to the power and I2C pins of the GPIO bus as described in the Adafruit manuals for the TSL2591.

There is a track on the back of the TSL2591 PCB which should be cut to disable the bright LED on the front of the board.
As the Raspberry Pi needs to be mounted close to the sensor, the LED's on the Raspberry Pi should also be switched off to remove any source of extraneous light.

## Software
Python 3 script to continuously read and log the light intensity levels in lux detected by an Adafruit TSL2591 digital light sensor. The integration time is set to the minimum time allowed by this device (100ms), which allows light levels to be read at 10 Hz. The gain is set to maximum, but in the event of the detector becoming saturated, the gain is changed to the medium setting, which should allow light levels to continue to be monitored in the event of very bright fireball events.

There is also a script to monitor sky quality, by measuring the sky brightness. This uses the longest integration time available for the device (600ms), so that there are more counts detected in very dark conditions. This increased integration time should allow sky brightness measurements down to 22 mpsas.

The data is written to a dated file in the ~/radiometer_data/ directory. For example, the file R20221127.csv contains the light level data for 2022-11-27, with a timestamp for each reading. The timestamps are the times at the end of each lux reading.

## Installation
This python software requires the following additional python modules to be installed using pip
```
pip install RPi.GPIO
pip install board
pip install adafruit-circuitpython-tsl2591
```

If using the TCA9548A multiplexer to address more than one TSL2591 light sensor, you will also need to install the TCA9548A package
```
pip install adafruit-circuitpython-tca9548a
```

## Running the radiometer data acquisition software
```
python radiometer_tsl2591.py
```

If using a TCA9548A multiplexer, specify the channel number that the light sensor is connected to on the TCA9548A e.g.
```
python radiometer_tsl2591.py --multiplexer 0 --name MULTI0
```

## Running the sky brightness/quality data acquisition software
```
python sqm_tsl2591.py
```


## "csv" Data Format

The output data file is a space-separated file containing the date, time, lux value, visible and IR sensor raw data, sensor gain setting, and sensor integration time in milliseconds.

Note that the "Visible" and "IR" columns contain the channel 0 and channel 1 raw values from the sensors. The "Visible" data on channel 0 read from the Adafruit TSL2591 library is actually the sum of the counts from both the visible and IR sensors.
```
              Date          Time          Lux  Visible    IR    Gain  IntTime
0       2022/12/24  00:00:02.630     0.002661       13     4  9876.0    100.0
1       2022/12/24  00:00:02.758     0.001570       12     5  9876.0    100.0
2       2022/12/24  00:00:03.017     0.001157       11     5  9876.0    100.0
3       2022/12/24  00:00:03.119     0.002396       14     5  9876.0    100.0
4       2022/12/24  00:00:03.416     0.001570       12     5  9876.0    100.0
```

## Display the light intensity, sky brightness and raw data graphs for a particular day/night
```
python graph_radiometer_data.py <data_file>
```

Example light intensity graph for a clear moonlit night:

![alt text](https://github.com/rabssm/Radiometer/blob/main/doc/Figure_Moon1.png)

