from datetime import datetime
import statistics
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import warnings
warnings.simplefilter("ignore")

###############
# Filtering & Sampling Params
###############
dht22_temp_stack = []
dht22_temp_stack_errors = 0
dht22_hum_stack = []
dht22_hum_stack_errors = 0

dht22_stack_size = 10
dht22_std_deviation = 3
dht22_error_count_stack_flush = 3

dht22mqtt_temp_unit = 'C'


###############
# Polling & Processing functions
###############
def getTemperatureJitter(temperature):
    return getTemperature(temperature-0.3), getTemperature(temperature+0.3)


def getTemperature(temperature):
    if(dht22mqtt_temp_unit == 'F'):
        temperature = temperature * (9 / 5) + 32
    return temperature


def getHumidity(humidity):
    return humidity


def processSensorValue(stack, error, value, value_type):
    # flush stack on accumulation of errors
    if(error >= dht22_error_count_stack_flush):
        stack = []
        error = 0

    # init stack
    if(len(stack) <= dht22_error_count_stack_flush):
        if(value not in stack):
            stack.append(value)
        # use jitter for bootstrap temperature stack
        if(value_type == 'temperature'):
            low, high = getTemperatureJitter(value)
            stack.append(low)
            stack.append(high)
        return stack, error, None

    # get statistics
    std = statistics.pstdev(stack)
    mean = statistics.mean(stack)

    # compute if outlier or not
    if(mean-std*dht22_std_deviation < value < mean+std*dht22_std_deviation):
        outlier = False
        if(value not in stack):
            stack.append(value)
        error = 0
    else:
        outlier = True
        error += 1

    # remove oldest element from stack
    if(len(stack) > 10):
        stack.pop(0)
    return stack, error, outlier


###############
# Dataset processing
###############
def timestampToSeconds(timestamp_begin, timestamp):
    b = datetime.fromtimestamp(timestamp_begin)
    e = datetime.fromtimestamp(timestamp)
    return (e-b).total_seconds()


def generatePlots(dataset, data_type):
    plot_rows = 5
    plot_columns = 5
    reduce_rate = 1
    for r in np.arange(plot_rows):
        for c in np.arange(plot_columns):
            temp_dataset = dataset.iloc[::reduce_rate, :]
            freq = dataset['timestamp'].mean()/len(temp_dataset.index)
            print('generating '+data_type+' plot from data with sampling frequency s='+str(freq)+'...')
            temp_dataset = processDataset(temp_dataset)
            axes[r, c].set_title(data_type + ' at sampling frequency '+str(round(freq, 2))+' (s)')
            sns.scatterplot(ax=axes[r, c], data=temp_dataset, x='timestamp', y=data_type, hue='type', s=10)
            # visualize stack flushes
            resets = temp_dataset[temp_dataset['reset'] == 'True']
            for key, row in resets.iterrows():
                plt.axvline(x=row['timestamp'], color='k', alpha=1, linewidth=0.3)
            reduce_rate += 1


def processDataset(dataset):
    dht22_temp_stack = []
    dht22_temp_stack_errors = 0
    dht22_hum_stack = []
    dht22_hum_stack_errors = 0
    dataset.loc[:, 'type'] = ''
    dataset.loc[:, 'reset'] = ''

    for key, row in dataset.iterrows():
        temperature = row['temperature']
        humidity = row['humidity']

        temp_data = processSensorValue(dht22_temp_stack,
                                       dht22_temp_stack_errors,
                                       temperature,
                                       'temperature')
        dht22_temp_stack = temp_data[0]
        dht22_temp_stack_errors = temp_data[1]
        temperature_outlier = temp_data[2]

        hum_data = processSensorValue(dht22_hum_stack,
                                      dht22_hum_stack_errors,
                                      humidity,
                                      'humidity')
        dht22_hum_stack = hum_data[0]
        dht22_hum_stack_errors = hum_data[1]
        humidity_outlier = hum_data[2]

        dataset.at[key, 'temperature_outlier'] = temperature_outlier
        dataset.at[key, 'humidity_outlier'] = humidity_outlier

        # record outlier detection source
        if(temperature_outlier and humidity_outlier):
            dataset.at[key, 'type'] = 'both outlier'
        elif(temperature_outlier):
            dataset.at[key, 'type'] = 'temperature outlier'
        elif(humidity_outlier):
            dataset.at[key, 'type'] = 'humidity outlier'
        else:
            dataset.at[key, 'type'] = 'accurate'
        # record reset pivots
        if(dht22_temp_stack_errors >= 3):
            dataset.at[key, 'reset'] = 'True'
        if(dht22_hum_stack_errors >= 3):
            dataset.at[key, 'reset'] = 'True'
    return dataset


dataset_dir = 'datasets/'
plots_dir = 'plots/'
filename = '2021-01-30T20-08-36Z_recording'
dataset = pd.read_csv(dataset_dir+filename+'.csv')
dataset['timestamp'] = np.vectorize(timestampToSeconds)(dataset['timestamp'][0], dataset['timestamp'])
print('formatted timestamps into seconds...')
fig, axes = plt.subplots(5, 5, figsize=(50, 25))
generatePlots(dataset, 'temperature')
plt.savefig(plots_dir+filename+'_temperature.png')
plt.clf()
fig, axes = plt.subplots(5, 5, sharex=True, figsize=(50, 25))
generatePlots(dataset, 'humidity')
plt.savefig(plots_dir+filename+'_humidity.png')
