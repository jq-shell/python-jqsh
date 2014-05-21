import jqsh.parser
import queue
import threading

class Terminator:
    """a special value used to signal the end of a channel"""

class Channel:
    def __init__(self, *args):
        self.input_lock = threading.Lock()
        self.output_lock = threading.Lock()
        self.terminated = False
        self.values = queue.Queue()
        for value in args:
            self.values.put(value)
    
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
    
    def pop(self, wait=False):
        """Returns a token. Raises queue.Empty if no element is currently available, and StopIteration if the channel is terminated."""
        if self.terminated:
            raise StopIteration('jqsh channel has terminated')
        with self.output_lock:
            ret = self.values.get(block=wait)
            if isinstance(ret, Terminator):
                self.terminated = True
                raise StopIteration('jqsh channel has terminated')
        return ret
    
    def push(self, value):
        if isinstance(value, jqsh.parser.Token):
            with self.input_lock:
                self.values.put(value)
        else:
            with self.input_lock:
                for token in jqsh.parser.json_to_tokens(value):
                    self.values.put(token)
    
    def terminate(self):
        self.values.put(Terminator())
