import jqsh
import jqsh.parser
import queue
import threading

class Terminator:
    """a special value used to signal the end of a channel"""

class Channel:
    def __init__(self, *args, terminated=False):
        self.input_lock = threading.Lock()
        self.input_terminated = False # has the terminator been pushed?
        self.output_lock = threading.Lock()
        self.terminated = False # has the terminator been popped?
        self.values = queue.Queue()
        for value in args:
            self.push(value)
        if terminated:
            self.terminate()
    
    def __iter__(self):
        return self
    
    def __next__(self):
        """Raises queue.Empty if no element is currently available, SyntaxError if the tokens are not valid JSON, and StopIteration if the channel is terminated."""
        if self.terminated:
            raise StopIteration('jqsh channel has terminated')
        tokens = []
        with self.output_lock:
            while True:
                if self.terminated:
                    if len(tokens):
                        raise jqsh.parser.Incomplete('jqsh channel has terminated mid-value')
                    raise StopIteration('jqsh channel has terminated')
                token = self.values.get()
                if isinstance(token, Terminator):
                    self.terminated = True
                    if len(tokens):
                        raise jqsh.parser.Incomplete('jqsh channel has terminated mid-value')
                    raise StopIteration('jqsh channel has terminated')
                tokens.append(token)
                try:
                    return jqsh.parser.parse_json(tokens, allow_extension_types=True)
                except jqsh.parser.Incomplete:
                    continue
    
    def __truediv__(self, other):
        """Splits the channel into multiple channels:
        
        All values that have not yet been read from this channel, and any values that are added later, will be copied into the other channels.
        The original channel will appear to be terminated immediately, and the split channels will terminate when the original channel is actually terminated.
        The split channels are returned as a tuple.
        """
        def spread_values(split_channels):
            while True:
                token = self.values.get()
                if isinstance(token, Terminator):
                    for chan in split_channels:
                        chan.terminate()
                    break
                for chan in split_channels:
                    chan.push(token)
        
        try:
            other = int(other)
        except:
            return NotImplemented
        buffered_tokens = []
        with self.output_lock:
            if self.terminated:
                return tuple([Channel(terminated=True)] * other)
            self.terminated = True
            self.values.put(Terminator())
            while True:
                token = self.values.get()
                if isinstance(token, Terminator):
                    break
                else:
                    buffered_tokens.append(token)
        ret = [Channel(*buffered_tokens) for _ in range(other)]
        threading.Thread(target=spread_values, args=(ret,)).start()
        return tuple(ret)
    
    def pop(self, wait=True):
        """Returns a token. Raises queue.Empty if no element is currently available, and StopIteration if the channel is terminated."""
        with self.output_lock:
            if self.terminated:
                raise StopIteration('jqsh channel has terminated')
            ret = self.values.get(block=wait)
            if isinstance(ret, Terminator):
                self.terminated = True
                raise StopIteration('jqsh channel has terminated')
        return ret
    
    def push(self, value):
        if isinstance(value, jqsh.parser.Token):
            with self.input_lock:
                if self.input_terminated:
                    raise RuntimeError('jqsh channel has terminated')
                self.values.put(value)
        else:
            with self.input_lock:
                for token in jqsh.parser.json_to_tokens(value, allow_extension_types=True):
                    self.values.put(token)
    
    def terminate(self):
        with self.input_lock:
            self.input_terminated = True
            self.values.put(Terminator())
