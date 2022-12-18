import argparse
import glob
import os
import pandas as pd
from matplotlib import pyplot as plt
from scipy.signal import find_peaks
import numpy as np


CAPTURE_DIR = os.path.expanduser('~/radiometer_data/')

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Analyse radiometer data')
    ap.add_argument("file", type=str, nargs='*',
                    help="File or directory to analyse. Default is last 2 files in the directory " + CAPTURE_DIR)
    ap.add_argument("-n", "--night", action='store_true',
                    help="Display with night readings range")
    ap.add_argument("-l", "--log", action='store_true',
                    help="Display with log scale")
    ap.add_argument("-s", "--sky", action='store_true',
                    help="Display sky brightness")
    ap.add_argument("-p", "--prominence", type=float, default=0.005,
                    help="Peak detection prominence above background. Default is 0.005 lux")

    args = vars(ap.parse_args())

    file_names = args['file']
    night_range = args['night']
    prominence = args['prominence']
    log_scale = args['log']
    display_sky_brightness = args['sky']

    # If no filenames were given, use the 2 newest files
    if len(file_names) == 0:
        file_names = sorted(glob.glob(CAPTURE_DIR + "R*.csv"))[-2:]

    print("Graphing", file_names)

    # Collect the data into a pandas dataframe
    columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain"]
    dfs = [pd.read_csv(file_name, sep=' ', names=columns)
           for file_name in file_names]
    df = pd.concat(dfs, ignore_index=True)

    # Find peaks in the data
    peaks, properties = find_peaks(
        df.Lux[df.Lux < 4.0], prominence=prominence)  # , width=3)
    print("Peaks found:", len(peaks))
    if (len(peaks) < 50):
        for peak in peaks:
            print(df.Time[peak], df.Lux[peak])

    # Format the times into datetime values
    times = pd.to_datetime(df.Date + " " + df.Time,
                           format="%Y/%m/%d %H:%M:%S.%f")

    print("Contents in csv file:")
    print(df)

    # Calculate sky brightness and minimum rolling average over 64 readings (~6 seconds)
    rolling = df.Lux.rolling(64).sum()/64
    min_lux_index = np.argmin(df.Lux)
    min_rolling_index = np.argmin(rolling)
    print("Min sky brightness:", times[min_lux_index], np.log10(df.Lux[min_lux_index]/108000)/-0.4, "mag/arcsec^2")
    print("Min rolling average sky brightness:", times[min_rolling_index], np.log10(rolling[min_rolling_index]/108000)/-0.4, "mag/arcsec^2")

    # Plot the lux data vs time
    plt.plot(times, df.Lux)
    plt.xlabel('Time')
    plt.ylabel('Lux')
    if night_range:
        plt.ylim(-0.1, 0.5)
    elif log_scale:
        plt.yscale("log")

    # Plot the detected peaks
    plt.plot(times[peaks], df.Lux[peaks], marker="o", ls="", ms=3)

    plt.show()

    # Display sky brightness
    if display_sky_brightness:
        sky_brightness = np.log10(df.Lux/108000)/-0.4
        plt.plot(times, sky_brightness)
        plt.xlabel('Time')
        plt.ylabel('Mag/arcsec^2')

        # Plot the detected peaks
        plt.plot(times[peaks], sky_brightness[peaks], marker="o", ls="", ms=3)
        plt.show()

    # Plot the visible and IR data vs time
    plt.xlabel('Time')
    plt.ylabel('Count')
    if log_scale:
        plt.yscale("log")
    plt.plot(times, df.Visible, label="Visible")
    plt.plot(times, df.IR, label="IR")
    plt.legend()
    plt.show()
