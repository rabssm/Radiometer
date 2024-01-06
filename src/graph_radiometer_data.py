import argparse
from collections import deque
import glob
import os
import pandas as pd
from matplotlib import pyplot as plt
from scipy.signal import find_peaks
import numpy as np


CAPTURE_DIR = os.path.expanduser('~/radiometer_data/')

PEAK_DETECTION_LUX_LIMIT = 2.0
SSSM_FACTOR = 1900   # Solar diameter is ~1900 arcsec 


# Taken from https://github.com/adafruit/Adafruit_CircuitPython_TSL2591/blob/main/adafruit_tsl2591.py for cpl calculation
ADAFRUIT_TSL2591_LUX_DF = 408.0

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Analyse radiometer data')
    ap.add_argument("file", type=str, nargs='*',
                    help="File or directory to analyse. Default is last 2 files in the directory " + CAPTURE_DIR)
    ap.add_argument("-n", "--night", action='store_true',
                    help="Display with night readings range")
    ap.add_argument("-l", "--linear", action='store_true',
                    help="Display with linear scale")
    ap.add_argument("-s", "--save", action='store_true',
                    help="Save plot")
    ap.add_argument("--seeing", type=int, default=0,
                    help="Display arcsecond seeing graph with seeing averaged over number of seconds supplied")
    # ap.add_argument("-s", "--sky", action='store_true',
    #                 help="Display sky brightness")
    ap.add_argument("-p", "--prominence", type=float, default=0,
                    help="Peak detection prominence above background. Usually 0.005 lux. Default is no peak detection")

    args = vars(ap.parse_args())

    file_names = args['file']
    night_range = args['night']
    prominence = args['prominence']
    linear_scale = args['linear']
    save_figure = args['save']
    display_seeing = args['seeing']

    # If no filenames were given, use the 2 newest files
    if len(file_names) == 0:
        file_names = sorted(glob.glob(CAPTURE_DIR + "R*.csv*"))[-2:]

    print("Graphing", file_names)

    # Collect the data into a pandas dataframe
    columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain", "IntTime"]
    dfs = [pd.read_csv(file_name, sep=' ', names=columns)
           for file_name in file_names]
    df = pd.concat(dfs, ignore_index=True)

    # Find peaks in the data that may match the light curve of a fireball
    peaks = []
    if prominence != 0:
        peaks, properties = find_peaks(
            df.Lux.clip(upper=PEAK_DETECTION_LUX_LIMIT), prominence=prominence, width=(1, 60))
        print("Peaks found:", len(peaks))
        if (len(peaks) < 50):
            for peak in peaks:
                print(df.Time[peak], df.Lux[peak])

    # Format the times into datetime values
    times = pd.to_datetime(df.Date + " " + df.Time,
                           format="%Y/%m/%d %H:%M:%S.%f")

    print("Contents in csv file:")
    print(df)

    # Print a sorted list of sky brightnesses ie. those with 600ms integration time
    sky_brightness_measurements = df[df['IntTime'] == 600]
    print("\nSky brightness measurements (sorted by brightness)")
    sky_brightness_measurements_sorted = sky_brightness_measurements.sort_values(
        by=['Lux'], ascending=False)
    for row in sky_brightness_measurements_sorted.itertuples():
        print(row.Date, row.Time, "SQM:", np.log10((row.Lux)/108000)/-0.4)

    # Calculate sky brightness and minimum rolling average over 64 readings (~6 seconds)
    rolling = df.Lux.rolling(64, center=True).sum()/64
    min_lux_index = np.argmin(df.Lux)
    min_rolling_index = np.argmin(rolling)
    print("Min sky brightness:", times[min_lux_index], np.log10(
        df.Lux[min_lux_index]/108000)/-0.4, "mag/arcsec^2")
    print("Min rolling average sky brightness:", times[min_rolling_index], np.log10(
        rolling[min_rolling_index]/108000)/-0.4, "mag/arcsec^2")

    # Plot the lux data vs time
    plt.figure(figsize=(10, 6))
    plt.plot(times, df.Lux)
    plt.xlabel('Time')
    plt.ylabel('Lux')
    if night_range:
        plt.ylim(-0.1, 0.5)
    elif not linear_scale:
        plt.yscale("log")

    # Plot the detected peaks
    if len(peaks) > 0:
        plt.plot(times[peaks],
                 df.Lux[peaks], marker="o", ls="", ms=3)

    plt.title('Illuminance')
    plt.grid()
    if save_figure:
        plt.savefig(os.path.splitext(file_names[-1])[0] + '.png')
        exit(0)
    plt.show()

    # Display sky brightness and rolling average
    sky_brightness = np.log10(df.Lux/108000)/-0.4
    plt.plot(times, sky_brightness, label="Sky Brightness")
    plt.plot(times, np.log10(rolling/108000)/-0.4, label="Rolling average")
    plt.xlabel('Time')
    plt.ylabel(r'Mag/$arcsec^2$ (mpsas)')

    plt.title('Sky Brightness')
    plt.legend(loc='lower left')
    plt.show()

    # Plot the seeing
    if display_seeing != 0 :
        # Split the data into chunks so we sample the RMS and the average over a period of 1 second
        chunk_size = 10
        rolling_deque = deque(maxlen=chunk_size)
        seeings = []
        seeing_times = []

        # Limit valid seeing readings to a lux value > 2000
        rslt_df = df[df['Lux'] > 2000] 

        for index, row in rslt_df.iterrows():
            lux = row['Lux']
            rolling_deque.append(lux)

            # If the deque is full
            if len(rolling_deque) == rolling_deque.maxlen:
                rolling = np.array(rolling_deque)
                average = np.average(rolling)
                rms = np.sqrt(np.mean((rolling - average)**2))
                average1 = np.average(rolling[0:4])
                average2 = np.average(rolling[5:9])
                seeing = SSSM_FACTOR * abs(rms / average)

                seeings.append(seeing)
                seeing_times.append(times[index])
                # print(average1, average2, rms, seeing)
                
                # Clear the deque for the next set of readings
                rolling_deque.clear()

        # Calcluate a rolling average over the required number of seconds
        rolling_seeings = np.convolve(seeings, np.ones(display_seeing), 'same') / display_seeing

        fig, ax1 = plt.subplots(figsize=(12,7))

        # Plot the illuminance
        color = 'tab:green'
        ax1.plot(times, df.Lux, color=color)
        ax1.set_ylabel('Illuminance (lux)', color=color)
        ax2 = ax1.twinx()

        # Plot the seeing
        color = 'tab:blue'
        ax2.plot(seeing_times, seeings, color=color)

        color = 'tab:red'
        ax2.plot(seeing_times, rolling_seeings, color=color)
        ax2.set(xlabel='Time')
        ax2.set_ylabel('Seeing (arcsec)', color=color)

       
        # ax1.yaxis.set_ticks_position("right")
        # ax2.yaxis.set_ticks_position("left")

        plt.grid()
        plt.show()
  

    # Plot the visible and IR data vs time
    plt.xlabel('Time')
    plt.ylabel('Count')
    if not linear_scale:
        plt.yscale("log")
    plt.plot(times, df.Visible, label="Visible and IR")
    plt.plot(times, df.IR, label="IR")
    plt.title('Raw sensor values')
    plt.legend(loc='upper left')
    plt.show()

    # Calculate average measured integration times
    res = np.diff(times)[::2].astype(np.int32)
    res1 = res[res < 140000000]
    if len(res1) > 0:
        m = res1.mean()/1e6
        print("Average measured times between readings for 100ms int time", m, "ms")
    res1 = res[res > 560000000]
    res2 = res1[res1 < 640000000]
    if len(res2) > 0:
        m = res2.mean()/1e6
        print("Average measured times between readings for 600ms int time", m, "ms")
