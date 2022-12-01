
import argparse
import pandas as pd
from matplotlib import pyplot as plt

# construct the argument parser and parse the arguments

ap = argparse.ArgumentParser(description='Analyse radiometer data')
ap.add_argument("file", type=str, help="File or directory to analyse.")
args = vars(ap.parse_args())

file_name = args['file']
print(file_name)

columns = ["Date", "Time", "Lux", "Visible", "IR", "Gain"]
df = pd.read_csv(file_name, sep=' ', names=columns)

times = pd.to_datetime(df.Time)

print("Contents in csv file:")
print(df)
plt.plot(times, df.Lux)
plt.xlabel('Time')
plt.ylabel('Lux')

plt.show()