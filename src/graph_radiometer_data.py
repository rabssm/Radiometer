
import argparse
import pandas as pd
from matplotlib import pyplot as plt
from scipy.signal import find_peaks
import numpy as np


# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Analyse radiometer data')
    ap.add_argument("file", type=str, help="File or directory to analyse.")
    ap.add_argument("-n", "--night", action='store_true',
                    help="Display with night readings range")
    ap.add_argument("-p", "--prominence", type=float, default=0.005,
                    help="Peak detection prominence above background. Default is 0.005 lux")

    args = vars(ap.parse_args())

    file_name = args['file']
    night_range = args['night']
    prominence = args['prominence']

    print("Graphing", file_name)

    columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain"]
    df = pd.read_csv(file_name, sep=' ', names=columns)

    # Find peaks in the data
    peaks, properties = find_peaks(
        df.Lux[df.Lux < 4.0], prominence=prominence)  # , width=3)
    print("Peaks found:", len(peaks))
    if (len(peaks) < 50):
        for peak in peaks:
            print(df.Time[peak], df.Lux[peak])

    times = pd.to_datetime(df.Date + " " + df.Time, format="%Y/%m/%d %H:%M:%S.%f")

    print("Contents in csv file:")
    print(df)

    # Plot the lux data vs time
    plt.plot(times, df.Lux)
    plt.xlabel('Time')
    plt.ylabel('Lux')
    if night_range:
        plt.ylim(-0.1, 0.5)

    # Plot the detected peaks
    plt.plot(times[peaks], df.Lux[peaks], marker="o", ls="", ms=3)

    plt.show()
