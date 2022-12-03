
import argparse
import pandas as pd
from matplotlib import pyplot as plt

# construct the argument parser and parse the arguments

ap = argparse.ArgumentParser(description='Analyse radiometer data')
ap.add_argument("file", type=str, help="File or directory to analyse.")
ap.add_argument("-n", "--night", action='store_true', help="Display with night readings range")

args = vars(ap.parse_args())

file_name = args['file']
night_range = args['night']

print(file_name)

columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain"]
df = pd.read_csv(file_name, sep=' ', names=columns)

times = pd.to_datetime(df.Time)

print("Contents in csv file:")
print(df)
plt.plot(times, df.Lux)
plt.xlabel('Time')
plt.ylabel('Lux')
if night_range:
    plt.ylim(-0.1, 0.5)

plt.show()