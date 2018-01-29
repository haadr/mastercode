#!/usr/bin/python3
import argparse
import datetime
import functools
import multiprocessing as mp
import numpy as np
import os
import pickle
import re
import sys
import time

from fastdtw import fastdtw

from master_utils import (dprint,
                          number_of_distances,
                          show_progress,
                          strftime_elapsed,
                          readExerciseCSV,
                          getParametersFromFilename)
from exercise_recording_data import DataSequence, ExerciseRecording, ExerciseRecordingDataSet


def euclidean_distance(q,p):
    if(q[0] == p[0] and
       q[1] == p[1] and
       q[2] == p[2] and
       q[3] == p[3]):
        return 0

    return np.linalg.norm(q-p)


def quaternion_distance(q,p):
    if(q[0] == p[0] and
       q[1] == p[1] and
       q[2] == p[2] and
       q[3] == p[3]):
        return 0
    i = 2 * ((np.inner(q,p))**2) - 1
    if( i <= 1 and i >= -1):
        return np.arccos(i)
    else:
        i = round(i,1)
        if( i <= 1 and i >= -1):
            return np.arccos(i)
        else:
            print("Unknown value error in distfunc for \nq={}\np={}\ni={}".format(q,p,i))
            raise Exception


def get_dtw_jobs(quat_sequences_by_sensor, distfunc):
    """ Generate DTW jobs consumed by compute_dtw_job """
    # For every sensor's sequence
    for s,quat_sequence in enumerate(quat_sequences_by_sensor):
        for i, sequence_1 in enumerate(quat_sequence):
            # Compare it to every other sequence for this sensor
            for j, sequence_2 in enumerate(quat_sequence[i+1:]):
                yield {"s": s,
                       "i": i,
                       "j": j,
                       "sequence_1": sequence_1,
                       "sequence_2": sequence_2,
                       "distfunc": distfunc}


def compute_dtw_job(job):
    sequence_1 = job['sequence_1']
    sequence_2 = job['sequence_2']
    s = job['s']
    i = job['i']
    j = job['j']
    distfunc = job["distfunc"]
    dist,path = fastdtw(sequence_1.data, sequence_2.data, dist=distfunc)

    result = {}
    result['s'] = s
    result['i'] = i
    result['j'] = j
    result['cost'] = dist

    return result


def save_parsed_exercise_recording(parsed_er, verbose=False, sensors_required=None):
        tsID = parsed_er["tsID"]
        exercise_name = parsed_er["exercise_name"]
        mode = parsed_er["mode"]
        sample_number = parsed_er["sample_number"]
        timestamp = parsed_er["timestamp"]
        sensors = parsed_er["sensors"]

        if sensors_required is not None:
            for sensor in sensors_required:
                if sensor not in sensors:
                    dprint("Required sensor {} not in {}, skipping"
                           .format(sensor,
                                   "_".join([tsID, exercise_name, mode, sample_number, timestamp])),
                           verbose=verbose)
                    return None
        exercise_object = ExerciseRecording(tsID, exercise_name, mode, sample_number, timestamp, sensors)
        return exercise_object


def traverse_data_files(verbose=False):
    """ Scan this directory for directories names tsX, where X is a number. """
    files = []
    cwd = os.getcwd()
    dprint("\nScanning for valid sensor data CSV files recursively from {}".format(cwd), verbose=verbose)

    for dirpath, dirnames, filenames in os.walk(cwd):
        dirs = dirnames[:]
        for d in dirs:
            if d[:2] != "ts":
                dirnames.remove(d)

        tsID_groups = re.search('ts([0-9]+$)', dirpath)
        tsID_groups = tsID_groups.groups() if tsID_groups else None

        if tsID_groups is None:
            dprint("Skipping incorrectly named directory {}".format(dirpath), verbose=verbose)
            continue

        tsID = tsID_groups[0]
        filenames.sort()

        for f in filenames:
            if f[-4:] != ".csv":
                continue

            matches = getParametersFromFilename(f)
            if not matches:
                dprint("File {} incorrectly named, skipping".format(f), verbose=verbose)
                continue

            file_info = {'filepath': os.path.join(dirpath, f),
                         'filename': f,
                         'tsID': tsID,
                         'exercise_name': matches['exercise_name'],
                         'mode': matches['mode'],
                         'sample_number': matches['sample_number'],
                         'timestamp': matches['timestamp']}
            files.append(file_info)
            dprint("\t Using {}".format(dirpath + "/" + f), verbose=verbose)

    dprint(verbose=verbose)
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate all distances between samples in the current directory')
    parser.add_argument('-d', '--dist-type', choices=["quaternion", "euclidean"],
                        default="quaternion", help="Either 'quaternion' (default) or 'euclidean'."
                        "Note that the quaternion distance function will likely throw weird errors for anything but quaternions.")

    parser.add_argument('-t', '--data-type', default="quat",
                        help="Must be the same as the column label in the data files used (for example 'quat')")

    parser.add_argument('-V', '--verbose', action="store_true", default=False, help="Be verbose")
    parser.add_argument('-D', '--debug', action="store_true", default=False,
                        help="After calculating all distances, print out the three closest distance for each sample")

    parser.add_argument('-i', '--sensor-id', dest="sensor_id_category", default='id',
                        help="The name of the csv column in the CSV input file containing the sensor id. Default is 'id'")

    parser.add_argument('-r', '--required-sensors', dest="sensors_required", default=None, nargs='*',
                        help="List of required sensors. If specified, will abort if a required sensor "
                        "is missing from input data")

    parser.add_argument('-j', '--jobs', default=os.cpu_count(), type=int, help="Number of jobs to run concurrently")
    args = parser.parse_args()

    if args.sensors_required:
        sensors_required = args.sensors_required
        dprint("Required sensors: {}".format(sensors_required), verbose=args.verbose)
    else:
        dprint("Using all available sensors", verbose=args.verbose)

    if args.dist_type == "quaternion":
        distfunc = quaternion_distance
        dprint("Using quaternion distance function", verbose=args.verbose)
    elif args.dist_type == "euclidean":
        dprint("Using euclidean distance function", verbose=args.verbose)
        distfunc = euclidean_distance

    np.seterr(all='raise')
    dprint("Using {} processes.".format(args.jobs), verbose=args.verbose)

    # Contains all sensor data for all exercise recordings
    exercise_recording_data_set = ExerciseRecordingDataSet()

    # Find files to parse
    files = traverse_data_files(verbose=args.verbose)
    if len(files) < 3:
        print("Found {} valid files to parse. Please run again with the verbose flag -V.".format(len(files)))
        sys.exit(1)

    dprint("Parsing {} files".format( len(files) ), verbose=args.verbose)

    # Parse all files
    parsed_data = []
    with mp.Pool(processes=args.jobs) as pool:
        start_time = time.time()
        short_func = functools.partial(readExerciseCSV,
                                       sensor_id_category=args.sensor_id_category,
                                       verbose=args.verbose)
        parsed_it = pool.imap_unordered(short_func, files)

        for i, res in enumerate(parsed_it):
            if res is None:
                print("Error occurred while trying to parse files")
                pool.terminate()
                pool.join()
                sys.exit(1)

            parsed_data.append(res)
            show_progress("Parsing files", len(files), i+1, start_time)

        end_time = time.time()
        pool.close()
        pool.join()


    if len(parsed_data) < 3:
        print("Parsed {} files. Please run again with the verbose flag -V.".format(len(files)))
        sys.exit(1)

    # Save parsed sensor data to ExerciseRecordingDataSet
    with mp.Pool(processes=args.jobs) as pool:
        start_time = time.time()
        short_func = functools.partial(save_parsed_exercise_recording,
                                       verbose=args.verbose,
                                       sensors_required=args.sensors_required)
        exercise_recordings_it = pool.imap_unordered(short_func, parsed_data)

        for i, res in enumerate(exercise_recordings_it):
            exercise_recording_data_set.add(res, verbose=args.verbose)
            show_progress("Saving data", len(parsed_data), i+1, start_time, verbose=args.verbose)

        end_time = time.time()
        pool.close()
        pool.join()

    # Aggregate data we're interested in computing distances for for each sensor
    data_sequences_by_sensor = []
    sensors = exercise_recording_data_set.get_sensors()
    for sensor in sensors:
        data_sequences = exercise_recording_data_set.get_data_sequences(data_types=[args.data_type], sensors=[sensor])
        if len(data_sequences) == 0:
            print("Sensor {} is missing data type '{}', skipping".format(sensor, args.data_type))
            continue
        data_sequences_by_sensor.append(data_sequences)
        # FIXME Slow?
        [ds.prepare_cost_array(len(data_sequences) - 1) for ds in data_sequences]

    if len(data_sequences_by_sensor) == 0:
        print("No data found for type {} for sensors {}".format(args.data_type, ", ".join(args.sensors_required)))
        sys.exit(0)

    num_jobs = int(sum( [ number_of_distances(len(dss)) for dss in data_sequences_by_sensor] ))

    dprint("\nTotal number of '{}' sequences: {}"
           .format(args.data_type, sum([len(dss) for dss in data_sequences_by_sensor])), verbose=args.verbose)
    dprint("Jobs generated: {}\n".format(num_jobs), verbose=args.verbose)

    # Prepare efficient arrays for jobs and results?
    job_dt = np.dtype( {'names': ["s", "i", "j", "sequence_1", "sequence_2", "distfunc"],
                        'formats': ['int', 'int', 'int', DataSequence, DataSequence, 'object_']} )
    jobs_all = np.full(num_jobs, float('Inf'), dtype=job_dt)

    for i, job in enumerate(get_dtw_jobs(data_sequences_by_sensor, distfunc)):
        for name in job_dt.names:
            jobs_all[i][name] = job[name]

    result_dt = np.dtype( {'names': ["s", "i", "j", "cost"],
                           'formats': ['int', 'int', 'int', 'float64']} )

    start_time = time.time()
    end_time = 0
    results_all = []
    with mp.Pool(processes=args.jobs) as pool:
        results_it = pool.imap_unordered(compute_dtw_job, jobs_all)
        for i, res in enumerate(results_it):
            results_all.append(res)
            show_progress("DTW", num_jobs, i+1, start_time)

        end_time = time.time()
        pool.close()
        pool.join()

    print("Done with DTW after {} at {}"
          .format(strftime_elapsed(end_time - start_time), time.strftime("%H:%M:%S", time.localtime(time.time()))))

    # Handle results: populate cost array for every DataSequence
    for result in results_all:
            # result = resultQueue.get()
            s = result["s"]
            i = result["i"]
            j = result["j"]
            cost = result["cost"]

            sequence_1 = data_sequences_by_sensor[s][i]
            sequence_2 = data_sequences_by_sensor[s][i+j+1]

            # Set distance for both sequences
            sequence_1.costs[i+j][0] = cost
            sequence_1.costs[i+j][1] = sequence_2

            sequence_2.costs[i][0] = cost
            sequence_2.costs[i][1] = sequence_1

    for data_sequences in data_sequences_by_sensor:
        for data_sequence in data_sequences:
            data_sequence.order_costs()
            data_sequence.index_cost_by_data_sequence_object()

    # Save complete exercise structure
    pickledir = "pickles"
    if not os.path.exists(pickledir):
        os.makedirs(pickledir)

    isotime = datetime.datetime.now().isoformat()
    exercise_recordings_file = pickledir + '/exercise_recording_data_set_' + args.dist_type + "_" + isotime + '.pickle'
    with open(exercise_recordings_file, "wb") as pf:
            # Pickle the 'data' dictionary using the highest protocol available.
            pickle.dump(exercise_recording_data_set, pf, pickle.HIGHEST_PROTOCOL)
            dprint("Saved {}".format(exercise_recordings_file), verbose=True)

    if args.debug:
        print("\First three closest distances for each sample ::")
        for data_sequences in data_sequences_by_sensor:
            data_sequences.sort()
            for quat_sequence in data_sequences:
                print('{:<25}->'.format(quat_sequence.full_name), end='')
                # print first 3 costs
                # for cost in qs.costs:
                for i in range(3):
                    cost = quat_sequence.costs[i]
                    try:
                        formatted = '{:>10} ({:>6.2f})'.format(cost[1].full_name, cost[0])
                        print('{:>35} || '.format(formatted), end='')
                    except:
                        print("Error on: {}".format(cost), end='')
                print("")
