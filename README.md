# Radiometer for measuring fireball light intensities using an Adafruit TSL2591 digital light sensor

## Hardware
A Raspberry Pi Zero, 2, 3 or 4 running the latest release of Raspbian.
A TSL2591 light sensor with I2C data and power connectors.

There is a track on the back of the TSL2591 PCB which should be cut to disable the bright LED on the front of the board.
As the Raspberry Pi needs to be mounted close to the sensor, the LED's on the Raspberry Pi should also be switched off to remove any source of extraneous light.

### I2C Ports and Configuration
If using just one sensor, the sensor can be connected to the normal I2C SDA pin 3 and SCL pin 5 on the Pi's GPIO. The power for the sensor is connected to pin 1 (3.3V) and pin 9 (GND)

If connecting more than one sensor to one RPi, we can use the dtoverlay to assign extra I2C ports on the GPIO bus. To do this, we add the following line(s) to the /boot/config.txt file.
```
# Add extra i2c ports for pins 23 and 24 of the GPIO bus
dtoverlay=i2c-gpio,bus=3,i2c_gpio_delay_us=2,i2c_gpio_sda=23,i2c_gpio_scl=24

# Add extra i2c ports for pins 17 and 27 of the GPIO bus
dtoverlay=i2c-gpio,bus=4,i2c_gpio_delay_us=2,i2c_gpio_sda=17,i2c_gpio_scl=27
```

This assigns pins 23 (SDA) and 24 (SCL) as additional I2C ports for I2C bus 3, and pins 17 (SDA) and 27 (SCL) as additional I2C ports for I2C bus 4.
To check the additional I2C buses
```
sudo i2cdetect -l
i2c-3	i2c       	3.i2c                           	I2C adapter
i2c-1	i2c       	bcm2835 (i2c@7e804000)          	I2C adapter
i2c-4	i2c       	4.i2c                           	I2C adapter
```

To use the alternative I2C buses, use the --bus option as described in the "Running the radiometer data acquisition software" below.

More details about assigning extra I2C ports can be found at https://github.com/JJSlabbert/Raspberry_PI_i2C_conficts .


## Software
Python 3 script to continuously read and log the light intensity levels in lux detected by an Adafruit TSL2591 digital light sensor. The integration time is set to the minimum time allowed by this device (100ms), which allows light levels to be read at 10 Hz.

By default, the gain is automatically controlled and is initially set to maximum. In the event of the detector becoming saturated, the gain is changed to the medium setting, which should allow light levels to continue to be monitored up to a brightness of 3000 Lux in the event of very bright fireball events.

The gain can also be set to a fixed value using the --gain command line option.

There is also a script to monitor sky quality, by measuring the sky brightness. This uses the longest integration time available for the device (600ms), so that there are more counts detected in very dark conditions. This increased integration time should allow sky brightness measurements down to 22 mpsas.

The data is written to a dated file in the ~/radiometer_data/ directory. For example, the file R20221127.csv contains the light level data for 2022-11-27, with a timestamp for each reading. The timestamps are the times at the end of each lux reading.

## Installation
This python software requires the following additional python modules to be installed using pip for python3:
```
pip install RPi.GPIO
pip install board
pip install adafruit-extended-bus
pip install adafruit-circuitpython-tsl2591
```

For the graph and lightcurve tools, install pandas and scipy
```
pip install pandas
pip install scipy
```

If using the TCA9548A multiplexer to address more than one TSL2591 light sensor, you will also need to install the TCA9548A package
```
pip install adafruit-circuitpython-tca9548a
```

## Running the radiometer data acquisition software
```
python radiometer_tsl2591.py
```

If using additional I2C buses for 2 additional sensors e.g. I2C buses 3 and 4 as well as the default bus 1:
```
python radiometer_tsl2591.py --bus 1 --gain max --name GAIN_MAX
python radiometer_tsl2591.py --bus 3 --gain med --name GAIN_MED
python radiometer_tsl2591.py --bus 4 --gain low --name GAIN_LOW
```


If using a TCA9548A multiplexer, specify the channel number that the light sensor is connected to on the TCA9548A. For example, to run using 3 sensors at different fixed gains using a TCA9548A multiplexer:
```
python radiometer_tsl2591.py --multiplexer 0 --gain max --name GAIN_MAX
python radiometer_tsl2591.py --multiplexer 1 --gain med --name GAIN_MED
python radiometer_tsl2591.py --multiplexer 2 --gain low --name GAIN_LOW
```

## Running the sky brightness/quality data acquisition software
```
python sqm_tsl2591.py
```


## "csv" Data Format

The output data file is a space-separated file containing the date, time, lux value, visible and IR sensor raw data, sensor gain setting, and sensor integration time in milliseconds.

Note that the "Visible" and "IR" columns contain the channel 0 and channel 1 raw values from the sensors. The "Visible" data on channel 0 read from the Adafruit TSL2591 library is the counts from the visible sensor, which is sensitive to both visible and IR.
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

