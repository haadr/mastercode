import ast
import csv
import math
import re
import time


def dprint(*args, verbose=False, **kwargs):
    if verbose:
        print(*args, **kwargs)


def number_of_distances(number_of_sequences):
    """ Return the number of distances we need to calculate, or jobs required, given the number of input data sequences. """
    return math.factorial(number_of_sequences)/(math.factorial(2)*math.factorial(number_of_sequences-2))


def strftime_elapsed(seconds):
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return "{:0>2.0f}:{:0>2.0f}:{:0>5.2f}".format(hours, minutes, seconds)


def show_progress(title, total, current, starting_time, verbose=False):
    now = time.time()
    jobs_left = total - current
    time_elapsed = now - starting_time
    seconds_per_job = (time_elapsed/current)
    jobs_per_second = current / time_elapsed
    seconds_left = jobs_left / jobs_per_second
    done_at = time.localtime(now + seconds_left)

    progress_string = ("\r{}{:15} [{:.2f}%]: Jobs [{}/{}] sec/job: [{}] Time left: [{}] Done at [{}]"
                       .format("\r" if not verbose else "",
                               title,
                               (current/total)*100, current, total,
                               strftime_elapsed(seconds_per_job),
                               strftime_elapsed(seconds_left),
                               time.strftime("%H:%M:%S", done_at)
                               ))

    print(progress_string, end='\n' if current == total else '')


def getParametersFromFilename(filename):
    try:
        matches = re.search('(\A[^\W\d_]+)_([0-9]+)_([0-9]+) - (.+).csv$', filename)
        matches = matches.groups() if matches else None
        if not matches or len(matches) is not 4:
            return False
        return {'exercise_name': matches[0],
                'mode': matches[1],
                'sample_number': matches[2],
                'timestamp': matches[3]}

    except Exception as e:
        print("Exception {} trying to get parameters from filename {}".format(e, filename))
        return False


def readExerciseCSV(file_info, verbose=False, sensor_id_category='id', data_types=None, quat_type=None, quat_order="WXYZ"):
    """
    Parses an CSV file containing sensor data. The filename must be of the format "exercise_name_mode_num<arbitrary>.csv", where mode and num must be numbers. See the regex below for details.

    :param file_info: must be a dictionary and contain at least 'filepath' and 'tsID' . Optionally also contains exercise_name, mode and sample_number
    :param verbose: Boolean
    :param id_category: The name of the category indicating the corresponding line's sensor
    :param data_types: Which data types to save. If None (default), save all.
    :param quat_type: The name of the quaternion category. Used in conjunction with quat_order.
    :param quat_order: Quaternion order the input file uses. This will be used to re-order the quaternions to "WXYZ".
    :returns: Returns a dict containing this file's parameters and sensor data index by sensorID or None if something went wrong.
    """

    tsID     = file_info['tsID']
    filepath = file_info['filepath']

    if quat_order.upper() is not "WXYZ" and quat_type is not None:
        convert_quat = True
        quat_order = quat_order.upper()
        w_i = quat_order.index("W")
        x_i = quat_order.index("X")
        y_i = quat_order.index("Y")
        z_i = quat_order.index("Z")
    else:
        convert_quat = False

    required_keys = set(['sample_number', 'mode', 'exercise_name', 'timestamp'])
    if len(required_keys.intersection(file_info.keys())) == len(required_keys):
        exercise_name = file_info['exercise_name']
        mode          = file_info['mode']
        sample_number = file_info['sample_number']
        timestamp     = file_info['timestamp']
    else:
        print("Missing entries from required file_info argument.")
        return None

    csvReader = None
    try:
        inputcsv = open(filepath, 'r')
        csvReader = csv.DictReader(inputcsv,
                                   skipinitialspace=True,
                                   delimiter=',',
                                   quotechar='|')

    except NameError as e:
        print("Error opening input file: {}".format( e))
        return None

    sensors = {}

    for row in csvReader:
        sensor_id = row[sensor_id_category]
        if sensor_id not in sensors:
            sensors[sensor_id] = {}
        for category in row:
            if category == sensor_id_category:
                continue

            try:
                data = ast.literal_eval(row[category])
            except:
                print("readExerciseCSV: Failed to eval data {} in file {} on column {}"
                      .format(filepath, row[category], category))
                return None

            if convert_quat and category == quat_type:
                data = [ data[w_i], data[x_i], data[y_i], data[z_i] ]

            if category not in sensors[sensor_id]:
                sensors[sensor_id][category] = []

            sensors[sensor_id][category].append(data)

    inputcsv.close()
    return {"tsID": tsID,
            "exercise_name": exercise_name,
            "mode" : mode,
            "sample_number" : sample_number,
            "timestamp": timestamp,
            "sensors" : sensors}
