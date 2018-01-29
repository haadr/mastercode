import csv
import sys
import datetime


class MotionLogger(object):
    def __init__(self, outputfile):

        print("File: {}".format(outputfile))

        self.lines = 0
        self.header = []
        self.outputfile = outputfile + " - " + datetime.datetime.now().isoformat().split('.')[0] + ".csv"

        try:
                self.csvfile   = open(self.outputfile, 'w')
        except NameError:
                pass
        try:
                self.logWriter = csv.writer(self.csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_NONNUMERIC)
                print("Start writing to {}".format(self.outputfile))
        except NameError as e:
            print("Name error {}".format( e ))
            sys.exit(1)

    def addData(self, data):
        if self.lines < 1:
            self.header = list(data.keys())
            self.header.sort()
            print("Writing header: {}".format(self.header))
            self.logWriter.writerow(self.header)

        to_write = []
        for key in self.header:
            to_write.append(data[key])

        self.logWriter.writerow(to_write)
        self.lines += 1

    def close(self):
        self.csvfile.close()
        print("Stop recording to {}, written {} lines".format(self.outputfile, self.lines))
