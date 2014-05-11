import queue

class Terminator:
    pass

class Channel:
    def __init__(self, *args):
        self.terminated = False
        self.values = queue.Queue()
        for value in args:
            self.values.put(value)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        """Blocks until an element is available or the channel is closed."""
        if self.terminated:
            raise StopIteration('jqsh channel has terminated')
        ret = self.values.get()
        if isinstance(ret, Terminator):
            self.terminated = True
            raise StopIteration('jqsh channel has terminated')
        return ret
    
    def pop(self):
        """Raises queue.Empty if no element is currently available, and StopIteration if the channel is terminated."""
        if self.terminated:
            raise StopIteration('jqsh channel has terminated')
        ret = self.values.get_nowait()
        if isinstance(ret, Terminator):
            self.terminated
            raise StopIteration('jqsh channel has terminated')
        return ret
    
    def push(self, value):
        self.values.put(value)
    
    def terminate(self):
        self.values.put(Terminator())
