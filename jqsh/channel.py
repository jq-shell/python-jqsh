import contextlib
import functools
import jqsh.context
import queue
import threading

class Terminator:
    """a special value used to signal the end of a channel"""

def coerce_other(f):
    @functools.wraps(f)
    def wrapper(self, other):
        import jqsh.values
        
        return f(self, jqsh.values.from_native(other))
    
    return wrapper

class Channel:
    _globals = None
    _locals = None
    _format_strings = None
    _context = None
    input_terminated = False # has the terminator been pushed?
    terminated = False # has the terminator been popped?
    
    def __init__(self, *args, global_namespace=None, local_namespace=None, format_strings=None, terminated=False, empty_namespaces=None, context=None):
        self.input_lock = threading.Lock()
        self.output_lock = threading.Lock()
        # namespaces and context
        if empty_namespaces is None:
            empty_namespaces = terminated
        if empty_namespaces:
            if global_namespace is None:
                global_namespace = {}
            if local_namespace is None:
                local_namespace = {}
            if format_strings is None:
                format_strings = {}
            if context is None:
                context = jqsh.context.FilterContext()
        self.has_globals = threading.Event()
        self.has_locals = threading.Event()
        self.has_format_strings = threading.Event()
        self.has_context = threading.Event()
        if global_namespace is not None:
            self.global_namespace = global_namespace
        if local_namespace is not None:
            self.local_namespace = local_namespace
        if format_strings is not None:
            self.format_strings = format_strings
        if context is not None:
            self.context = context
        # values
        self.value_queue = queue.Queue()
        for value in args:
            self.push(value)
        if terminated:
            self.terminate()
    
    def __iter__(self):
        return self
    
    def __next__(self):
        """Raises StopIteration if the channel is terminated."""
        with self.output_lock:
            if self.terminated:
                raise StopIteration('jqsh channel has terminated')
            value = self.value_queue.get()
            if isinstance(value, Terminator):
                self.terminated = True
                raise StopIteration('jqsh channel has terminated')
            self.store_value(value)
            return value
    
    def __truediv__(self, other):
        """Splits the channel into multiple channels:
        
        All values that have not yet been read from this channel, and any values that are added later, will be copied into the other channels.
        The original channel will appear to be terminated immediately, and the split channels will terminate when the original channel is actually terminated.
        The split channels are returned as a tuple.
        """
        import jqsh.filter
        
        def spread_values(split_channels):
            while True:
                value = self.value_queue.get()
                if isinstance(value, Terminator):
                    for chan in split_channels:
                        chan.terminate()
                    break
                self.store_value(value)
                for chan in split_channels:
                    chan.push(value)
        
        try:
            other = int(other)
        except:
            return NotImplemented
        buffered_values = []
        with self.output_lock:
            if self.terminated:
                return tuple([Channel(terminated=True)] * other)
            self.terminated = True
            self.value_queue.put(Terminator())
            while True:
                value = self.value_queue.get()
                if isinstance(value, Terminator):
                    break
                self.store_value(value)
                buffered_values.append(value)
        ret = [Channel(*buffered_values) for _ in range(other)]
        threading.Thread(target=spread_values, args=(ret,)).start()
        threading.Thread(target=self.push_namespaces, args=tuple(ret)).start()
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
    
    @property
    def context(self):
        self.has_context.wait()
        return self._context
    
    @context.setter
    def context(self, value):
        self._context = value
        self.has_context.set()
    
    def get_namespaces(self, from_channel, include_context=True):
        from_channel.push_namespaces(self, include_context=include_context)
    
    def namespaces(self):
        return self.global_namespace, self.local_namespace, self.format_strings
    
    def pop(self, wait=True):
        """Returns a value. Raises queue.Empty if no element is currently available, and StopIteration if the channel is terminated."""
        with self.output_lock:
            if self.terminated:
                raise StopIteration('jqsh channel has terminated')
            ret = self.value_queue.get(block=wait)
            if isinstance(ret, Terminator):
                self.terminated = True
                raise StopIteration('jqsh channel has terminated')
            self.store_value(ret)
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
                value = from_channel.pop()
            except StopIteration:
                break
            self.value_queue.put(value)
        if terminate:
            self.value_queue.put(Terminator())
        else:
            self.input_lock.release()
    
    @coerce_other
    def push(self, value):
        with self.input_lock:
            if self.input_terminated:
                raise RuntimeError('jqsh channel has terminated')
            self.value_queue.put(value)
    
    def push_attribute(self, attribute_name, *output_channels):
        """Waits until the attribute is available, then passes it unchanged to the output channels. Used by Filter.run_raw and Channel.push_namespaces."""
        attribute_value = getattr(self, attribute_name)
        for chan in output_channels:
            setattr(chan, attribute_name, attribute_value)
    
    def push_namespaces(self, *output_channels, include_context=True):
        threads = []
        for attribute_name in ['global_namespace', 'local_namespace', 'format_strings'] + (['context'] if include_context else []):
            thread = threading.Thread(target=self.push_attribute, args=(attribute_name,) + output_channels)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
    
    def store_value(self, value):
        pass # subclass this if required, by default channels don't store values
    
    def terminate(self):
        with self.input_lock:
            self.input_terminated = True
            self.value_queue.put(Terminator())
    
    def throw(self, exception):
        """Tries to append the exception onto the channel, failing silently if terminated, then defines all properties for which events are defined, and terminates."""
        import jqsh.values
        
        if isinstance(exception, str) or isinstance(exception, jqsh.values.String):
            exception = jqsh.values.JQSHException(exception)
        with contextlib.suppress(RuntimeError):
            self.push(exception)
        if self._globals is None:
            self.global_namespace = {}
        if self._locals is None:
            self.local_namespace = {}
        if self._format_strings is None:
            self.format_strings = {}
        if self._context is None:
            self.context = jqsh.context.FilterContext()
        self.terminate()
