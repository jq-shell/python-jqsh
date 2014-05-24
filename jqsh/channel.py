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
                    return jqsh.parser.parse_json(tokens)
                except jqsh.parser.Incomplete:
                    continue
    
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
                if self._terminated:
                    raise RuntimeError('jqsh channel has terminated')
                self.values.put(value)
        else:
            with self.input_lock:
                for token in jqsh.parser.json_to_tokens(value):
                    self.values.put(token)
    
    def terminate(self):
        with self.input_lock:
            self._terminated = True
            self.values.put(Terminator())
