import datetime
import os
import signal
import time
import board
import adafruit_tsl2591

DATA_DIR = os.path.expanduser('~/radiometer_data/')

DEBUG = True

# Handle process signals


def signalHandler(signum, frame):
    os._exit(0)


# Class for logging detections to radiometer data file
class RadiometerDataLogger():

    def __init__(self):
        # Make the data logging directory
        os.makedirs(DATA_DIR, exist_ok=True)

        # Set the filename and open it for appending
        self.filename = "R" + datetime.datetime.now().strftime("%Y%m%d") + ".csv"
        self.rmfile = open(DATA_DIR + self.filename, "a")

    def log_data(self, obs_time, lux_value):
        # Check for date change
        filename = "R" + obs_time.strftime("%Y%m%d") + ".csv"
        if filename != self.filename:
            self.filename.close()
            self.filename = filename
            self.rmfile = open(DATA_DIR + self.filename, "a")

        # Log the data
        self.rmfile.write(obs_time.strftime("%d/%m/%Y %H:%M:%S.%f")[
                          :-3] + " {0}\n".format(lux_value))


""""""
# Add a get_light_levels method to the afruit_tsl2591 class


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
        return max(lux1, lux2), channel_0, channel_1


# Main program
if __name__ == "__main__":

    signal.signal(signal.SIGINT,signalHandler)
    signal.signal(signal.SIGTERM, signalHandler)

    # Open the sensor
    i2c = board.I2C()
    sensor = adafruit_tsl2591_extended(i2c)

    # Set max gain and fastest integration time (100ms)
    sensor.enable()
    sensor.gain = adafruit_tsl2591.GAIN_MAX
    sensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
    prev_lux = -100
    time.sleep(0.5)

    radiometer_data_logger = RadiometerDataLogger()

    while True:
        try:
            # Read and calculate the light level in lux.
            lux, vis_level, ir_level = sensor.get_light_levels()
            if sensor.gain != adafruit_tsl2591.GAIN_MAX and lux < 3.0:
                sensor.disable()
                sensor.gain = adafruit_tsl2591.GAIN_MAX
                sensor.enable()

            time_stamp = datetime.datetime.now()
            if DEBUG:
                out_string = '{0:s} {1:.9f} {2:d} {3:d}'.format(time_stamp.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3], lux, vis_level, ir_level)
                print(out_string)
            radiometer_data_logger.log_data(time_stamp, lux)

            prev_lux = lux
            time.sleep(0.05)

        except Exception as e:
            # print(e)
            # print("Error reading from sensor")
            if sensor.gain == adafruit_tsl2591.GAIN_MAX:
                sensor.disable()
                sensor.gain = adafruit_tsl2591.GAIN_LOW
                sensor.enable()

            time.sleep(0.1)