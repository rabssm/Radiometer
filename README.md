# Radiometer for measuring fireball light intensities using an Adafruit TSL2591 digital light sensor

## Hardware
A Raspberry Pi Zero, 2, 3 or 4 running Raspbian Bookworm.

A TSL2591 light sensor with I2C data and power connectors.

There is a track on the back of the TSL2591 PCB which should be cut to disable the bright LED on the front of the board.
As the Raspberry Pi needs to be mounted close to the sensor, the LED's on the Raspberry Pi should also be switched off to remove any source of extraneous light.

### I2C Ports and Configuration
If using just one sensor, the sensor can be connected to the normal I2C SDA GPIO 2 (pin 3) and SCL GPIO 3 (pin 5) on the Pi's GPIO. The power for the sensor is connected to pin 1 (3.3V) and pin 9 (GND). See https://learn.adafruit.com/assets/95248

Note: Use 'sudo raspi-config' to enable I2C on the raspberry pi.

If connecting more than one sensor to one RPi, we can use the dtoverlay to assign extra I2C ports on the GPIO bus. To do this, we add the following line(s) to the /boot/config.txt file.
```
# Add extra i2c ports for GPIO pins 23 and 24 of the GPIO bus
dtoverlay=i2c-gpio,bus=3,i2c_gpio_delay_us=2,i2c_gpio_sda=23,i2c_gpio_scl=24

# Add extra i2c ports for GPIO pins 17 and 27 of the GPIO bus
dtoverlay=i2c-gpio,bus=4,i2c_gpio_delay_us=2,i2c_gpio_sda=17,i2c_gpio_scl=27
```

This assigns GPIO 23 (pin 16) SDA and GPIO 24 (pin 18) SCL as additional I2C ports for I2C bus 3, and GPIO 17 (pin 11) SDA and GPIO 27 (pin 13) SCL as additional I2C ports for I2C bus 4.
To check the additional I2C buses
```
sudo i2cdetect -l
i2c-3	i2c       	3.i2c                           	I2C adapter
i2c-1	i2c       	bcm2835 (i2c@7e804000)          	I2C adapter
i2c-4	i2c       	4.i2c                           	I2C adapter
```

To check that the TSL2591 is available on a bus e.g. bus 1:
```
sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- 29 -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- -- --                         

```
This should display the I2C address of the attached TSL2591, which should be 29.

Add your user to the i2c and gpio groups:
```
sudo usermod -a -G gpio,i2c $USER
```

To use the additional/alternative I2C buses, use the --bus option as described in the "Running the radiometer data acquisition software" below.

More details about assigning extra I2C ports can be found at https://github.com/JJSlabbert/Raspberry_PI_i2C_conficts .


## Software
Python 3 script to continuously read and log the light intensity levels in lux detected by an Adafruit TSL2591 digital light sensor. The integration time is set to the minimum time allowed by this device (100ms), which allows light levels to be read at 10 Hz.

### Gain Settings
By default, the gain is automatically controlled and is initially set to maximum. In the event of the detector becoming saturated, the gain is changed to the medium setting, which should allow light levels to continue to be monitored up to a brightness of 3000 Lux in the event of very bright fireball events. The downside of the auto gain setting is that there will be a gap of 200 ms between valid readings during the period when the detector was saturated and while the gain is changed.

The gain can also be set to a fixed value using the --gain command line option.

### Sky Quality Metering
There is also a script to monitor sky quality, by measuring the sky brightness. This uses the longest integration time available for the device (600ms), so that there are more counts detected in very dark conditions. This increased integration time should allow sky brightness measurements down to 22 mpsas.

## Installation

Firstly clone this repository to your computer:
```
git clone https://github.com/rabssm/Radiometer.git
```

This python software requires the following additional python modules to be installed using pip for python3. These can all be installed using the requirements.txt file e.g.
```
pip install -r requirements.txt
```

Alternatively, install the packages individually:
```
pip install RPi.GPIO
pip install board
pip install adafruit-extended-bus
pip install adafruit-circuitpython-tsl2591
pip install flask    # For the REST API
```

For the graph and lightcurve tools, install pandas, scipy and matplotlib
```
pip install pandas
pip install scipy
pip install matplotlib
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

## Starting the radiometer data acquisition software on each reboot

To get the lux meter to run on every reboot, add the following to your cron tasks using 'crontab -e'
```
@reboot sleep 60 && /usr/bin/python3 ~/source/Radiometer/src/radiometer_tsl2591.py 2>&1 | /usr/bin/logger -t radiometer_tsl2591.py
 
```
You may need to change the path to the python3 you are using, the path to the radiometer_tsl2591.py script, and add any command line options needed for additional sensors.


## Running the sky brightness/quality data acquisition software
```
python sqm_tsl2591.py
```

## Running the Solar Scintillation Seeing Monitor software

This software acquires data all day and logs lux data in the same format as the sqm and radiometer scripts. The most recent seeing value in arcseconds is presented in the file '/tmp/sssm_tsl2591.txt'.
```
python sssm_tsl2591.py

# Show graph of the Solar Scintillation Seeing data with a rolling average of 60 seconds
python graph_radiometer_data.py --seeing 60 <csv_data_file>
```


## Data Output
The data is written to a dated file in the ~/radiometer_data/ directory. For example, the file R20221127.csv contains the light level data for 2022-11-27, with a timestamp for each reading. The timestamps are the times at the end of each lux reading.

### "csv" Data Format
The output data file is a space-separated file containing the date, time, lux value, visible and IR sensor raw data, sensor gain setting, and sensor integration time in milliseconds.

Note that the "Visible" and "IR" columns contain the channel 0 and channel 1 raw values from the sensors. The "Visible" data on channel 0 read from the Adafruit TSL2591 library is the counts from the "visible" sensor, which is sensitive to both visible and IR. To obtain a Lux reading a proportion of the IR sensor reading is subtracted from the visible+IR sensor reading. The raw data values for each sensor are provided to allow a user to calibrate their device and tailor their own equations for conversion to sky brightness or seeing values.
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
python graph_radiometer_data.py <csv_data_file>
```

Example light intensity graph for a clear moonlit night:

![alt text](https://github.com/rabssm/Radiometer/blob/main/doc/Figure_Moon1.png)

