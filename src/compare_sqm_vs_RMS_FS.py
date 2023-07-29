import argparse
import pandas as pd
from matplotlib import pyplot as plt
import numpy as np
import scipy.stats

ANGLE = 65  # Altitude angle of the camera providing FS data

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Compare lux meter SQM data to RMS FS measurements')
    ap.add_argument("sqm_file", type=str,
                    help="File to analyse.")
    ap.add_argument("rms_file", type=str,
                    help="RMS FS file to analyse.")

    args = vars(ap.parse_args())

    fs_file = args['rms_file']
    sqm_file = args['sqm_file']


    print("Comparing", sqm_file, fs_file)

    # Collect the data into a pandas dataframes
    df_fs = pd.read_csv(fs_file)
    
    # Use this for reading RMS background pixel file
    # df_photom = pd.read_csv(photom_file, sep=' ', dtype={'Date':'string', 'Time':'string'})

    df_sqm = pd.read_csv(sqm_file, sep=',')

    print(df_fs)
    print(df_sqm)

    # Format the times into datetime values
    df_fs["times"] = pd.to_datetime(df_fs.DateTime,
                           format="%Y-%m-%d %H:%M:%S.%f")

    df_sqm["times"] = pd.to_datetime(df_sqm.Date + " " + df_sqm.Time,
                           format="%Y/%m/%d %H:%M:%S")


    # Merge the data into 1 dataframe
    df = pd.merge_asof(df_sqm.sort_values(['times']), df_fs.sort_values(['times']), on='times', direction='forward')
    
    # df_fs = df_fs.set_index(pd.DatetimeIndex(df_fs['times']))
    df["log_FS"] = 2.5*np.log10(df.intensity_data_avg/np.cos(np.radians(65)))
    df = df.dropna(how='any')

    # Clip data below mag 12
    df = df.drop(df[df.SQM < 12].index)
    print(df)

    # Get the correlation
    print("Correlation:", df['log_FS'].corr(df['SQM']))
    linregress_results = scipy.stats.linregress(df['log_FS'], df['SQM'])
    print(linregress_results)

    # df_fs.times.resample('3T')
    # df_fs.intensity_data_avg=2.5*np.log10(df_fs.intensity_data_avg/np.cos(np.radians(65)))

    # Produce curve based on correlation results
    df["Correlated_data"] = (2.5*np.log10(df.intensity_data_avg/np.cos(np.radians(ANGLE))) * linregress_results.slope) + linregress_results.intercept


    # Now plot some graphs
    # plt.figure(figsize=(10, 6))
    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = 'tab:red'
    ax1.set_xlabel('Date/time')
    ax1.set_ylabel('SQM (mpsas)', color=color)
    # ax1.set_ylim(10, 22)
    ax1.plot(df.times, df.SQM, color=color)

    ax2 = ax1.twinx()  # instantiate a second axis that shares the same x-axis

    color = 'tab:blue'
    ax2.set_ylabel('log10 RMS Ave FS', color=color)
    # ax2.set_yscale('log')

    ax2.invert_yaxis()

    ax2.plot(df.times, df.log_FS)

    plt.show()

    # Plot the correlation
    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = 'tab:red'
    ax1.set_xlabel('Date/time')
    ax1.set_ylabel('SQM (mpsas)', color=color)
    # ax1.set_ylim(10, 22)
    ax1.plot(df.times, df.SQM, color=color, label='SQM')

    # ax2 = ax1.twinx()  # instantiate a second axis that shares the same x-axis
    # ax2 = ax1.twiny()  # instantiate a second axis that shares the same x-axis

    color = 'tab:blue'
    # ax2.set_ylabel('RMS Ave FS (converted to mpsas)', color=color)
    ax1.plot(df.times, df.Correlated_data, color=color, label='RMS FS')
    
    plt.legend()
    plt.grid()
    plt.show()

