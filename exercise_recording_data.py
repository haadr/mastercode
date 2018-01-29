import numpy as np


def print_data_set_info(data_set):
    sensors = data_set.get_sensors()
    print("--------------------------------------------------------------------------------")
    print("Data set info:")
    print("\nExercises:                    {}".format(data_set.get_exercises()))
    print("Modes:                        {!r}".format(data_set.get_modes()))
    print("tsIDs:                        {!r}".format(data_set.get_tsIDs()))
    print("Data sequences:               {!r}".format(len(data_set.get_data_sequences())))
    print("Sensors:                      {!r}".format(sensors))
    print("Data types:                   {!r}\n".format(data_set.get_data_types()))
    sensor_contents = {}
    for sensor in sensors:
        sensor_contents[sensor] = {}
        data_sequences = data_set.get_data_sequences(sensors=[sensor])
        for ds in data_sequences:
            if ds.data_type not in sensor_contents[sensor]:
                sensor_contents[sensor][ds.data_type] = None
                # Only say a sensor's data has cost if ALL of this sensor's data
                # has costs set
                if ds.costs is not None:
                    if sensor_contents[sensor][ds.data_type] is None:
                        sensor_contents[sensor][ds.data_type] = True
                    else:
                        sensor_contents[sensor][ds.data_type] = False

    for sensor in sensor_contents:
        print("Sensor {}'s data:".format(sensor))
        for data_type in sorted(list(sensor_contents[sensor].keys())):
            if sensor_contents[sensor][data_type]:
                print("  {:<10} with cost".format(data_type))
            else:
                print("  {:<10} without cost".format(data_type))
    print("--------------------------------------------------------------------------------")


class DataSequence:
    def __init__(self, exercise_recording, tsID, exercise, mode, sample_number, sensor, data_type, timestamp, data):

        self.full_name = "_".join([tsID, exercise, mode, sample_number, sensor, data_type])
        self.exercise_recording = exercise_recording
        self.tsID = tsID
        self.exercise = exercise
        self.mode = mode
        self.sample_number = sample_number
        self.sensor = sensor
        self.data_type = data_type
        self.data = data
        self.timestamp = timestamp

        self.cost_dt = np.dtype( {'names': ["cost", "data sequence object"], 'formats': ['float64', 'object_']} )
        self.costs = None
        self.costs_by_data_sequence_object = {}
        self.num_costs = 0

    def order_costs(self):
        np.ndarray.sort(self.costs, order='cost')

    def index_cost_by_data_sequence_object(self):
        for entry in self.costs:
            self.costs_by_data_sequence_object[entry[1]] = entry[0]

    def get_cost(self, data_sequence_object):
        if not self.costs_by_data_sequence_object:
            self.index_cost_by_data_sequence_object()

        if data_sequence_object in self.costs_by_data_sequence_object:
            return self.costs_by_data_sequence_object[data_sequence_object]
        else:
            print("get_cost() error: {} doesn't have cost for {}".format(self, data_sequence_object))
            return None

    def __repr__(self):
        return ("<DataSequence {}, Name: {!r},Sensor: {!r}, Data type: {!r}, Data size: {!r}, Data[0]: {!r}>"
                .format(hex(id(self)), self.full_name, self.sensor, self.data_type, len(self.data), self.data[0]))

    def info(self):
        return str("Name:              {}\n"
                   "tsID               {}\n"
                   "exercise           {}\n"
                   "mode               {}\n"
                   "sample_number      {}\n"
                   "sensor             {}\n"
                   "data type          {}\n"
                   "exercise_recording {}\n"
                   .format(self.full_name,
                           self.tsID,
                           self.exercise,
                           self.mode,
                           self.sample_number,
                           self.sensor,
                           self.data_type,
                           self.exercise_recording))

    def prepare_cost_array(self, size, dt=None):
        if dt is None:
            dt = self.cost_dt
        self.costs = np.full(size, float('Inf'), dtype=dt)

    def __hash__(self):
        return hash(id(self))

    def __lt__(self, other):
        return self.full_name < other.full_name

    def __le__(self, other):
        return self.full_name <= other.full_name

    def __eq__(self, other):
        return self.full_name == other.full_name

    def __ne__(self, other):
        return self.full_name != other.full_name

    def __gt__(self, other):
        return self.full_name > other.full_name

    def __ge__(self, other):
        return self.full_name >= other.full_name


class ExerciseRecording:
    """ One sensor recording """
    def __init__(self, tsID, exercise, mode, sample_number, timestamp, input_data):
        self.tsID = tsID
        self.exercise = exercise
        self.mode = mode
        self.sample_number = sample_number
        self.timestamp = timestamp

        # Every DataSequence object by sensor, then by data_type
        self.sensors = {}

        # Every DataSequence object by data_type, then by sensor
        self.data_types = {}

        # Every DataSequence() object
        self.data_sequences = []

        self.full_name = "_".join([tsID, exercise, mode, sample_number])

        for sensor in input_data:
            if sensor not in self.sensors:
                self.sensors[sensor] = {}

            for data_type in input_data[sensor]:
                if data_type not in self.data_types:
                    self.data_types[data_type] = {}
                    if sensor not in self.data_types[data_type]:
                        self.data_types[data_type][sensor] = None
                    if data_type not in self.sensors[sensor]:
                        self.sensors[sensor][data_type] = None

                new_data_sequence = DataSequence(self,
                                                 tsID,
                                                 exercise,
                                                 mode,
                                                 sample_number,
                                                 sensor,
                                                 data_type,
                                                 timestamp,
                                                 input_data[sensor][data_type])
                self.data_sequences.append(new_data_sequence)
                self.data_types[data_type][sensor] = new_data_sequence
                self.sensors[sensor][data_type] = new_data_sequence

    def __hash__(self):
        return hash(self.full_name)

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __repr__(self):
        return ("<ExerciseRecording Name {!r}, Sensors {!r}, Data types {!r}, Sequences {!r}>".format(self.full_name, self.sensors, self.data_types, self.data_sequences))

    def __str__(self):
        return ("<ExerciseRecording Name {!r}>".format(self.full_name))


class ExerciseRecordingDataSet:
    def __init__(self, exercise_recordings=None):
        self.exercise_recordings = {}
        if exercise_recordings is not None:
            for er in exercise_recordings:
                self.add(er)

    def add(self, exercise_recording, verbose=False):
        if exercise_recording is None:
            return

        if exercise_recording in self.exercise_recordings:
            if verbose:
                print("\n\nWarning: Trying to add exercise recording with pre-existing parameter combination {}, choosing oldest according to timestamp.\n"
                      .format(exercise_recording.full_name))
            if exercise_recording.timestamp > self.exercise_recordings[exercise_recording].timestamp:
                self.exercise_recordings[exercise_recording] = exercise_recording
        else:
            self.exercise_recordings[exercise_recording] = exercise_recording

    def get_exercise_recording_full_names(self):
        """ Return set of full names for all exercise recordings """
        full_names = set()
        for er in self.exercise_recordings:
            full_names.add(er.full_name)
        return full_names

    def get_sensors(self):
        """ Return list of sensors in this data set """
        sensors = set()
        for er in self.exercise_recordings:
            for sensor in er.sensors:
                if sensor not in sensors:
                    sensors.add(sensor)
        return list(sensors)

    def get_exercises(self):
        """ Return list of exercises in this data set """
        exercises = set()
        for er in self.exercise_recordings:
            if er.exercise not in exercises:
                exercises.add(er.exercise)
        return list(exercises)

    def get_modes(self):
        """ Return list of exercise modes in this data set """
        modes = set()
        for er in self.exercise_recordings:
            if er.mode not in modes:
                modes.add(er.mode)
        return list(modes)

    def get_tsIDs(self):
        """ Return list of test subjects in this data set """
        tsIDs = set()
        for er in self.exercise_recordings:
            if er.tsID not in tsIDs:
                tsIDs.add(er.tsID)
        return list(tsIDs)

    def get_data_types(self):
        """ Return list of all data types in this data set. Note that not all sensors might have the same data types! """
        data_types = set()
        for er in self.exercise_recordings:
            for data_type in er.data_types:
                if data_type not in data_types:
                    data_types.add(data_type)
        return list(data_types)

    def get_exercise_recordings(self, tsIDs=[], exercises=[], modes=[], sensors=[], data_types=[], has_costs=None):
        """ Returns a list of all exercise recordings filtered by the parameters given.  """
        exercise_recordings = []
        for er in self.exercise_recordings:
            if not ((er.tsID in tsIDs or len(tsIDs) == 0)                                    and
                    (er.exercise in exercises or len(exercises) == 0)                            and
                    (er.mode in modes or len(modes) == 0)                                    and
                    (len(set(sensors).intersection(set(er.sensors))) == len(sensors) or len(sensors) == 0) and
                    (len(set(data_types).intersection(set(er.data_types))) == len(data_types) or len(data_types) == 0)):
                continue

            cont = False
            if has_costs is not None:
                for ds in er.data_sequences:
                    if data_types is not None:
                        if ds.data_type in data_types and has_costs != (ds.costs is not None):
                            cont = True
                            break
                    elif data_types is None:
                        if (ds.costs is not None) != has_costs:
                            cont = True
                            break

            if cont:
                continue

            exercise_recordings.append(er)
        return exercise_recordings

    def get_data_sequences(self, tsIDs=[], exercises=[], modes=[], sensors=[], data_types=[], has_costs=None):
        """ Returns a list of all data sequences filtered by the parameters given. """
        data_sequences = []
        for er in self.exercise_recordings:
            if not ((er.tsID in tsIDs or len(tsIDs) == 0)                                    and
                    (er.exercise in exercises or len(exercises) == 0)                            and
                    (er.mode in modes or len(modes) == 0)                                    and
                    (len(set(sensors).intersection(set(er.sensors))) > 0 or len(sensors) == 0) and
                    (len(set(data_types).intersection(set(er.data_types))) > 0 or len(data_types) == 0)):
                continue

            for ds in er.data_sequences:
                if not ((ds.sensor in sensors or len(sensors) == 0) and
                        (ds.data_type in data_types or len(data_types) == 0) and
                        (has_costs is None or (has_costs == (ds.costs is not None)))):
                    continue
                data_sequences.append(ds)

        return data_sequences
