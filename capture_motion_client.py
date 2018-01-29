#!/usr/bin/python3
import argparse
import json
import os
import socket
import struct
import sys

from motion_logger import MotionLogger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect to message bus and save motion data to csv file.")
    parser.add_argument("-t","--ts-id", help="Id of the test subject performing the exercise", required=True)
    parser.add_argument("-e","--exercise", help="Name of exercise", required=True)
    parser.add_argument("-m","--mode", help="Mode code number representing an execution type "
                        "(for instance an error type or correct)", required=True)
    parser.add_argument("-n","--num", help="Sample number", required=True)
    args = parser.parse_args()

    ts_dir = "ts" + args.ts_id
    if not os.path.exists(ts_dir):
        print("Creating directory {}...".format(ts_dir))
        os.makedirs(ts_dir)

    filepath = ts_dir + "/" + "_".join([args.exercise, args.mode, args.num])
    print("Saving to file {}".format(filepath))

    # Create UDS socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    server_address = '/tmp/sensor_consumer'
    print("Connecting to message bus at {}".format( server_address ) )

    header_length = struct.calcsize("!l")

    try:
        sock.connect(server_address)
    except socket.error:
        print(socket.error)
        sys.exit(1)
    else:
        print("Connected to message bus")

    logger = MotionLogger(filepath)
    try:
        while True:
            data = None
            tmp_sz = sock.recv( header_length )
            if len(tmp_sz) == 0:
                print("Connection dropped! Exiting")
                sys.exit(1)

            size = int(struct.unpack("!l", tmp_sz)[0])
            data = sock.recv( size )
            while size-len(data) > 0:
                tmp = sock.recv(size-len(data))
                if len(tmp) > 0:
                    data += tmp
                else:
                    print("Connection dropped!")
                    sys.exit(1)

            deserialized_data = json.loads(data.decode('utf-8'))
            logger.addData(deserialized_data)

    except KeyboardInterrupt:
        print("\nExiting...")
        logger.close()
        sock.close()
        sys.exit(1)
    except Exception as e:
        raise
        logger.close()
        print("Exit: {}".format(e.args))
        sock.close()
        sys.exit(1)
    else:
        logger.close()
        sock.close()
