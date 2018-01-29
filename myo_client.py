#!/usr/bin/python
from __future__ import print_function

import argparse
import dbus
import json
import numpy
import re
import socket
import struct
import sys
import time
import xml.etree.ElementTree as ET

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from timer_interval import Timer

from myodbus import MyoDbus


def discover_available_myos():
    """
    Tries to discover available (paired) Myo devices by traversing the dbus org.bluez tree,
    looking for devices exhibiting the Myo's base UUID and checking if its service and characterstic
    nodes are populated.

    :returns: A dict containing the available Myo devices.
    """

    bus = dbus.SystemBus()
    raw_bluez = bus.get_object('org.bluez', '/org/bluez')
    bluez_introspection = dbus.Interface(raw_bluez, dbus.INTROSPECTABLE_IFACE)
    introsprect_string = ET.fromstring(bluez_introspection.Introspect())

    # Connected bluetooth adapters
    nodes = introsprect_string.findall('node')
    adapters = {}
    for node in nodes:
        adapters[node.attrib['name']] = None

    # Paired Myos
    myo_base_uuid = 'd506[0-9a-fA-F]{4}-a904-deb9-4748-2c7f4a124842'
    uuid_matcher = re.compile(myo_base_uuid)
    myos = {}
    for adapter in adapters:
        raw_adapter = bus.get_object('org.bluez', '/org/bluez/' + adapter)
        adapter_introspect = dbus.Interface(raw_adapter, dbus.INTROSPECTABLE_IFACE)
        nodes = ET.fromstring(adapter_introspect.Introspect()).findall('node')

        for node in nodes:
            node_name = node.attrib['name']
            node_raw = bus.get_object('org.bluez', '/org/bluez/{}/{}'.format(adapter, node_name))
            node_props = dbus.Interface(node_raw, dbus.PROPERTIES_IFACE)
            uuids = node_props.Get('org.bluez.Device1', 'UUIDs')
            for uuid in uuids:
                matches = uuid_matcher.match(uuid)
                if matches is not None:
                    address = str(node_props.Get('org.bluez.Device1', "Address"))
                    if address not in myos:
                        path = node_raw.object_path
                        given_name = str(node_props.Get('org.bluez.Device1', "Name"))
                        myos[address] = {'name': given_name, 'adapter': adapter, 'path': path, 'address': address}
                    continue

    # Check which myos are "set up" by checking which have sub-nodes
    for node_name in myos.copy():
        myo_raw = bus.get_object('org.bluez', myos[node_name]['path'])
        myo_introspect = dbus.Interface(myo_raw, dbus.INTROSPECTABLE_IFACE)
        nodes = ET.fromstring(myo_introspect.Introspect()).findall('node')
        if len(nodes) < 1:
            del myos[node_name]

    return myos


class MyoClient:
    def __init__(self, wanted_myos=None, sleep=False, verbose=False):
        self.sleep = sleep
        self.verbose = verbose

        # Event loop and dbus
        DBusGMainLoop(set_as_default=True)
        self.loop = GLib.MainLoop()
        self.bus = dbus.SystemBus()

        self.myos = {}
        self.timers = []
        self.status = []
        self.num_myos = 0

        connected_myos = discover_available_myos()
        use_these_myos = []

        if wanted_myos is None:
            use_these_myos = list(connected_myos.values())
        else:
            for myo in wanted_myos:
                if myo not in connected_myos:
                    print("Error: {} not connected".format(myo))
                    return None

        for i,myo in enumerate(use_these_myos):
            self.myos[myo['path']] = MyoDbus(self.bus, myo['path'])
            self.myos[myo['path']].num = i

        self.num_myos = len(self.myos)

        if self.num_myos == 0:
            if wanted_myos is None:
                print("No devices available.")
            else:
                print("None of the specified devices were available.")

            sys.exit(0)

        """ Connect to all and subscribe to IMU """
        for myo in self.myos.itervalues():
            myo.connect(wait=True)
            if verbose:
                self.timers.append(Timer("{}".format(myo.myo_name), 1))
            self.status.append(None)
            myo.lock()
            myo.setNeverSleep()

            myo.subscribeToIMU()
            myo.attachIMUHandler(self.handleIMU)
            myo.enableIMU()

            print("Battery:     {}%".format( myo.getBatterLevel()))
            print("Sensor name: {}".format( myo.getName()))

        # Connect to message bus
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        messageBusAddress = '/tmp/sensor_producer'
        print("Connecting to message bus at {}".format( messageBusAddress ) )
        try:
            self.sock.connect(messageBusAddress)
        except socket.error:
            print(socket.error)
            sys.exit(1)
        else:
            print("Connected to message bus")

        # Start main loop
        try:
            print("Running main loop!")

            self.loop.run()

        except KeyboardInterrupt:

            print("\nShutting down...")

            self.sock.close()
            self.loop.quit()

            for myo in self.myos.itervalues():
                print("Disconnecting...")
                myo.unsubscribeFromIMU()
                myo.detachIMUHandler()
                myo.disableIMU_EMG_CLF()
                myo.vibrate(duration='short')
                if args.sleep:
                    print("Setting Myo to deep sleep...")
                    myo.setDeepSleep()
                myo.disconnect()

    def handleIMU(self, string1, dictionary, variant, myo_basepath=None):
        """ Handles receiving myo sensor values and sending them into the message bus. """
        if( myo_basepath[:37] in self.myos ):
            char = self.myos[myo_basepath[:37]].num
        else:
            print("Error! Got data from unregistered device.")
            sys.exit(-1)

        rb = dictionary['Value']
        MYOHW_ORIENTATION_SCALE = 16384.0
        MYOHW_ACCELEROMETER_SCALE = 2048.0
        MYOHW_GYROSCOPE_SCALE = 16.0
        vals = struct.unpack('10h', rb)
        quat = vals[:4]
        acc = vals[4:7]
        gyr = vals[7:10]

        # Apply scaling, see https://github.com/thalmiclabs/myo-bluetooth/blob/master/myohw.h
        acc = [ a * MYOHW_ACCELEROMETER_SCALE for a in acc ]
        gyr = [ g * MYOHW_GYROSCOPE_SCALE for g in gyr ]
        quat = [ q * MYOHW_ORIENTATION_SCALE for q in quat ]
        quat = quat / numpy.linalg.norm(quat)

        stringy = {'id' : self.myos[myo_basepath[:37]].myo_name,
                   'quat' : [ quat[0],quat[1],quat[2],quat[3] ],
                   'acc' : acc,
                   'gyr' : gyr,
                   'timestamp' : time.time()
                   }
        json_payload = json.dumps( stringy )
        try:
            self.sock.sendall(struct.pack("!l", len(json_payload) ))
            self.sock.sendall(json_payload )
        except socket.error as se:
            print("Socket error in handleIMU: {}\nExiting...".format(se))
            self.sock.close()
            self.loop.quit()
            sys.exit(0)
        except Exception as e:
            print("Exception in handleIMU: {}".format( e ))
            self.loop.quit()
            sys.exit(1)

        if self.verbose:
            self.timers[char].tick()


if __name__ == "__main__":
    header_length = struct.calcsize("!l")

    parser = argparse.ArgumentParser(description='Connect to Myo sensors and send their sensor data to the message bus')
    parser.add_argument('--sleep', dest='sleep', default=False, action='store_true')
    parser.add_argument('--myos', dest='addresses', default=None, nargs='+', help="Myo bluetooth addresses")
    parser.add_argument('-V', dest='verbose', default=False, action='store_true', help="Enable verbose output")
    parser.add_argument('-l', '--list', default=False, action='store_true', help="List available Myos and exit")
    args = parser.parse_args()

    if args.list:
        connected = discover_available_myos()
        print("Available Myo devices:")
        for myo_addr in connected:
            print("  Name: {} Address: {}".format(connected[myo_addr]['name'], myo_addr))
        sys.exit(0)

    myo_client = MyoClient(wanted_myos=args.addresses, sleep=args.sleep, verbose=args.verbose)
