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
TAU = 0.005

# Luminous efficacy
LUMINOUS_EFFICACY = 0.0079

# Power of a magnitude 0 fireball is 1500 Watts
POWER_OF_MAG_ZERO_FIREBALL = 1500

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(
        description='Analyse a light curve from the radiometer data')
    ap.add_argument("file", type=str, nargs='*',
                    help="File or directory to analyse. Default is last 2 files in the directory " + CAPTURE_DIR)
    ap.add_argument("-p", "--prominence", type=float, default=0.005,
                    help="Peak detection prominence above background. Default is 0.005 lux")
    ap.add_argument("-w", "--width", type=int, default=10,
                    help="Number of points to analyse around the peak. Default is 10")
    ap.add_argument("-d", "--distance", type=float, default=50000,
                    help="Straight line distance to meteor in meters. Default is 50000 m")
    ap.add_argument("-a", "--angle", type=float, default=45,
                    help="Incident angle of meteor with sensor in degrees. Default is 45 degrees")
    ap.add_argument("-v", "--velocity", type=float, default=15000,
                    help="Velocity in m/s. Default is 15000 m/s")

    args = vars(ap.parse_args())

    file_names = args['file']
    prominence = args['prominence']
    width = args['width']
    distance = args['distance']
    angle = args['angle']
    velocity = args['velocity']

    # If no filenames were given, use the 2 newest files
    if len(file_names) == 0:
        file_names = sorted(glob.glob(CAPTURE_DIR + "R*.csv*"))[-2:]

    print("Graphing", file_names)
    print("Initial parameters. Distance:", distance, "Angle:", angle)

    # Collect the data into a pandas dataframe
    columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain", "IntTime"]
    dfs = [pd.read_csv(file_name, sep=' ', names=columns)
           for file_name in file_names]
    df = pd.concat(dfs, ignore_index=True)

    # Format the times into datetime values
    times = pd.to_datetime(df.Date + " " + df.Time,
                           format="%Y/%m/%d %H:%M:%S.%f")

    # Find peaks in the data
    peaks = []
    peaks, properties = find_peaks(
        df.Lux, prominence=prominence)  # , width=3)
    print("Peaks found:", len(peaks))

    if len(peaks) == 0:
        exit(-1)

    for peak in peaks:
        print(df.Time[peak], df.Lux[peak])

    # Calculate area under the peak
    print(peaks, properties)
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
    print("Area under peak:", integrated_lux, "Lux")
    lux_results = np.array([integrated_lux, np.std(df.Lux)])

    # Calculate the energy and mass
    area = 4 * np.pi * np.square(distance)
    angle_adjusted_lux = lux_results / np.cos(np.deg2rad(angle))
    total_energy = angle_adjusted_lux * area * LUMINOUS_EFFICACY
    mass = 2 * total_energy / (TAU * np.square(velocity))

    print("Estimated energy:", total_energy)
    print("Estimated mass:", np.around(
        mass[0], 2), "+/-", np.around(mass[1], 3), "kg")

    # Plot the lux data vs time
    plt.plot(times, df.Lux)
    plt.axvspan(times[peaks-width], times[peaks+width], color='red', alpha=0.1)
    plt.xlabel('Time')
    plt.ylabel('Lux')

    # Plot the detected peaks
    if len(peaks) > 0:
        plt.plot(times[peaks],
                 df.Lux[peaks], marker="o", ls="", ms=3)

    plt.title('Illuminance')
    plt.show()

    # Calculate the power and magnitude over the light curve
    powers = (median_adjusted_lux / np.cos(np.deg2rad(angle))) * \
        area * LUMINOUS_EFFICACY
    powers[powers < 0] = 0
    magnitudes = -2.5*np.log10(powers/POWER_OF_MAG_ZERO_FIREBALL)

    integrated_power = np.trapz(powers, x=np_times_over_peaks)
    mass = 2 * integrated_power / (TAU * np.square(velocity))

    # Plot the magnitudes
    plt.plot(times_over_peaks, magnitudes)
    plt.xlabel('Time')
    plt.ylabel('Abs Magnitude')
    plt.gca().invert_yaxis()
    plt.show()
