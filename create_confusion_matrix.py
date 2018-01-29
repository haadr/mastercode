#!/usr/bin/python3
from master_utils import dprint

import numpy as np
import sys


def nearest_neighbour(sample, classify_by=None, data_type="quat", sensors=[], k_neighbours=1, leave_me_out=None):
    """ Classify an exercise recording using k-NN """
    choices = set()
    for sensor in sensors:

        # We only look for quat sequences, one per sensor
        data_sequence = sample.sensors[sensor][data_type]
        costs = data_sequence.costs

        votes = {}
        sub_winner = None
        sub_score = 0

        # Find the winner for this sensor's data sequence
        i = 0
        for entry in costs:
            other_sample = entry[1]
            # Crown winner if done
            if i+1 > k_neighbours:
                for candidate in votes:
                    if votes[candidate] > sub_score:
                        sub_winner = candidate
                        sub_score = votes[candidate]

                if sub_winner and sub_winner not in choices:
                    choices.add(sub_winner.exercise_recording)
                break

            # Only consider this candidate if not excluded due to leave_me_out options
            if not leave_me_out:
                # print("Valid!")
                i += 1
            elif leave_me_out and other_sample.tsID == data_sequence.tsID:
                # print("Checking legality of {}".format(other_sample))
                if ((leave_me_out == "all") or
                   (classify_by == "exercise" and other_sample.exercise == data_sequence.exercise) or
                   (classify_by == "mode" and other_sample.mode == data_sequence.mode)):
                    continue
                else:
                    i += 1

            # Add one of the k-closest candiates
            if other_sample not in votes:
                votes[other_sample] = 1
            else:
                votes[other_sample] += 1

    if len(choices) == 1:
        return choices.pop()
    elif len(choices) == 0:
        return None

    cost = None
    winner = 0
    for choice in choices:
        sub_cost = 0
        for sensor in sensors:
            sub_cost += sample.sensors[sensor][data_type].get_cost(choice.sensors[sensor][data_type])
        if cost is None or sub_cost < cost:
            cost = sub_cost
            winner = choice
        elif sub_cost < cost:
            cost = sub_cost
            winner = choice

    return winner


def create_confusion_matrix(exercise_recording_data_set,
                            sensors=[],
                            classify_by='exercise',
                            data_type='quat',
                            k_neighbours=1,
                            leave_me_out=None,
                            verbose=False):

    if classify_by == "exercise":
        m_classes = exercise_recording_data_set.get_exercises()
        m_classes.sort()
    elif classify_by == "mode":
        m_classes = exercise_recording_data_set.get_modes()
        m_classes.sort()
    else:
        print("Unknown class to classify by! Aborting.")
        return None

    if len(sensors) == 0:
        sensors = exercise_recording_data_set.get_sensors()

    dimensions = { 'x': len(m_classes) + 2, 'y': len(m_classes) + 1 }
    confusion_matrix = np.zeros((dimensions['y'], dimensions['x']))

    samples = exercise_recording_data_set.get_exercise_recordings(sensors=sensors, data_types=[data_type], has_costs=True)

    dprint("", verbose=verbose)
    validation = "leave-1-out" if not leave_me_out else leave_me_out
    dprint("Generating confusion matrix with k-NN.\n"
           "Classify by [{}]\n"
           "Data type   [{}]\n"
           "k-paramter  [{}]\n"
           "Validation  [{}]\n"
           "Samples     [{}]\n"
           .format(classify_by, data_type, k_neighbours, validation, len(samples)), verbose=verbose)

    if len(samples) < 3:
        print("Error: Too few samples to run k-NN. Have {} samples.".format(len(samples)))
        return None

    # Classify every sample
    for sample in samples:
        # Majority vote on top n samples
        sample.predicted = nearest_neighbour(sample,
                                             data_type=data_type,
                                             classify_by=classify_by,
                                             leave_me_out=leave_me_out,
                                             sensors=sensors,
                                             k_neighbours=1)

        if not sample.predicted:
            print("Failed to classify {} - check validation scheme and dataset".format(sample.full_name))
            continue

        if classify_by == "exercise":
            actual = sample.exercise
            predicted = sample.predicted.exercise
        elif classify_by == "mode":
            actual = sample.mode
            predicted = sample.predicted.mode
        else:
            print("ERROR: INVALID classify_by {}".format(classify_by))
            sys.exit(1)

        actual_i = m_classes.index(actual)
        predicted_i = m_classes.index(predicted)

        # Count predicted
        confusion_matrix[actual_i][predicted_i] += 1
        confusion_matrix[-1][predicted_i] += 1

        # Count actual
        confusion_matrix[actual_i][-2] += 1

        # Count total
        confusion_matrix[-1][-2] += 1

    # Calculate average accuracies
    for i,m_class in enumerate(m_classes):
        if confusion_matrix[i][-2] > 0:
            avg_accuracy = confusion_matrix[i][i] / confusion_matrix[i][-2]
        else:
            avg_accuracy = 0

        confusion_matrix[i][-1] = avg_accuracy * 100
    # Total average accuracy
    a = sum([ confusion_matrix[i][-1] for i in range(dimensions['y']) ]) / len(m_classes)
    confusion_matrix[-1][-1] = a

    dprint("{}".format(confusion_matrix), verbose=verbose)
    return confusion_matrix
