import argparse
import re
import pandas as pd
from matplotlib import pyplot as plt
import numpy as np
import scipy.stats
import ephem
import datetime

TWILIGHT_HORIZON = '-9.0'     # Set degree below horizon for twilight (astronomical is -18 degrees)


class ConfigReader() :
    def get_config(self, config_dir) :
        with open(config_dir + '/.config') as fp:
            for cnt, line in enumerate(fp):
                line_words = (re.split("[: ]+", line))
                if line_words[0] == 'stationID' : self.cameraname = line_words[1]
                if line_words[0] == 'latitude'  : self.latitude = line_words[1]
                if line_words[0] == 'longitude' : self.longitude = line_words[1]
                if line_words[0] == 'elevation' : self.elevation = float(line_words[1])


class DayNightChecker() :

    def __init__(self, latitude, longitude, elevation) :
        self.location = ephem.Observer()
        self.location.lat, self.location.long = str(latitude), str(longitude)
        self.location.elevation          = elevation
        self.location.horizon            = TWILIGHT_HORIZON

        self.sun = ephem.Sun()


    def is_sun_down(self, time):

        ephem_time = ephem.Date(time)

        # Only recalculate rise and set if one of them has passed
        try:
            if (ephem_time < self.next_setting) and (ephem_time < self.next_rising) :
                return (self.next_setting > self.next_rising)
        except:
            pass

        # Calculate rise and set times
        try:
            self.next_setting = self.location.next_setting(self.sun, start=ephem_time)
            self.next_rising  = self.location.next_rising(self.sun, start=ephem_time)
            # print(ephem_time, self.next_setting, self.next_rising)
            return self.next_setting > self.next_rising
        except:
            return False

# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Compare lux meter SQM data to RMS FS measurements')
    ap.add_argument("sqm_file", type=str,
                    help="File to analyse.")
    ap.add_argument("rms_file", type=str,
                    help="RMS FS file to analyse.")
    ap.add_argument("-c", "--config_dir", type=str, default='.',
                    help="RMS config directory")
    ap.add_argument("-a", "--angle", type=float, default=65.0,
                    help="Camera angle above horizon")
    ap.add_argument("-n", "--night", type=str, default=None,
                    help="Date of night to compare e.g. 20230714")

    args = vars(ap.parse_args())

    fs_file = args['rms_file']
    sqm_file = args['sqm_file']
    config_dir = args['config_dir']
    camera_angle = args['angle']
    night = args['night']

    config = ConfigReader()
    config.get_config(config_dir)
    night_checker = DayNightChecker(config.latitude, config.longitude, config.elevation)

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
    # df = df.drop(df[df.SQM < 12].index)

    # Isolate data based on date
    if night is not None :
        start_date = datetime.datetime.strptime(night + ' 12:00', "%Y%m%d %H:%M")
        end_date = start_date + datetime.timedelta(days=1)
        print(start_date, end_date)

        res = df[df['times'] > start_date]
        df = res[res['times'] < end_date]

    # Clip the data outside astronomical twilight (sun 18 degrees below horizon)
    indexes = []
    for index, row in df.iterrows():
        if not night_checker.is_sun_down(row.times) :
            # print("Dropping", index, row.times)
            indexes.append(index)
    
    df.drop(index=indexes, inplace=True)

    print(df)

    # Get the correlation
    print("Correlation:", df['log_FS'].corr(df['SQM']))
    linregress_results = scipy.stats.linregress(df['log_FS'], df['SQM'])
    print(linregress_results)

    slope=linregress_results.slope
    intercept=linregress_results.intercept

    """
    # Try a polynomial fit
    poly_fit_result = np.polyfit(df['log_FS'], df['SQM'], 2)
    print(poly_fit_result)

    poly_fit_tmp = 2.5*np.log10(df.intensity_data_avg/np.cos(np.radians(camera_angle)))
    poly_fit = np.polyval(poly_fit_result, poly_fit_tmp)
    # poly_fit = (np.power(poly_fit_tmp, 3) + (np.square(poly_fit_tmp) * poly_fit_result[0]) + (poly_fit_tmp * poly_fit_result[1]) + poly_fit_result[2]
    df["Fitted_data"] = poly_fit
    """

    # df_fs.times.resample('3T')
    # df_fs.intensity_data_avg=2.5*np.log10(df_fs.intensity_data_avg/np.cos(np.radians(65)))

    # Produce curve based on correlation results
    df["Fitted_data"] = (df["log_FS"] * slope) + intercept


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
    ax1.plot(df.times, df.Fitted_data, color=color, label='RMS FS (data fit)')
    
    plt.legend()
    plt.grid()
    plt.show()

