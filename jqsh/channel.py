import jqsh
import jqsh.filter
import jqsh.parser
import queue
import threading

class Terminator:
    """a special value used to signal the end of a channel"""

class Channel:
    def __init__(self, *args, global_namespace=None, local_namespace=None, format_strings=None, terminated=False, empty_namespaces=None):
        self.input_lock = threading.Lock()
        self.input_terminated = False # has the terminator been pushed?
        self.output_lock = threading.Lock()
        self.terminated = False # has the terminator been popped?
        # namespaces
        if empty_namespaces is None:
            empty_namespaces = terminated
        if empty_namespaces:
            if global_namespace is None:
                global_namespace = {}
            if local_namespace is None:
                local_namespace = {}
            if format_strings is None:
                format_strings = {}
        self._globals = None
        self._locals = None
        self._format_strings = None
        self.has_globals = threading.Event()
        self.has_locals = threading.Event()
        self.has_format_strings = threading.Event()
        if global_namespace is not None:
            self.global_namespace = global_namespace
        if local_namespace is not None:
            self.local_namespace = local_namespace
        if format_strings is not None:
            self.format_strings = format_strings
        # values
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
        threading.Thread(target=jqsh.filter.Filter.handle_namespace, kwargs={'namespace_name': 'global_namespace', 'input_channel': self, 'output_channels': ret}).start()
        threading.Thread(target=jqsh.filter.Filter.handle_namespace, kwargs={'namespace_name': 'local_namespace', 'input_channel': self, 'output_channels': ret}).start()
        threading.Thread(target=jqsh.filter.Filter.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': self, 'output_channels': ret}).start()
        return tuple(ret)
    
    @property
    def global_namespace(self):
        self.has_globals.wait()
        return self._globals
    
    @global_namespace.setter
    def global_namespace(self, value):
        self._globals = value
        self.has_globals.set()
    
    @property
    def local_namespace(self):
        self.has_locals.wait()
        return self._locals
    
    @local_namespace.setter
    def local_namespace(self, value):
        self._locals = value
        self.has_locals.set()
    
    @property
    def format_strings(self):
        self.has_format_strings.wait()
        return self._format_strings
    
    @format_strings.setter
    def format_strings(self, value):
        self._format_strings = value
        self.has_format_strings.set()
    
    def get_namespaces(self, from_channel):
        self.global_namespace = from_channel.global_namespace
        self.local_namespace = from_channel.local_namespace
        self.format_strings = from_channel.format_strings
    
    def namespaces(self):
        return self.global_namespace, self.local_namespace, self.format_strings
    
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
    
    def pull(self, from_channel, terminate=True):
        """Move all values from from_channel to this one, blocking until from_channel terminates, then optionally terminate."""
        if terminate:
            with self.input_lock:
                if self.input_terminated:
                    raise RuntimeError('jqsh channel has terminated')
                self.input_terminated = True
        else:
            self.input_lock.acquire()
        while True:
            try:
                token = from_channel.pop()
            except StopIteration:
                break
            self.values.put(token)
        if terminate:
            self.values.put(Terminator())
        else:
            self.input_lock.release()
    
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
