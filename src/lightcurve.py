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

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(
        description='Analyse a light curve from the radiometer data')
    ap.add_argument("file", type=str, nargs='*',
                    help="File or directory to analyse. Default is last 2 files in the directory " + CAPTURE_DIR)
    ap.add_argument("-p", "--prominence", type=float, default=0,
                    help="Peak detection prominence above background. Usually 0.005 lux. Default is no peak detection")
    ap.add_argument("-w", "--width", type=int, default=10,
                    help="Peak width. Default is 10")
    ap.add_argument("-d", "--distance", type=float, default=50000,
                    help="Straight line distance to meteor. Default is 50000 m")
    ap.add_argument("-a", "--angle", type=float, default=45,
                    help="Incident angle of meteor with sensor in degrees. Default is 45 degrees")
    ap.add_argument("-v", "--velocity", type=float, default=15000,
                    help="Velocity in m/s. Default is 15000")

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

    # Find peaks in the data
    peaks = []
    if prominence != 0:
        peaks, properties = find_peaks(
            df.Lux, prominence=prominence)  # , width=3)
        print("Peaks found:", len(peaks))
        for peak in peaks:
            print(df.Time[peak], df.Lux[peak])

        # Calculate area under the peak
        print(peaks, properties)
        median_adjusted_peaks = df.Lux[peak -
                                       (int(width/2)):peak+(int(width/2))]-np.median(df.Lux)
        # print(adjusted_peaks)
        print("Median", np.median(df.Lux), "Peak",
              df.Lux[peak], "STD", np.std(df.Lux))
        integrated_lux = np.trapz(median_adjusted_peaks)
        # , simpson(adjusted_peaks))
        print("Area under peak:", integrated_lux, "Lux")
        lux_array = np.array([integrated_lux, np.std(df.Lux)])

        # Calculate the energy and mass
        area = 4 * np.pi * np.square(distance)
        lum_effic = 0.007
        angle_adjusted_lux = lux_array / np.cos(np.deg2rad(angle))
        total_energy = angle_adjusted_lux * area * lum_effic
        tau = 0.007
        mass = 2 * total_energy / (tau * np.square(velocity))

        print("Estimated energy:", total_energy)
        print("Estimated mass:", np.around(
            mass[0], 2), "+/-", np.around(mass[1], 3), "kg")

    # Format the times into datetime values
    times = pd.to_datetime(df.Date + " " + df.Time,
                           format="%Y/%m/%d %H:%M:%S.%f")

    print("Contents in csv file:")
    print(df)

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
