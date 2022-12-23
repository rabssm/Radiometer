import datetime
import os
import signal
import threading
import time
import numpy as np
import syslog
import board
import adafruit_tsl2591

DATA_DIR = os.path.expanduser('~/radiometer_data/')

DEBUG = True

# Minimum time to wait after a sensor time or gain setting
GUARD_TIME = 1.3

# Handle process signals


def signalHandler(signum, frame):
    os._exit(0)


# Measure sky brightness in mag/arcsec^2 using max integration time


def measure_sky_brightness(sensor):
    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
    # Sleep to ensure next reading is valid
    time.sleep(1.3)

    lux, vis_level, ir_level, again, atime = sensor.get_light_levels()

    sky_brightness = np.log10(lux/108000)/-0.4
    syslog.syslog(syslog.LOG_INFO, "TSL2591 Sky brightness " +
                  str(sky_brightness))
    time.sleep(GUARD_TIME)

    return sky_brightness


# Class for logging detections to radiometer data file
class RadiometerDataLogger():

    def __init__(self):
        # Make the data logging directory
        os.makedirs(DATA_DIR, exist_ok=True)

        # Set the filename and open it for appending
        self.filename = "R" + datetime.datetime.now().strftime("%Y%m%d") + ".csv"
        self.rmfile = open(DATA_DIR + self.filename, "a")

        self.flush_thread = threading.Thread(target=self.flush_file)
        self.flush_thread.start()

    # Log the date/time and lux reading
    def log_data(self, obs_time, lux_value, vis_level, ir_level, again, atime):
        # Check for date change
        try:
            filename = "R" + obs_time.strftime("%Y%m%d") + ".csv"
            if filename != self.filename:
                self.rmfile.close()
                self.filename = filename
                self.rmfile = open(DATA_DIR + self.filename, "a")

            # Log the data
            out_string = '{0:s} {1:.9f} {2:d} {3:d} {4:.1f} {5:.1f}\n'.format(time_stamp.strftime(
                "%Y/%m/%d %H:%M:%S.%f")[:-3], lux_value, vis_level, ir_level, again, atime)
            self.rmfile.write(out_string)
            if DEBUG:
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

    def get_light_levels(self):
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


# Main program
if __name__ == "__main__":

    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGTERM, signalHandler)

    # Open the sensor
    i2c = board.I2C()
    sensor = adafruit_tsl2591_extended(i2c)

    # Set max gain and slowest integration time (600ms)
    sensor.enable()
    gain_level = adafruit_tsl2591.GAIN_MAX
    sensor.gain = gain_level
    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
    prev_lux = -100
    saturation_counter = 0

    time.sleep(GUARD_TIME)

    radiometer_data_logger = RadiometerDataLogger()

    while True:
        try:
            # Read and calculate the light level in lux.
            lux, vis_level, ir_level, again, atime = sensor.get_light_levels()

            # If there is a change in light level, record it
            if lux != prev_lux:
                time_stamp = datetime.datetime.now()
                radiometer_data_logger.log_data(
                    time_stamp, lux, vis_level, ir_level, again, atime)

            # Check if the gain level can be changed back to max
            if gain_level != adafruit_tsl2591.GAIN_MAX and lux < 1.0:
                sensor.adc_en_off()
                gain_level = adafruit_tsl2591.GAIN_MAX
                sensor.gain = gain_level
                sensor.enable()
                sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
                # Sleep to ensure next reading is valid
                time.sleep(GUARD_TIME)

            # Reset the saturation counter, record the current lux value and sleep
            saturation_counter = 0
            prev_lux = lux

            time.sleep(0.05)

        # An exception can occur if the light sensor saturates, so change the gain.
        # Gain at GAIN_MED will allow measurements to be taken up to about 2000 lux
        except Exception as e:
            # print(e)
            # print("Error reading from sensor")
            if gain_level == adafruit_tsl2591.GAIN_MAX:
                sensor.adc_en_off()
                gain_level = adafruit_tsl2591.GAIN_MED
                sensor.gain = gain_level
                sensor.enable()
                sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_600MS
                # Sleep to ensure next reading is valid
                time.sleep(GUARD_TIME)

            # If the sensor has been saturated for a long time (120s), then stay asleep
            else:
                saturation_counter += 1
                if saturation_counter > 1200:
                    sensor.disable()
                    time.sleep(120)

                    # Take a reading at lowest gain, then set the gain back to medium
                    sensor.gain = adafruit_tsl2591.GAIN_LOW
                    sensor.enable()
                    time.sleep(GUARD_TIME)
                    try:
                        lux, vis_level, ir_level, again, atime = sensor.get_light_levels()
                        time_stamp = datetime.datetime.now()
                        radiometer_data_logger.log_data(
                            time_stamp, lux, vis_level, ir_level, again, atime)

                        sensor.adc_en_off()
                        time.sleep(GUARD_TIME)
                        gain_level = adafruit_tsl2591.GAIN_MED
                        sensor.gain = gain_level
                        sensor.enable()
                        time.sleep(GUARD_TIME)

                    except Exception as e:
                        print(e)

            time.sleep(0.05)
