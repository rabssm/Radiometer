import argparse
import datetime
import os
import signal
import threading
import time
import numpy as np
from collections import deque
import syslog
try:
    from flask import Flask, jsonify
except:
    pass
import board
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_tsl2591

from radiometer_tsl2591 import adafruit_tsl2591_extended


DATA_DIR = os.path.expanduser('~/radiometer_data/')
SQM_FILE = '/tmp/sqm_tsl2591.txt'

# Minimum time to wait after a sensor time or gain setting
GUARD_TIME = 0.12

# The tsl2591 default i2c address is 0x29
DEFAULT_I2C_ADDRESS = adafruit_tsl2591._TSL2591_ADDR


def signalHandler(signum, frame):
    # Handle process signals
    os._exit(0)


def reset_sensor(sensor, gain, integration_time):
    # Sensor reset
    if verbose:
        print("Resetting sensor")
    # sensor.disable()
    sensor.reset()
    sensor.gain = gain
    sensor.enable()
    sensor.integration_time = integration_time
    # Wait for next interrupt
    sensor.wait_interrupt_600()


class Sqm_Writer():
    def __init__(self):
        self.rolling = deque(maxlen=10)


    def update(self, sky_brightness):
        # Take a rolling average over last 10 measurements (6s) and write it to /tmp/sqm_tsl2591.txt

        self.rolling.append(sky_brightness)
        rolling_average = np.average(self.rolling)

        with open(SQM_FILE, 'w') as sqm_file:
            sqm_file.write(str(rolling_average) + "\n")

        return


# Class to run a REST API
class FlaskServer(threading.Thread):
    def __init__(self, device_name='SQM'):
        self.device_name = device_name
        self.rolling = deque(maxlen=10)
        self.readings = [{'time_stamp': '', 'sky_brightness': '', 'lux': '', 'vis_level': '', 'ir_level': '', 'again': '', 'atime': ''}]

        # Initialise the thread
        threading.Thread.__init__(self)

    def run(self):
        try:
            app = Flask(__name__)
            @app.route('/' + self.device_name, methods=['GET'])
            def get_data():
                return jsonify({self.device_name: self.readings})

            print("REST service running on:", self.device_name)
            app.run(host='0.0.0.0', port=5000) # debug=True)
        except:
            print("Unable to start flask REST server")

    def set_data(self, time_stamp, lux, vis_level, ir_level, again, atime):
        # Take a rolling average of the sky brightness over last 10 measurements (6s)
        sky_brightness = np.log10(lux/108000)/-0.4
        self.rolling.append(sky_brightness)
        sky_brighness_rolling_average = np.average(self.rolling)

        # Publish the readings
        self.readings = [{'time_stamp': time_stamp, 'sky_brightness': sky_brighness_rolling_average, 'lux': lux, 'vis_level': vis_level, 'ir_level': ir_level, 'again': again, 'atime': atime}]


# Class for logging detections to radiometer data file
class RadiometerDataLogger():

    def __init__(self, name=""):
        self.name = name
        if name:
            self.name = "_" + name + "_"
        # Make the data logging directory
        os.makedirs(DATA_DIR, exist_ok=True)

        # Set the filename and open it for appending
        self.filename = "R" + self.name + \
            datetime.datetime.now().strftime("%Y%m%d") + ".csv"
        if verbose:
            print("Writing data to file:", DATA_DIR + self.filename)
        self.rmfile = open(DATA_DIR + self.filename, "a")

        # Start a thread to periodically flush the data to disk
        self.flush_thread = threading.Thread(target=self.flush_file)
        self.flush_thread.start()

    # Log the date/time and lux reading
    def log_data(self, obs_time, lux_value, vis_level, ir_level, again, atime):
        # Check for date change
        try:
            filename = "R" + self.name + obs_time.strftime("%Y%m%d") + ".csv"
            if filename != self.filename:
                self.rmfile.close()
                self.filename = filename
                self.rmfile = open(DATA_DIR + self.filename, "a")

            # Log the data
            out_string = '{0:s} {1:.9f} {2:d} {3:d} {4:.1f} {5:.1f}\n'.format(obs_time.strftime(
                "%Y/%m/%d %H:%M:%S.%f")[:-3], lux_value, vis_level, ir_level, again, atime)
            self.rmfile.write(out_string)
            if verbose:
                print(out_string, end='')

        except Exception as e:
            print(e)

    # Flush the data log file to disk every 10s
    def flush_file(self):
        while True:
            time.sleep(10)
            try:
                self.rmfile.flush()
            except:
                pass


# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Acquire light levels')
    ap.add_argument("-a", "--address", type=lambda x: int(x, 0), default=DEFAULT_I2C_ADDRESS,
                    help="Set the light sensor's i2c address. Default is " + hex(DEFAULT_I2C_ADDRESS))
    ap.add_argument("-b", "--bus", type=int, default=1,
                    help="Specify the i2c bus used for connecting the sensor e.g. 3 if /dev/i2c-3 has been created using dtoverlay. Default is bus 1")
    gain_choices = ["max", "high", "med", "low", "auto"]
    ap.add_argument(
        "-g", "--gain", choices=gain_choices, type=str, default="auto", help="Gain level for the light sensor. Default is auto")
    ap.add_argument("-m", "--multiplexer", type=int, default=None,
                    help="Connect to the i2c sensor via an adafruit TCA9548A multiplexer using the number of the multiplexer channel e.g. 0-7")
    ap.add_argument("-n", "--name", type=str, default="SQM",
                    help="Optional name of the sensor for the output file name. Default is SQM")
    ap.add_argument("-v", "--verbose", action='store_true',
                    help="Verbose output to terminal")
    args = vars(ap.parse_args())

    i2c_address = args['address']
    i2c_bus = args['bus']
    gain_name = args['gain']
    device_name = args['name']
    multiplexer = args['multiplexer']
    verbose = args['verbose']

    # Get the TSL2591 gain from the command line string. If the gain is set to auto, set the gain to maximum
    valid_device_gain_settings = [adafruit_tsl2591.GAIN_MAX,
                                  adafruit_tsl2591.GAIN_HIGH, adafruit_tsl2591.GAIN_MED, adafruit_tsl2591.GAIN_LOW, adafruit_tsl2591.GAIN_MAX]
    required_device_gain_setting = valid_device_gain_settings[gain_choices.index(
        gain_name)]
    auto_gain = True if gain_name == "auto" else False

    # Handle termination signals gracefully
    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGTERM, signalHandler)

    # Open the i2c bus
    i2c = I2C(i2c_bus)

    # Create the sensor or TCA9548A object and pass it the I2C bus
    if multiplexer is not None:
        import adafruit_tca9548a
        tca = adafruit_tca9548a.TCA9548A(i2c)
        # For the sensor on the multiplexer, create it using the TCA9548A channel instead of the I2C object
        sensor = adafruit_tsl2591_extended(tca[multiplexer])
    else:
        sensor = adafruit_tsl2591_extended(i2c, address=i2c_address)

    # Set gain and integration time (600ms)
    sensor.enable()
    gain_level = required_device_gain_setting
    sensor.gain = gain_level
    # sensor.gain = adafruit_tsl2591.GAIN_LOW # for testing
    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
    prev_lux = -100
    saturation_counter = 0

    time.sleep(0.5)

    # Create the data logger
    radiometer_data_logger = RadiometerDataLogger(name=device_name)

    # Create the SQM readings writer
    sqm_writer = Sqm_Writer()

    # Create the flask REST server
    flask_server = FlaskServer(device_name=device_name)
    flask_server.start()


    while True:
        try:
            # Wait for an ALS interrupt to signal a reading has completed
            sensor.wait_interrupt_600()

            # Get a time stamp for the latest reading
            time_stamp = datetime.datetime.now()

            # Read and calculate the light level in lux.
            lux, vis_level, ir_level, again, atime = sensor.get_light_levels()

            # Log the latest reading
            radiometer_data_logger.log_data(
                time_stamp, lux, vis_level, ir_level, again, atime)

            # Write the latest SQM value
            sqm_writer.update(np.log10(lux/108000)/-0.4)

            # Write the latest data to the flask server
            flask_server.set_data(time_stamp, lux, vis_level, ir_level, again, atime)

            # Check if the gain level can be changed back to max
            if auto_gain and gain_level != adafruit_tsl2591.GAIN_MAX and lux < 1.0:
                # sensor.disable()
                sensor.adc_en_off()
                gain_level = adafruit_tsl2591.GAIN_MAX
                sensor.gain = gain_level
                sensor.enable()
                sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
                # Wait for next valid reading
                sensor.wait_interrupt_600()
                # time.sleep(GUARD_TIME)

            # Reset the saturation counter amd store the previous lux value
            saturation_counter = 0
            prev_lux = lux


        # An exception can occur if the light sensor saturates
        except Exception as e:
            if verbose:
                print(e)

            # If there is an exception with fixed gain, reset the sensor every 1200 readings (120s)
            if not auto_gain:
                saturation_counter += 1
                if saturation_counter > 100:
                    reset_sensor(sensor, gain_level,
                                 adafruit_tsl2591.INTEGRATIONTIME_100MS)
                    saturation_counter = 0
                continue

            # Attempt to lower gain so that readings can continue
            # Gain at GAIN_MED will allow measurements to be taken up to about 3000 lux
            if gain_level == adafruit_tsl2591.GAIN_MAX:

                # Log the sensor values anyway even though there has been an exception as the IR sensor values may still be useful.
                if prev_lux > 0:
                    lux, vis_level, ir_level, again, atime = sensor.get_light_levels(
                        disable_exception=True)
                    radiometer_data_logger.log_data(
                        time_stamp, prev_lux, vis_level, ir_level, again, atime)

                # sensor.disable()
                sensor.adc_en_off()
                gain_level = adafruit_tsl2591.GAIN_MED
                sensor.gain = gain_level
                sensor.enable()
                sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
                # Sleep to ensure next reading is valid
                sensor.wait_interrupt_600()
                # time.sleep(GUARD_TIME)

            # If the sensor has been saturated for a long time (60s), reset the sensor and then stay asleep
            else:
                saturation_counter += 1
                if saturation_counter > 100:
                    reset_sensor(sensor, gain_level,
                                 adafruit_tsl2591.INTEGRATIONTIME_100MS)
                    time.sleep(120)

                    # Take a reading at lowest gain, then set the gain back to medium
                    sensor.gain = adafruit_tsl2591.GAIN_LOW
                    sensor.enable()
                    time.sleep(1)
                    try:
                        lux, vis_level, ir_level, again, atime = sensor.get_light_levels()
                        time_stamp = datetime.datetime.now()
                        radiometer_data_logger.log_data(
                            time_stamp, lux, vis_level, ir_level, again, atime)
 
                         # Write the new SQM value
                        sqm_writer.update(np.log10(lux/108000)/-0.4)
                        flask_server.set_data(time_stamp, lux, vis_level, ir_level, again, atime)

                    except Exception as e:
                        print(e)

                    # sensor.disable()
                    sensor.adc_en_off()
                    time.sleep(1)
                    gain_level = adafruit_tsl2591.GAIN_MED
                    sensor.gain = gain_level
                    sensor.enable()
                    time.sleep(1)

            time.sleep(0.05)
