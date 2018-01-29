#!/usr/bin/python2.7
from __future__ import print_function

import argparse
import ast
import csv
import json
import numpy
import socket
import struct
import sys
import threading
import time
import visual
import visual.text as vt


def axisAngleFromQuaternion(quat):
    v = visual.vector(0,0,0)
    angle = 2 * numpy.arccos( quat[0] )
    v.x = quat[1] / numpy.sin( angle / 2 )
    v.y = quat[2] / numpy.sin( angle / 2 )
    v.z = quat[3] / numpy.sin( angle / 2 )
    return v,angle


class VisObj(object):
    def __init__(self, position, f):
        self.f = f
        self.obj = visual.box(frame=self.f, pos=position, axis=(1,0,0) ,length=3 ,height=.2 , radius=.5,material=visual.materials.rough)

        self.angle = 0
        self.axis  = visual.vector(0,0,1)
        self.quat = [0,0,0,0]
        self.saveaxis   = visual.vector(0,3,0)
        self.saveup = visual.vector(0,1,0)


class Graphics (threading.Thread):
    def __init__(self, num_objs, ids):
        threading.Thread.__init__(self)

        visual.scene.autoscale = False
        visual.scene.center = (2*5-1.5,-3,0)
        vt.scene.title = "Motion Visualizer"

        f = visual.frame()

        self.text = []
        self.objs = []
        self.graphs = []
        self.data = []
        self.index = []
        self.stop = False
        for i in range(num_objs):

            self.text.append(None)
            self.objs.append(VisObj( (i*5,1,0), f ))
            self.data.append( [] )
            self.index.append( 0 )
            self.graphs.append( [] )
            self.data[-1] = [ [], [], [] ]

            for n in range(100):
                self.data[-1][0].append( [(i*5-1.5)+(3.0/100)*n, -5, 0])
            for n in range(100):
                self.data[-1][1].append( [(i*5-1.5)+(3.0/100)*n, -4, 0])
            for n in range(100):
                self.data[-1][2].append( [(i*5-1.5)+(3.0/100)*n, -3, 0])

            self.graphs[-1].append( visual.curve( pos=self.data[-1][0], radius=0.05,color=visual.color.red  ) )

            self.graphs[-1].append( visual.curve(pos=self.data[-1][1],
                                                 radius=0.05,color=visual.color.blue  ) )
            self.graphs[-1].append( visual.curve(pos=self.data[-1][2],
                                                 radius=0.05,color=visual.color.yellow  ) )

    def add_label(self, num, label):
        self.text[num] = vt.text(pos=(num*5,3.5,0), string=label.upper(), justify='center', depth=-0.3, color=vt.color.green)

    def run(self):
        while True:
            if self.stop:
                vt.scene.visible = False
                print("exit graphics")
                sys.exit(0)
                return
            visual.rate(60)
            for i,thing in enumerate(self.objs):
                # Reset current orientation
                thing.obj.up   = thing.saveup
                thing.obj.axis = thing.saveaxis
                thing.obj.rotate(angle=numpy.pi/2, axis=visual.vector(0,0,1) )

                # Set angle, axis from current quat
                thing.axis, thing.angle = axisAngleFromQuaternion(thing.quat)
                thing.obj.rotate(angle=thing.angle, axis=thing.axis)

                # Update graphs
                self.graphs[i][0].pos = self.data[i][0]
                self.graphs[i][1].pos = self.data[i][1]
                self.graphs[i][2].pos = self.data[i][2]

    def update(self, data):
        sensor_id = data['sensor_id']
        acc_data = data['acc_data']
        quat_data = data['quat_data']

        if self.index[sensor_id] >= 99:
            self.index[sensor_id] = 0
        else:
            self.index[sensor_id] += 1

        self.data[sensor_id][0][self.index[sensor_id]][1] = -2 + acc_data[0]
        self.data[sensor_id][1][self.index[sensor_id]][1] = -4 + acc_data[1]
        self.data[sensor_id][2][self.index[sensor_id]][1] = -6 + acc_data[2]

        self.objs[sensor_id].quat = [quat_data[0],
                                     quat_data[1],
                                     quat_data[2],
                                     quat_data[3]]


def read_from_socket():
    # Create UDS socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_address = '/tmp/sensor_consumer'
    print("Connecting to {}... ".format( server_address ), end='')
    header_length = struct.calcsize("!l")

    try:
        sock.connect(server_address)
    except socket.error:
        print(socket.error)
        return
    else:
        print("connected")

    try:
        while True:
            data = None
            tmp_sz = sock.recv( header_length )
            if len(tmp_sz) == 0:
                print("Connection dropped! Exiting")
                sys.exit(1)

            size = struct.unpack("!l", tmp_sz)[0]
            data = sock.recv( size )

            while size-len(data) > 0:
                tmp = sock.recv(size-len(data))
                if len(tmp) > 0:
                    data += tmp
                else:
                    print("Connection dropped!")
                    sys.exit(1)

            r = json.loads(data)

            sensor_id = r['id']
            acc_data = r['acc']
            acc_data = [ a/10000000 for a in acc_data]
            quat_data = r['quat']

            # Re-order for y-up coordinate system
            quat_data = [quat_data[0],
                         quat_data[1],  # x = x
                         quat_data[3],   # y = z
                         -quat_data[2]]   # z = -y

            yield {'sensor_id': sensor_id, 'acc_data': acc_data, 'quat_data': quat_data}

    except KeyboardInterrupt:
        print("\nExiting message bus reader...")
        sock.close()
        return
    except Exception as e:
        print("Closing, error {}".format(e))
        sock.close()
        return
    else:
        print("Closing")
        return


def read_from_log(inputfile, speed):
    csvReader = None
    try:
        inputcsv = open(inputfile, 'r')
        csvReader = csv.DictReader(inputcsv,
                                   skipinitialspace=True,
                                   delimiter=',',
                                   quotechar='|')

    except NameError as e:
        print("Error opening input file: %" % e)
        sys.exit(-1)

    prev_timestamps = {}
    last_yield = {}
    toggles = {}

    try:
        for row in csvReader:
            sensor_id = row['id']
            timestamp = float(row['timestamp'])
            quat_data  = ast.literal_eval( row['quat'] )
            # Re-order for y-up coordinate system
            quat_data = [quat_data[0],
                         quat_data[1],  # x = x
                         quat_data[3],   # y = z
                         -quat_data[2]]   # z = -y

            acc_data   = ast.literal_eval( row['acc'] )
            # Scale data for viewing
            acc_data = [ a/10000000 for a in acc_data]

            if sensor_id not in prev_timestamps:
                prev_timestamps[sensor_id] = [ timestamp, timestamp ]
                last_yield[sensor_id] = 0
                toggles[sensor_id] = True

            if toggles[sensor_id]:
                to_wait = prev_timestamps[sensor_id][1] - prev_timestamps[sensor_id][0]
                prev_timestamps[sensor_id][0] = timestamp
            else:
                to_wait = prev_timestamps[sensor_id][0] - prev_timestamps[sensor_id][1]
                prev_timestamps[sensor_id][1] = timestamp
            toggles[sensor_id] = not toggles[sensor_id]

            now = time.time()
            to_wait = to_wait / speed
            delta = (now - last_yield[sensor_id])

            if delta < to_wait:
                time.sleep(to_wait - delta)

            last_yield[sensor_id] = time.time()

            yield {'sensor_id': sensor_id, 'acc_data': acc_data, 'quat_data': quat_data}

    except KeyboardInterrupt:
        print("\nExiting log reader...")
        return
    finally:
        inputcsv.close()
    return


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Visualize motion data from message bus or from a csv log file')
    parser.add_argument('-b','--bus', help='use message bus', action='store_true')
    parser.add_argument('-c','--csv', help='use csv file', default="")
    parser.add_argument('-s','--speed', type=float, help='Speed multiplier to apply when playing back a csv file', default="1")
    args = parser.parse_args()

    args.speed = args.speed if args.speed > 0 else 1

    if not args.bus and len(args.csv) == 0:
        print("Specify either bus or csv")
        sys.exit(-1)

    lots_of_data = read_from_socket() if args.bus else read_from_log(args.csv, float(args.speed))

    graphics = Graphics(4, ["00","01","10","11"])
    graphics.daemon = True
    graphics.start()

    sensors = {}

    for data in lots_of_data:
        if data['sensor_id'] not in sensors:
            num = len(sensors)
            graphics.add_label(num, data['sensor_id'])
            sensors[data['sensor_id']] = num
        data['sensor_id'] = sensors[data['sensor_id']]
        graphics.update(data)
    graphics.stop = True
