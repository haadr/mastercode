import time


class Timer:
    """ Timer to easily calculate a frequency for an event.

    :param name: Name to use when printing out to stdout
    :param interval: How often to return the frequency per second. If 0, always return.
    :param pipe: A multiprocessing.Connection to send frequency to on calling tick() according to interval frequency
    :param disabled: Disables the entire timer
    :returns: Frequency of calls to tick()
    """
    def __init__(self, name, interval, disabled=False):
        self.disabled = disabled
        self.name     = name
        self.hz       = 0
        self.interval = 1/interval
        self.last     = time.time()
        self.last_return = self.last
        self.current  = None
        self.times    = []

    def tick(self):
        """ Call this function to mark an event. Print out frequency according to interval arg provided to constructor.  """
        if(self.disabled):
            return

        self.current = time.time()
        if( len(self.times) > 100):
            self.times.pop()
            self.times.insert(0, self.current - self.last )
        else:
            self.times.append( self.current - self.last )
        self.last = self.current

        if ( self.current - self.last_return > self.interval ):
            avg = sum( self.times) / len(self.times)
            self.last_return = self.current
            self.hz = 1/avg
            print("{:10s} {:5.2f}".format(self.name, self.hz))
        return
