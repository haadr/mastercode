#!/usr/bin/python3
import errno
import json
import os
import select
import socket
import struct
import sys


def message_bus():
    """Start the message bus"""

    producer_address = '/tmp/sensor_producer'
    consumer_address = '/tmp/sensor_consumer'

    # Make sure the sockets does not already exist
    try:
        os.unlink(producer_address)
        os.unlink(consumer_address)
    except OSError:
        if os.path.exists(producer_address):
            raise
        if os.path.exists(consumer_address):
            raise

    producer_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    producer_socket.bind(producer_address)
    producer_socket.listen(1)

    consumer_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    consumer_socket.bind(consumer_address)
    consumer_socket.listen(1)

    # Select lists
    inputs = {producer_socket, consumer_socket}
    excepts = set()
    outputs = set()

    # Client and producer states
    producers = set()

    # producer_offsets = {}
    consumers = set()

    # Message queue for all sockets
    # Contains a queue of messages to be sent, for each sock
    # message_queues[<socket object>] = [ <list of messages to be sent to this socket object> ]
    message_queues = {}

    # Debugging timers
    print("Starting message bus...")
    while True:
        try:
            readable, writable, exceptional = select.select(inputs, outputs, excepts)
        except KeyboardInterrupt:
            print("\nCtrl+C caught.")
            for sock in inputs:
                sock.close()
            break
        except Exception as e:
            print("\nExeption: {}".format(e))
            exit(1)

        # Handle inputs
        for sock in readable:
            # New producer
            if sock is producer_socket:
                connection, client_address = sock.accept()

                print("New PRODUCER on {}".format(connection))

                producers.add(connection)
                inputs.add(connection)
                message_queues[connection] = []

            # New consumer
            elif sock is consumer_socket:
                connection, client_address = sock.accept()

                print("New CONSUMER on {}".format(connection))

                consumers.add(connection)
                outputs.add(connection)

                message_queues[connection] = []

            # A client has sent data
            else:
                try:
                    tmp_size = sock.recv(struct.calcsize("!l"))
                    if len(tmp_size) == 0:
                        data = 0
                    else:
                        size = int(struct.unpack("!l", tmp_size)[0])
                        data = sock.recv(size)
                        while len(data) < size:
                            data += sock.recv(size - len(data))

                except OSError as e:
                    if e.errno != errno.ECONNRESET:
                        # raise
                        # Handle socket reset/hangup
                        print("Exception: {} -- Closing {}".format(e, sock))
                        if sock in outputs:
                            outputs.remove(sock)
                        if sock in inputs:
                            inputs.remove(sock)
                        if sock in producers:
                            producers.pop(sock)
                        if sock in consumers:
                            consumers.pop(sock)
                        sock.close()
                        del message_queues[sock]
                except Exception as e:
                    print("Exception:{} ::{}:: {}".format(
                          repr(e), tmp_size, type(tmp_size).__name__))
                    sys.exit(1)

                # We have received data from an existing consumer or producer
                else:
                    # Data from producer
                    if data and sock in producers:
                        # Check valid json
                        try:
                            tmp = json.loads(data.decode('utf-8'))
                        except Exception as e:
                            print("Error: {}".format(e))
                        # Broadcast to everyone
                        else:
                            tmp = json.dumps(tmp)

                            for client in consumers:
                                message_queues[client].append(tmp)

                    # Data from consumer
                    elif data and sock in consumers:
                        print("Received {} from CONSUMER {} ".format(data, sock))
                        print("Warning: Receiving data from consumers is not supported! Doing nothing...")

                    # Closed connection
                    else:
                        if sock in inputs:
                            print("Removing from inputs")
                            inputs.remove(sock)
                        if sock in outputs:
                            print("Removing from outputs")
                            outputs.remove(sock)
                        if sock in writable:
                            print("Removing from writable")
                            writable.remove(sock)

                        if sock in producers:
                            print("Closing producer {}".format(sock))
                            # Broadcast disconnect
                            producers.remove(sock)
                        if sock in consumers:
                            print("Closing consumer {}".format(sock))
                            consumers.remove(sock)

                        sock.close()
                        del message_queues[sock]

        for sock in writable:
            if sock in producers:
                print("Sending to producer!")
            try:
                while len(message_queues[sock]) > 0:
                    sock.sendall(struct.pack("!l", len(message_queues[sock][-1])))
                    sock.sendall(bytearray(message_queues[sock].pop(), 'utf-8'))
            except Exception as e:
                print("Error \"{}\" while sending queue to {}".format(e.args, sock))
                print("Closing socket {}".format(sock))
                if sock in inputs:
                    inputs.remove(sock)
                if sock in outputs:
                    outputs.remove(sock)
                if sock in producers:
                    producers.remove(sock)
                if sock in consumers:
                    consumers.remove(sock)
                sock.close()
                del message_queues[sock]

        for sock in exceptional:
            print("Handling exceptional condition for {}".format(sock))
            if sock in inputs:
                inputs.remove(sock)
            if sock in outputs:
                outputs.remove(sock)
            if sock in producers:
                producers.remove(sock)
            if sock in consumers:
                consumers.remove(sock)
            sock.close()
            del message_queues[sock]

    print("Good bye!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("Usage:\n\n"
              "This program will start a message bus. Producers and consumers "
              "can connect on '/tmp/sensor_producer' and '/tmp/sensor_consumer'"
              ", respectively. Messages are sent formatted in json. "
              "Producers send messages to the message bus, which forwards them to all consumers.\n\n"
              "This program takes no arguments.\n")

    message_bus()
