import collections
import functools

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
        def wrapper(*args):
            if not any_args and len(args) != num_args:
                raise ValueError('incorrect number of arguments: expected ' + repr(num_args) + ', found ' + repr(len(args)))
            return f(*args)
        return wrapper
    if callable(num_args):
        return ret(num_args, any_args=True)
    return ret
