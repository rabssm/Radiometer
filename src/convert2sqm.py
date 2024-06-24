import argparse
import glob
import os
import pandas as pd
from matplotlib import pyplot as plt
from scipy.signal import find_peaks
import numpy as np

# Rolling average step size
STEP_SIZE = 100


# Main program
if __name__ == "__main__":

    # Construct the argument parser and parse the arguments
    ap = argparse.ArgumentParser(description='Convert radiometer data to SQM measurements')
    ap.add_argument("file", type=str, nargs='*',
                    help="File or directory to analyse.")
    ap.add_argument("-o", "--outfile", type=str, help="Output file name", default="sqm.csv")

    args = vars(ap.parse_args())

    file_names = args['file']
    output_file_name = args['outfile']

    print("Converting", file_names)

    # Collect the data into a pandas dataframe
    columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain", "IntTime"]
    dfs = [pd.read_csv(file_name, sep=' ', names=columns)
           for file_name in file_names]
    df = pd.concat(dfs, ignore_index=True)

    # Check that the file length is long enough for the rolling average step size
    if STEP_SIZE > int(len(df["Lux"]) / 2) :
        STEP_SIZE = int(len(df["Lux"]) / 2)

    # Format the times into datetime values
    # times = pd.to_datetime(df.Date + " " + df.Time,
    #                        format="%Y/%m/%d %H:%M:%S.%f")

    df["Rolling"] = df.Lux.rolling(STEP_SIZE, center=True).mean()
    df = df.iloc[::STEP_SIZE, :]
    df["SQM"] = np.log10(df["Rolling"]/108000)/-0.4
    df = df.dropna(how='any')
    print(df)

    df[['Date', 'Time', "Rolling"]].to_csv('lux.csv', index=False)
    df[['Date', 'Time', "SQM"]].to_csv(output_file_name, index=False)


    # Try using visible+IR sensor values
    # Luminous efficacy at 5800 K
    LUM_EFFICACY = 0.0079 # 1 lux in W/m^2

    # Re irradiance responsivity from TSL2591 datasheet, white light on "visible" sensor channel 0
    # The 100 scaling factor is to convert the RE_WHITE_CHANNEL0 from the datsheet units of counts/(μW/cm2) to counts/(W/m2)
    RE_WHITE_CHANNEL0 = 264.1 * 100
    TSL2591_LUX_DF = 408.0
    TSL2591_LUX_COEFC = 0.59

    # High gain factor 428x from https://github.com/adafruit/Adafruit_CircuitPython_TSL2591/blob/main/adafruit_tsl2591.py
    GAIN_HIGH = 428

    dfs = [pd.read_csv(file_name, sep=' ', names=columns)
           for file_name in file_names]
    df = pd.concat(dfs, ignore_index=True)

    cpl = (df.IntTime * df.Gain) / TSL2591_LUX_DF

    # df["lux2"] = ((TSL2591_LUX_COEFC * df.Visible)) / cpl
    df["lux2"] = df.Visible / cpl

    """
    gain_scaling = np.array(df["Gain"].values, dtype=float)/GAIN_HIGH

    # Get watts/m2 from visible data
    visible_data = np.array(df["Visible"].values, dtype=float)
    watts_per_square_meter = visible_data/(RE_WHITE_CHANNEL0*gain_scaling)

    # Compute the lux from visible data
    df["lux_data_with_ir"] = watts_per_square_meter/LUM_EFFICACY
    """

    # df["Rolling"] = df.lux_data_with_ir.rolling(STEP_SIZE, center=True).mean()
    df["Rolling"] = df.lux2.rolling(STEP_SIZE, center=True).mean()
    df = df.iloc[::STEP_SIZE, :]
    df["SQM"] = np.log10(df["Rolling"]/108000)/-0.4
    df = df.dropna(how='any')
    print(df)

    df[['Date', 'Time', "SQM"]].to_csv('sqm_with_ir.csv', index=False)

