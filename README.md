# Radiometer for measuring fireball light intensities using an Adafruit TSL2591 digital light sensor

## Hardware
A Raspberry Pi Zero or Raspberry Pi 4 running the latest release of Raspbian. The TSL2591 is connected to the power and I2C pins of the GPIO bus as described in the Adafruit manuals for the TSL2591.

## Software
Python 3 script to continuously read and log the light intensity levels in lux detected by an Adafruit TSL2591 digital light sensor. The integration time is set to the minimum time allowed by this device (100ms), which allows light levels to be read at 10 Hz. The gain is set to maximum, but in the event of the detector becoming saturated, the gain is changed to the medium setting, which should allow light levels to continue to be monitored in the event of very bright fireball events.

The data is written to a dated file in the ~/radiometer_data/ directory. For example, the file R20221127.csv contains the light level data for 2022-11-27, with a timestamp for each reading. The timestamps are the times at the end of each lux reading.

## Installation
This python software requires the following additional python modules to be installed using pip
```
pip install RPi.GPIO
pip install board
pip install adafruit-circuitpython-tsl2591
```

## Running
```
python radiometer_tsl2591.py
```

## Display the light intensity graph for a particular day
```
python graph_radiometer_data.py <data_file>
```

Example light intensity graph for a moonlit night:

![alt text](https://github.com/rabssm/Radiometer/blob/main/doc/Figure_Moon1.png)

