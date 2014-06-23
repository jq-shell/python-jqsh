import collections
import decimal
import functools
import jqsh
import jqsh.channel
import jqsh.filter
import jqsh.values
import builtins as python_builtins
import threading

builtin_functions = collections.defaultdict(dict)

def get_builtin(name, *args, num_args=None):
    if num_args is None:
        num_args = len(args)
    if name in builtin_functions:
        function_vector = builtin_functions[name]
        if num_args in function_vector:
            return function_vector[num_args]
        else:
            return function_vector['varargs']
    else:
        raise KeyError('No such built-in function')

def def_builtin(num_args=0, name=None):
    def ret(f, any_args=False):
        builtin_functions[f.__name__ if name is None else name]['varargs' if any_args else num_args] = f
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
            for value in f(*args, input_channel=bridge):
                output_channel.push(value)
                if isinstance(value, jqsh.values.JQSHException):
                    break
        
        bridge_channel = jqsh.channel.Channel()
        helper_thread = threading.Thread(target=run_thread, kwargs={'bridge': bridge_channel})
        handle_globals = threading.Thread(target=jqsh.filter.Filter.handle_namespace, kwargs={'namespace_name': 'global_namespace', 'input_channel': input_channel, 'output_channels': [bridge_channel, output_channel]})
        handle_locals = threading.Thread(target=jqsh.filter.Filter.handle_namespace, kwargs={'namespace_name': 'local_namespace', 'input_channel': input_channel, 'output_channels': [bridge_channel, output_channel]})
        handle_format_strings = threading.Thread(target=jqsh.filter.Filter.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': input_channel, 'output_channels': [bridge_channel, output_channel]})
        helper_thread.start()
        handle_globals.start()
        handle_locals.start()
        handle_format_strings.start()
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
        handle_globals.join()
        handle_locals.join()
        handle_format_strings.join()
        output_channel.terminate()
    return wrapper

@def_builtin(1)
@wrap_builtin
def each(the_filter, input_channel):
    for value in input_channel:
        yield from the_filter.start(jqsh.channel.Channel(value, terminated=True))

@def_builtin(0)
@wrap_builtin
def empty(input_channel):
    return
    yield # the empty generator

@def_builtin(0)
@wrap_builtin
def false(input_channel):
    yield False

@def_builtin(2, name='for')
@wrap_builtin
def jqsh_for(initial, body, input_channel):
    input_channel, initial_input = input_channel / 2
    output_channel = initial.start(initial_input)
    for value in input_channel:
        output_channel = body.start(output_channel)
        output_channel, current_output = output_channel / 2
        yield from current_output

@def_builtin(0)
@wrap_builtin
def implode(input_channel):
    ret = ''
    for value in input_channel:
        if not isinstance(value, decimal.Decimal):
            yield jqsh.values.JQSHException('type')
            return
        if value % 1 != 0:
            yield jqsh.values.JQSHException('integer')
            return
        ret += chr(value)
    yield ret

@def_builtin(1)
@wrap_builtin
def nth(index, input_channel):
    input_channel, index_input = input_channel / 2
    try:
        index_value = next(index.start(index_input))
    except StopIteration:
        yield jqsh.values.JQSHException('empty')
        return
    if isinstance(index_value, decimal.Decimal):
        if index_value % 1 == 0:
            index_value = int(index_value)
        else:
            yield jqsh.values.JQSHException('integer')
            return
    else:
        yield jqsh.values.JQSHException('type')
        return
    for i in python_builtins.range(index_value):
        try:
            next(input_channel)
        except StopIteration:
            yield jqsh.values.JQSHException('numValues')
            return
    try:
        yield next(input_channel)
    except StopIteration:
        yield jqsh.values.JQSHException('numValues')

@def_builtin(0)
@wrap_builtin
def null(input_channel):
    yield None

@def_builtin(0)
@wrap_builtin
def range(input_channel):
    for value in input_channel:
        if isinstance(value, decimal.Decimal):
            if value % 1 == 0:
                yield from (decimal.Decimal(number) for number in python_builtins.range(int(value)))
            else:
                yield jqsh.values.JQSHException('integer')
        else:
            yield jqsh.values.JQSHException('type')

@def_builtin(2)
@wrap_builtin
def reduce(initial, body, input_channel):
    input_channel, initial_input = input_channel / 2
    output_channel = initial.start(initial_input)
    for value in input_channel:
        output_channel = body.start(output_channel)
    yield from output_channel

@def_builtin(0)
@wrap_builtin
def true(input_channel):
    yield True
