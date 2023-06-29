import argparse
import datetime
import os
import signal
import threading
import time
import numpy as np
import syslog
import board
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_tsl2591

DATA_DIR = os.path.expanduser('~/radiometer_data/')

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
    sensor.wait_interrupt()


def measure_sky_brightness(sensor, radiometer_data_logger):
    # Measure sky brightness in mag/arcsec^2 using max integration time
    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
    # Sleep to ensure next reading is valid
    sensor.wait_interrupt()
    sensor.wait_interrupt()
    # time.sleep(1.3)

    try:
        lux, vis_level, ir_level, again, atime = sensor.get_light_levels()
    except:
        sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
        sensor.wait_interrupt()
        # time.sleep(1.3)
        return 0

    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
    radiometer_data_logger.log_data(
        datetime.datetime.now(), lux, vis_level, ir_level, again, atime)

    sky_brightness = np.log10(lux/108000)/-0.4
    syslog.syslog(syslog.LOG_INFO, "TSL2591 Sky brightness " +
                  str(sky_brightness))
    sensor.wait_interrupt()
    # time.sleep(1.3)

    return sky_brightness


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


# Add a get_light_levels method to the adafruit_tsl2591 class
class adafruit_tsl2591_extended(adafruit_tsl2591.TSL2591):

    def get_light_levels(self, disable_exception=False):
        """Read the sensor and calculate a lux value from both its infrared
        and visible light channels.

        .. note::
            :attr:`lux` is not calibrated!

        """
        channel_0, channel_1 = self.raw_luminosity

        # Compute the atime in milliseconds
        atime = 100.0 * self._integration_time + 100.0

        # Set the maximum sensor counts based on the integration time (atime) setting
        if self._integration_time == adafruit_tsl2591.INTEGRATIONTIME_100MS:
            max_counts = adafruit_tsl2591._TSL2591_MAX_COUNT_100MS
        else:
            max_counts = adafruit_tsl2591._TSL2591_MAX_COUNT

        # Handle overflow.
        if channel_0 >= max_counts or channel_1 >= max_counts:
            message = (
                "Overflow reading light channels!, Try to reduce the gain of\n "
                + "the sensor using adafruit_tsl2591.GAIN_LOW"
            )
            if not disable_exception:
                raise RuntimeError(message)
        # Calculate lux using same equation as Arduino library:
        #  https://github.com/adafruit/Adafruit_TSL2591_Library/blob/master/Adafruit_TSL2591.cpp
        again = 1.0
        if self._gain == adafruit_tsl2591.GAIN_MED:
            again = 25.0
        elif self._gain == adafruit_tsl2591.GAIN_HIGH:
            again = 428.0
        elif self._gain == adafruit_tsl2591.GAIN_MAX:
            again = 9876.0
        cpl = (atime * again) / adafruit_tsl2591._TSL2591_LUX_DF
        lux1 = (channel_0 - (adafruit_tsl2591._TSL2591_LUX_COEFB * channel_1)) / cpl
        lux2 = (
            (adafruit_tsl2591._TSL2591_LUX_COEFC * channel_0) -
            (adafruit_tsl2591._TSL2591_LUX_COEFD * channel_1)
        ) / cpl

        # Alternate lux calculation 1 - currently used by C++ libraries
        # See: https://github.com/adafruit/Adafruit_TSL2591_Library/issues/14
        #     lux = (((float)ch0 - (float)ch1)) * (1.0F - ((float)ch1 / (float)ch0)) / cpl;
        # alt_lux = ((float(channel_0) - float(channel_1))) * (1.0 - (float(channel_1) / float(channel_0))) / cpl

        return max(lux1, lux2), channel_0, channel_1, again, atime

    # Switch off only the ADC_EN
    def adc_en_off(self):
        self._write_u8(
            adafruit_tsl2591._TSL2591_REGISTER_ENABLE,
            adafruit_tsl2591._TSL2591_ENABLE_POWERON
            | adafruit_tsl2591._TSL2591_ENABLE_AIEN
            | adafruit_tsl2591._TSL2591_ENABLE_NPIEN,
        )

    def reset(self):
        # Perform a device reset
        val = 0b10000000
        # control = self._read_u8(adafruit_tsl2591._TSL2591_REGISTER_CONTROL)
        # control &= 0b01111111
        control = val

        # A write to the reset register always generates an exception
        try:
            self._write_u8(adafruit_tsl2591._TSL2591_REGISTER_CONTROL, control)
        except:
            pass

    def clear_interrupts(self):
        # Clear ALS interrupts.
        with self._device as i2c:
            # Make sure to add command bit and special function bit to write request.
            sf = 0x07
            self._BUFFER[0] = (0xE0 | sf) & 0xFF
            self._BUFFER[1] = 0x00 & 0xFF
            i2c.write(self._BUFFER, end=2)

    def wait_interrupt(self):
        # Wait for AINT interrupt to signal a reading has completed
        # Initial sleep 50ms
        time.sleep(0.05)
        # Get the status to check for the AINT interrupt being asserted
        while self._read_u8(0x13) & 0x10 == 0:
            time.sleep(0.005)

        self.clear_interrupts()


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
    ap.add_argument("-n", "--name", type=str, default="",
                    help="Optional name of the sensor for the output file name. Default is no name")
    ap.add_argument("-s", "--sqm", action='store_true',
                    help="Take hourly SQM measurements")
    ap.add_argument("-v", "--verbose", action='store_true',
                    help="Verbose output to terminal")
    args = vars(ap.parse_args())

    i2c_address = args['address']
    i2c_bus = args['bus']
    gain_name = args['gain']
    device_name = args['name']
    multiplexer = args['multiplexer']
    sqm = args['sqm']
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

    # Set gain and fastest integration time (100ms)
    sensor.enable()
    gain_level = required_device_gain_setting
    sensor.gain = gain_level
    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
    prev_lux = -100
    saturation_counter = 0

    time.sleep(0.5)

    # Create the data logger
    radiometer_data_logger = RadiometerDataLogger(name=device_name)

    while True:
        try:
            # Wait for an ALS interrupt to signal a reading has completed
            sensor.wait_interrupt()

            # Get a time stamp for the latest reading
            time_stamp = datetime.datetime.now()

            # Read and calculate the light level in lux.
            lux, vis_level, ir_level, again, atime = sensor.get_light_levels()

            # Log the latest reading
            radiometer_data_logger.log_data(
                time_stamp, lux, vis_level, ir_level, again, atime)

            # Check if the gain level can be changed back to max
            if auto_gain and gain_level != adafruit_tsl2591.GAIN_MAX and lux < 3.0:
                # sensor.disable()
                sensor.adc_en_off()
                gain_level = adafruit_tsl2591.GAIN_MAX
                sensor.gain = gain_level
                sensor.enable()
                sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
                # Wait for next valid reading
                sensor.wait_interrupt()
                # time.sleep(GUARD_TIME)

            # Reset the saturation counter amd store the previous lux value
            saturation_counter = 0
            prev_lux = lux

            # On each hour change, measure the sky brightness if it's dark
            if sqm and lux < 0.2 and time_stamp.minute == 0 and time_stamp.second == 0:
                measure_sky_brightness(sensor, radiometer_data_logger)

        # An exception can occur if the light sensor saturates
        except Exception as e:
            if verbose:
                print(e)

            # If there is an exception with fixed gain, reset the sensor every 1200 readings (120s)
            if not auto_gain:
                saturation_counter += 1
                if saturation_counter > 1200:
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
                sensor.wait_interrupt()
                # time.sleep(GUARD_TIME)

            # If the sensor has been saturated for a long time (120s), reset the sensor and then stay asleep
            else:
                saturation_counter += 1
                if saturation_counter > 1200:
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
