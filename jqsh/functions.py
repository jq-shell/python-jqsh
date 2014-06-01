import collections
import functools
import jqsh
import jqsh.channel
import threading

builtin_functions = collections.defaultdict(dict)

def get_builtin(name, *args, num_args=None):
    if num_args is None:
        num_args = len(args)
    if name in builtin_functions:
        function_vector = builtin_functions[name]
        return function_vector.get(num_args, function_vector['varargs'])
    else:
        raise KeyError('No such built-in function')

def def_builtin(num_args=0):
    def ret(f, any_args=False):
        builtin_functions[f.__name__]['varargs' if any_args else num_args] = f
        @functools.wraps(f)
        def wrapper(*args, input_channel=None, output_channel=None):
            if not any_args and len(args) != num_args:
                raise ValueError('incorrect number of arguments: expected ' + repr(num_args) + ', found ' + repr(len(args)))
            return f(*args, input_channel=input_channel, output_channel=output_channel)
        return wrapper
    if callable(num_args):
        return ret(num_args, any_args=True)
    return ret

def wrap_builtin(f):
    @functools.wraps(f)
    def wrapper(*args, input_channel=None, output_channel=None):
        def run_thread(bridge):
            for value in f(input_channel=bridge):
                output_channel.push(value)
                if isinstance(value, Exception):
                    break
        
        bridge_channel = jqsh.channel.Channel()
        helper_thread = threading.Thread(target=run_thread, kwargs={'bridge': bridge_channel})
        helper_thread.start()
        while True:
            try:
                token = input_channel.pop()
            except StopIteration:
                break
            bridge_channel.push(token)
            if isinstance(token, Exception):
                output_channel.push(token)
                break
        bridge_channel.terminate()
        helper_thread.join()
        output_channel.terminate()
    return wrapper

@def_builtin
@wrap_builtin
def empty(input_channel):
    return
    yield # the empty generator

@def_builtin
@wrap_builtin
def false(input_channel):
    yield False

@def_builtin
@wrap_builtin
def null(input_channel):
    yield None

@def_builtin
@wrap_builtin
def true(input_channel):
    yield True
