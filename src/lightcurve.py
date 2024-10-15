import argparse
import glob
import os
import pandas as pd
from matplotlib import pyplot as plt
from scipy.signal import find_peaks
# from scipy.integrate import simpson
import numpy as np


CAPTURE_DIR = os.path.expanduser('~/radiometer_data/')

# Taken from https://github.com/adafruit/Adafruit_CircuitPython_TSL2591/blob/main/adafruit_tsl2591.py for cpl calculation
ADAFRUIT_TSL2591_LUX_DF = 408.0

# Tau for meteor mass calulation
TAU = 0.05

# Luminous efficacy
LUMINOUS_EFFICACY = 0.0079

# Power of a magnitude 0 fireball is 1500 Watts
POWER_OF_MAG_ZERO_FIREBALL = 1500

# Re irradiance responsivity from TSL2591 datasheet, white light on "visible" sensor channel 0
# The 100 scaling factor is to convert the RE_WHITE_CHANNEL0 from the datsheet units of counts/(μW/cm2) to counts/(W/m2)
RE_WHITE_CHANNEL0 = 264.1 * 100

# High gain factor 428x from https://github.com/adafruit/Adafruit_CircuitPython_TSL2591/blob/main/adafruit_tsl2591.py
GAIN_HIGH = 428

# Minimum magnitude detectable with the sensor
MIN_MAGNITUDE = -6.0

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(
        description='Analyse a light curve from the radiometer data',
        epilog='Example usage: python lightcurve.py -p 0.01 -w 40 -d 120000 -a 50 -v 12000 20230131_0001.csv')
    ap.add_argument("file", type=str, nargs='+',
                    help="File to analyse")
    ap.add_argument("-p", "--prominence", type=float, default=0.0,
                    help="Peak detection prominence above background. Default is auto")
    ap.add_argument("-w", "--width", type=int, default=40,
                    help="Number of points to analyse around the peak. Default is 40")
    ap.add_argument("-d", "--distance", type=float, default=50000,
                    help="Straight line distance to meteor in meters. Default is 50000 m")
    ap.add_argument("-a", "--angle", type=float, default=45,
                    help="Incident angle of meteor with sensor in degrees. Default is 45 degrees")
    ap.add_argument("-e", "--extinction", type=float, default=0.0,
                    help="Atmospheric extinction in magnitudes. Default is 0 magnitudes extinctions")
    ap.add_argument("-v", "--velocity", type=float, default=15000,
                    help="Velocity in m/s. Default is 15000 m/s")

    args = vars(ap.parse_args())

    file_names = args['file']
    prominence = args['prominence']
    width = args['width']
    distance = args['distance']
    angle = args['angle']
    extinction = args['extinction']
    velocity = args['velocity']

    print("Graphing", file_names)
    print("Initial parameters.\nDistance (m):", distance,
          "\nAngle (degrees):", angle, "\nAtmospheric Extinction", extinction, "\nVelocity (m/s):", velocity)
    print()

    # Ignore div by zero warnings
    np.seterr(divide='ignore')

    # Collect the data into a pandas dataframe
    columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain", "IntTime"]
    dfs = [pd.read_csv(file_name, sep=' ', names=columns)
           for file_name in file_names]
    df = pd.concat(dfs, ignore_index=True)

    # Format the times into datetime values
    times = pd.to_datetime(df.Date + " " + df.Time,
                           format="%Y/%m/%d %H:%M:%S.%f")

    # Find peaks in the data. If no prominence is given, calculate one
    if prominence == 0.0:
        prominence = np.max(df.Lux) - np.median(df.Lux) - np.std(df.Lux)
    peaks = []
    peaks, properties = find_peaks(
        df.Lux, prominence=prominence)  # , width=3)
    print("Peaks found:", len(peaks))

    if len(peaks) == 0:
        exit(-1)

    for peak in peaks:
        print(df.Time[peak], df.Lux[peak])

    # Calculate area under the peak
    # print(peaks, properties)
    median_adjusted_lux = df.Lux[peak -
                                 (int(width/2)):peak+(int(width/2))]-np.median(df.Lux)
    median_adjusted_lux[median_adjusted_lux < 0] = 0
    times_over_peaks = times[peak - (int(width/2)):peak+(int(width/2))]
    times_over_peaks = times_over_peaks - times[peak - (int(width/2))]
    np_times_over_peaks = times_over_peaks.to_numpy(dtype=float)/1e9

    print("Median", np.median(df.Lux), "Peak",
          df.Lux[peak], "STD", np.std(df.Lux))
    integrated_lux = np.trapz(median_adjusted_lux, x=np_times_over_peaks)
    # , simpson(adjusted_peaks))
    print("Area under peak:", integrated_lux, "Lux.s\n")

    # Calculate the area of the sphere at that distance
    area = 4 * np.pi * np.square(distance)

    # Adjust the lux values for incident angle with the sensor
    angle_adjusted_lux = median_adjusted_lux / np.cos(np.deg2rad(angle))

    # Adjust the lux values for atmospheric extinction
    extinction_adjusted_lux = angle_adjusted_lux * np.power(2.5, extinction)

    # Calculate the power and magnitude over the light curve
    powers = extinction_adjusted_lux * area * LUMINOUS_EFFICACY
    powers[powers < 0] = 0
    magnitudes = -2.5*np.log10(powers/POWER_OF_MAG_ZERO_FIREBALL)
    magnitudes[magnitudes == np.inf] = MIN_MAGNITUDE

    integrated_power = np.trapz(powers, x=np_times_over_peaks)
    mass = 2 * integrated_power / (TAU * np.square(velocity))

    print("Estimated energy:", np.around(integrated_power, 2), "J")
    print("Estimated mass:", np.around(mass, 2), "kg")
    print("Peak magnitude", np.around(np.min(magnitudes), 2))
    print()

    # Plot the lux data vs time
    plt.plot(times, df.Lux)
    # plt.axvspan(times[peaks-width], times[peaks+width], color='red', alpha=0.1)
    plt.xlabel('Time')
    plt.ylabel('Lux')

    # Plot the detected peaks
    if len(peaks) > 0:
        plt.plot(times[peaks],
                 df.Lux[peaks], marker="o", ls="", ms=3)

    plt.title('Illuminance')
    plt.show()

    # Plot the magnitudes
    plt.plot(times_over_peaks, magnitudes)
    plt.xlabel('Time')
    plt.ylabel('Abs Magnitude')
    plt.gca().invert_yaxis()
    plt.show()

    # Plot the visible and IR data vs time
    plt.xlabel('Time')
    plt.ylabel('Count')
    plt.plot(times, df.Visible, label="Visible and IR", marker='.')
    plt.plot(times, df.IR, label="IR", marker='.')
    plt.title('Raw sensor values')
    plt.legend(loc='upper left')
    plt.show()

    # Calculate energy and mass using the raw channel 0 data which includes visble and IR
    visible_data = df.Visible
    visible_data = visible_data - np.median(visible_data)

    # Restrict the data to values either side of the peak
    visible_data = visible_data[peak - (int(width/2)):peak+(int(width/2))]
    times_of_visible_data = times[peak - (int(width/2)):peak+(int(width/2))]
    gains_of_visible_data = df.Gain[peak - (int(width/2)):peak+(int(width/2))]

    # Calculate the gain scaling
    # The RE_WHITE_CHANNEL0 measured in the datasheet is measured at high gain, so divide by the GAIN_HIGH factor
    # Note: datasheet says the gain scaling for max gain is 9200/400
    gain_scaling = gains_of_visible_data/GAIN_HIGH

    # Get watts/m2.
    watts_per_square_meter = visible_data / (RE_WHITE_CHANNEL0 * gain_scaling)
    powers = watts_per_square_meter * area

    # Remove any powers that may be negative
    powers[powers < 0] = 0

    # Adjust the powers for the incident angle of the light with the sensor
    angle_adjusted_powers = powers / np.cos(np.deg2rad(angle))

    # Adjust the powers for atmospheric extinction
    extinction_adjusted_powers = angle_adjusted_powers * np.power(2.5, extinction)

    # Integrate the power over time to get the energy under the light curve
    integrated_power = np.trapz(extinction_adjusted_powers, x=np_times_over_peaks)

    mass = 2 * integrated_power / (TAU * np.square(velocity))
    print("Estimated energy from raw sensor data",
          '{:.2E}'.format(integrated_power), "J")
    print("Estimated mass from raw sensor data", np.around(mass, 2), "kg")

    magnitudes_raw = -2.5*np.log10(extinction_adjusted_powers /
                               POWER_OF_MAG_ZERO_FIREBALL)

    magnitudes_raw[magnitudes_raw == np.inf] = MIN_MAGNITUDE

    print("Peak magnitude", np.around(np.min(magnitudes_raw), 2))

    # Plot power graph
    plt.plot(times_of_visible_data, powers, marker='.')
    plt.title("Power from Raw Visible Sensor Data")
    plt.xlabel('Time')
    plt.ylabel('Power (Watts)')
    plt.show()

    # Plot graph of magnitudes
    plt.plot(times_of_visible_data, magnitudes, label="Lux Data", marker='.')
    plt.plot(times_of_visible_data, magnitudes_raw, label="Raw Visible Sensor Data", marker='.')
    plt.title("Magnitudes")
    plt.xlabel('Time')
    plt.ylabel('Abs Magnitude')
    plt.gca().invert_yaxis()
    plt.legend(loc='upper left')

    plt.show()
