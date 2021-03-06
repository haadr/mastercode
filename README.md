# mastercode

All code (but not the dataset) necessary to reproduce the machine learning results from the master's thesis: Drews, Haakon. “Classification of Error Types in Physiotherapy Exercises,” 2017. https://www.duo.uio.no/handle/10852/56891.

What follows is an overview of functionality and data flow. For more details please refer to the usage instructions of the different components by passing the --help argument. See the examples folder for examples of the file structure layout. Note: the example csv files do not contain real exercises or error types.

## Main flow and functionality

- Record the sensor data for each sample and save it to a CSV file. 
- Calculate the distance between each sample using DTW
- Generate confusion matrices
- Visualize the recorded motion data in a very simple way (real-time and playback of csv files)

## Requirements

Tested on Linux only.

Main requirements are

- [MyoDbus](https://github.com/haadr/myodbus)
- [fastdtw](https://github.com/slaypni/fastdtw)
- [vPython](http://vpython.org/)

## Motion capture

**Message bus**

- message_bus.py

**Sensor clients**

- myo_client.py
- readLP.c

**Data consumers**

- capture_motion_client.py
- visualizer.py

**Data flow**

- A message bus is run which the other components use to interface.
- For each type of sensor used, a client is run which forwards the motion data from the sensor to the message bus. Contains clients for the Myo and LPMS-B sensors.
- To record the sensor data, a recording client is connected to the message bus which receives all sensor data and saves it to a CSV file in an appropriate folder structure.
- The visualizer can be connected to the message bus to make sure the motion data is received correctly in real-time.

## Data processing

- Having recorded all samples, calc_dtw.py is used to calculate all DTW distances between the samples. A pickle containing the processed data set is saved to a file.

```
./calc_dtw.py --help
usage: calc_dtw.py [-h] [-d {quaternion,euclidean}] [-t DATA_TYPE] [-V]
                   [-i SENSOR_ID_CATEGORY]
                   [-r [SENSORS_REQUIRED [SENSORS_REQUIRED ...]]] [-j JOBS]

Calculate all distances between samples in the current directory

optional arguments:
  -h, --help            show this help message and exit
  -d {quaternion,euclidean}, --dist-type {quaternion,euclidean}
                        Either 'quaternion' (default) or 'euclidean'.Note that
                        the quaternion distance function will likely throw
                        weird errors for anything but quaternions.
  -t DATA_TYPE, --data-type DATA_TYPE
                        Must be the same as the column label in the data files
                        used (for example 'quat')
  -V, --verbose         Be verbose
  -i SENSOR_ID_CATEGORY, --sensor-id SENSOR_ID_CATEGORY
                        The name of the csv column in the CSV input file
                        containing the sensor id. Default is 'id'
  -r [SENSORS_REQUIRED [SENSORS_REQUIRED ...]], --required-sensors [SENSORS_REQUIRED [SENSORS_REQUIRED ...]]
                        List of required sensors. If specified, will abort if
                        a required sensor is missing from input data
  -j JOBS, --jobs JOBS  Number of jobs to run concurrently
```

- Using the exported data set file, data_tester.py is used to classify each sample using the k-nearest-neighbor algorithm and generate confusion matrices. 

```
./data_tester.py --help
usage: data_tester.py [-h] [-s [SENSORS [SENSORS ...]]] [-k KNEIGHBORS]
                      [--class-type {exercise,mode}] [-t DATA_TYPE]
                      [-l {all,exact}] [-d DPI] [-V] [--save] [--show]
                      inputfile

Generate confusion matrices and classify using k-NN

positional arguments:
  inputfile             Pickle file generated by calc_all_dtw.py containing an
                        ExerciseRecordingDataSet

optional arguments:
  -h, --help            show this help message and exit
  -s [SENSORS [SENSORS ...]], --sensors [SENSORS [SENSORS ...]]
                        List of required sensors to combine for kNN matching.
                        If not specified, combine all available.
  -k KNEIGHBORS, --kneighbors KNEIGHBORS
                        Number of neighbors to use for majority voting matches
  --class-type {exercise,mode}
                        'exercise' for classification by exercise or 'mode'
                        for classification by error type
  -t DATA_TYPE, --data-type DATA_TYPE
                        Data type to use
  -l {all,exact}, --leave-me-out {all,exact}
                        set leaveMeOut scheme. Must be 'all' (leave out all
                        with same tsID) or 'exact' (leave out all with same
                        tsID and same exercise)
  -d DPI, --dpi DPI     Set DPI for the saved figure
  -V, --verbose         enable verbose mode
  --save                save figure to file
  --show                show figure
```

### Screenshots 

![Visualizer](https://gitlab.com/haadr/mastercode/uploads/ecac4be3a3125db4cdf0b31b7ea0853a/visualizer_example.png)
![Confusion matrix](https://gitlab.com/haadr/mastercode/uploads/66aef24e7961972d0b2a2a969481f7da/confusion_matrix.png)