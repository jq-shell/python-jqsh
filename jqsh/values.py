import abc
import collections
import collections.abc
import contextlib
import decimal
import functools
import itertools
import jqsh.channel
import more_itertools
import numbers
import operator
import sys
import traceback

def from_native(python_object):
    """Constructs a jqsh value from the passed Python object. The Python object may be anything the json module can work with."""
    if isinstance(python_object, Value):
        return python_object
    elif isinstance(python_object, BaseException):
        return JQSHException(str(python_object))
    elif python_object is None:
        return Null()
    elif isinstance(python_object, bool):
        return Boolean(python_object)
    elif isinstance(python_object, dict):
        return Object(python_object)
    elif isinstance(python_object, str):
        return String(python_object)
    try:
        iter(python_object)
    except TypeError:
        try:
            return Number(python_object)
        except (TypeError, decimal.InvalidOperation) as e:
            raise TypeError('cannot convert Python object of type ' + repr(python_object.__class__) + ' to a jqsh value') from e
    else:
        return Array(python_object)

@functools.total_ordering
class Value(abc.ABC):
    @abc.abstractmethod
    def __eq__(self, other):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def __hash__(self):
        return 0
    
    @abc.abstractmethod
    def __lt__(self, other):
        return NotImplemented
    
    def __repr__(self):
        return 'jqsh.values.' + self.__class__.__name__ + '(' + repr(self.value) + ')'
    
    @abc.abstractmethod
    def serializable(self):
        """Whether or not the value is JSON-serializable."""
        return False
    
    @abc.abstractmethod
    def syntax_highlight_lines(self, terminal):
        return
        yield

class JQSHException(Value):
    @jqsh.channel.coerce_other
    def __eq__(self, other):
        if isinstance(other, JQSHException):
            return self.name == other.name
        else:
            return False
    
    def __hash__(self):
        return hash(self.name)
    
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
    
    @jqsh.channel.coerce_other
    def __lt__(self, other):
        if isinstance(other, JQSHException):
            return self.name < other.name
        else:
            return True
    
    def __repr__(self):
        return 'jqsh.values.' + self.__class__.__name__ + '(' + repr(self.name) + ')'
    
    def print(self, output_file=None):
        import blessings
        
        if output_file is None:
            output_file=sys.stdout
        for line in self.syntax_highlight_lines(blessings.Terminal()):
            print(line, file=output_file, flush=True)
    
    def serializable(self):
        return False
    
    def syntax_highlight_lines(self, terminal):
        if not terminal.does_styling:
            yield str(self)
            return
        yield '\rjqsh: uncaught exception: ' + self.name
        if self.name == 'assignment' and 'target_filter' in self.kwargs:
            yield 'cannot assign to filter of type ' + self.kwargs['target_filter'].__class__.__name__
        elif self.name == 'internal' and 'exc_info' in self.kwargs:
            yield from self.kwargs['traceback_string'].strip('\n').split('\n')
        elif self.name == 'name' and 'missing_name' in self.kwargs:
            yield 'name ' + self.kwargs['missing_name'] + ' is not defined'
        elif self.name == 'notImplemented' and 'filter' in self.kwargs:
            yield 'filter ' + self.kwargs['filter'].__class__.__name__ + ' not yet implemented' + (' for attributes ' + repr(self.kwargs['attributes']) if 'attributes' in self.kwargs else '')
        elif self.name == 'numArgs' and 'expected' in self.kwargs:
            yield 'wrong number of function arguments: ' + ('received ' + str(self.kwargs['received']) + ', ') + 'expected ' + ('any of ' if len(self.kwargs['expected']) > 1 else '') + ', '.join(str(num_args) for num_args in sorted(self.kwargs['expected']))

class Null(Value):
    value = None
    
    def __bool__(self):
        return False
    
    @jqsh.channel.coerce_other
    def __eq__(self, other):
        if isinstance(other, Null):
            return True
        else:
            return False
    
    def __hash__(self):
        return hash(None)
    
    def __init__(self, *args, **kwargs):
        pass
    
    @jqsh.channel.coerce_other
    def __lt__(self, other):
        if isinstance(other, JQSHException):
            return False
        elif isinstance(other, Null):
            return False
        else:
            return True
    
    def __str__(self):
        return 'null'
    
    def serializable(self):
        return True
    
    def syntax_highlight_lines(self, terminal):
        if not terminal.does_styling:
            yield str(self)
            return
        yield terminal.bold(terminal.color(28)('null'))

class Boolean(Value):
    def __bool__(self):
        return self.value
    
    @jqsh.channel.coerce_other
    def __eq__(self, other):
        if isinstance(other, Boolean):
            return self.value == other.value
        else:
            return False
    
    def __hash__(self):
        return hash(self.value)
    
    def __init__(self, value=False):
        self.value = bool(value)
    
    @jqsh.channel.coerce_other
    def __lt__(self, other):
        if any(isinstance(other, other_class) for other_class in (JQSHException, Null)):
            return False
        elif isinstance(other, Boolean):
            return self.value == False and other.value == True
        else:
            return True
    
    def __str__(self):
        if self.value:
            return 'true'
        else:
            return 'false'
    
    def serializable(self):
        return True
    
    def syntax_highlight_lines(self, terminal):
        if not terminal.does_styling:
            yield str(self)
            return
        yield terminal.bold(terminal.color(28)('true' if self.value else 'false'))

class Number(Value, decimal.Decimal):
    def __bool__(self):
        return True
    
    @jqsh.channel.coerce_other
    def __eq__(self, other):
        if isinstance(other, Number):
            return decimal.Decimal.__eq__(self, other)
        else:
            return False
    
    def __hash__(self):
        return decimal.Decimal.__hash__(self)
    
    @jqsh.channel.coerce_other
    def __lt__(self, other):
        if any(isinstance(other, other_class) for other_class in (JQSHException, Null, Boolean)):
            return False
        elif isinstance(other, Number):
            return decimal.Decimal.__lt__(self, other)
        else:
            return True
    
    def __repr__(self):
        return 'jqsh.values.' + self.__class__.__name__ + '(' + repr(str(self)) + ')'
    
    def serializable(self):
        return True
    
    def syntax_highlight_lines(self, terminal):
        if not terminal.does_styling:
            yield str(self)
            return
        yield terminal.color(32)(str(self))
    
    @property
    def value(self):
        return decimal.Decimal(self)

class String(Value, jqsh.channel.Channel, collections.abc.Sequence):
    @jqsh.channel.coerce_other
    def __eq__(self, other):
        if isinstance(other, String):
            for index in itertools.count():
                if len(self) <= index: #TODO avoid calling len(self) if possible
                    if len(other) <= index: #TODO avoid calling len(other) if possible
                        return True
                    else:
                        return False
                elif len(other) <= index:
                    return False
                elif self[index] != other[index]:
                    return False
            return self.value == other.value
        else:
            return False
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            start = key.start
            if start is None:
                start = 0
            stop = key.stop
            if start < 0 or stop < 0:
                start, stop, step = key.indices(len(self))
            else:
                step = key.step
                if step is None:
                    step = -1 if stop < start else 1
            return String(itertools.islice(self, start, stop, step))
        while True:
            if len(self.value_store) > key:
                return self.value_store[key]
            try:
                self.pop()
            except StopIteration as e:
                if len(self.value_store) > key:
                    return self.value_store[key]
                raise IndexError('Index {} is out of bounds for jqsh array'.format(key)) from e
    
    def __hash__(self):
        return hash(self.value)
    
    def __init__(self, value='', terminated=True):
        self.value_store = ''
        super().__init__(str(value), terminated=terminated)
    
    def __iter__(self):
        for index in itertools.count():
            try:
                yield self[index]
            except IndexError as e:
                raise StopIteration('Reached end of jqsh string') from e
    
    def __len__(self):
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return len(self.value_store)
    
    @jqsh.channel.coerce_other
    def __lt__(self, other):
        if any(isinstance(other, other_class) for other_class in (JQSHException, Null, Boolean, Number)):
            return False
        elif isinstance(other, String):
            for index in itertools.count():
                if len(other) <= index: #TODO avoid calling len(other) if possible
                    return False
                elif len(self) <= index: #TODO avoid calling len(self) if possible
                    return True
                elif self[index] < other[index]:
                    return True
                elif self[index] > other[index]:
                    return False
        else:
            return True
    
    def __str__(self):
        import jqsh.filter
        
        return jqsh.filter.StringLiteral.representation(self.value)
    
    def push(self, value):
        error_message = 'String channel only accepts valid Unicode strings'
        if not isinstance(value, str):
            raise TypeError(error_message)
        try:
            value.encode('utf-16')
        except UnicodeEncodeError as e:
            raise ValueError(error_message) from e
        with self.input_lock:
            if self.input_terminated:
                raise RuntimeError('jqsh channel has terminated')
            self.value_queue.put(value)
    
    def serializable(self):
        return True #TODO add support for extended strings(regex), mark them as unserializable
    
    def store_value(self, value):
        self.value_store += value
    
    def syntax_highlight_lines(self, terminal):
        import jqsh.filter
        
        if not terminal.does_styling:
            yield str(self)
            return
        yield terminal.color(9)('"') + ''.join(terminal.color(202 if jqsh.filter.StringLiteral.escape(character).startswith('\\') else 1)(jqsh.filter.StringLiteral.escape(character)) for character in self.value) + terminal.color(9)('"')
    
    @property
    def value(self):
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return self.value_store

class Array(Value, jqsh.channel.Channel, collections.abc.Sequence):
    def __eq__(self, other):
        if isinstance(other, Array):
            for index in itertools.count():
                if len(self) <= index: #TODO avoid calling len(self) if possible
                    if len(other) <= index: #TODO avoid calling len(other) if possible
                        return True
                    else:
                        return False
                elif len(other) <= index:
                    return False
                elif self[index] != other[index]:
                    return False
        else:
            return False
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            start = key.start
            if start is None:
                start = 0
            stop = key.stop
            if start < 0 or stop < 0:
                start, stop, step = key.indices(len(self))
            else:
                step = key.step
                if step is None:
                    step = -1 if stop < start else 1
            return Array(itertools.islice(self, start, stop, step))
        while True:
            if len(self.value_store) > key:
                return self.value_store[key]
            try:
                self.pop()
            except StopIteration as e:
                if len(self.value_store) > key:
                    return self.value_store[key]
                raise IndexError('Index {} is out of bounds for jqsh array'.format(key)) from e
    
    def __hash__(self):
        try:
            return hash(self[0])
        except IndexError:
            return -1
    
    def __init__(self, values=(), terminated=True):
        self.value_store = []
        super().__init__(*values, terminated=terminated)
    
    def __iter__(self):
        for index in itertools.count():
            try:
                yield self[index]
            except IndexError as e:
                raise StopIteration('Reached end of jqsh array') from e
    
    def __len__(self):
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return len(self.value_store)
    
    def __lt__(self, other):
        if any(isinstance(other, other_class) for other_class in (JQSHException, Null, Boolean, Number, String)):
            return False
        elif isinstance(other, Array):
            for index in itertools.count():
                if len(other) <= index: #TODO avoid calling len(other) if possible
                    return False
                elif len(self) <= index: #TODO avoid calling len(self) if possible
                    return True
                elif self[index] < other[index]:
                    return True
                elif self[index] > other[index]:
                    return False
        else:
            return True
    
    def __str__(self):
        return '[' + ', '.join(str(item) for item in self) + ']'
    
    def serializable(self):
        return all(serializable(item) for item in self)
    
    def store_value(self, value):
        self.value_store.append(value)
    
    def syntax_highlight_lines(self, terminal):
        if not terminal.does_styling:
            yield str(self)
            return
        has_items = False
        iter_self = more_itertools.peekable(self)
        for item in iter_self:
            if not has_items:
                yield terminal.bold(terminal.color(15)('['))
            try:
                iter_self.peek()
            except StopIteration:
                for line in item.syntax_highlight_lines(terminal):
                    yield ' ' * 2 + line
            else:
                iter_item = more_itertools.peekable(item.syntax_highlight_lines(terminal))
                for line in iter_item:
                    try:
                        iter_item.peek()
                    except StopIteration:
                        yield ' ' * 2 + line + terminal.color(15)(',')
                    else:
                        yield ' ' * 2 + line
            has_items = True
        if has_items:
            yield terminal.bold(terminal.color(15)(']'))
        else:
            yield terminal.bold(terminal.color(15)('[]'))
    
    @property
    def value(self):
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return [item.value for item in self.value_store]

class Object(Value, jqsh.channel.Channel, collections.abc.Mapping):
    @jqsh.channel.coerce_other
    def __eq__(self, other):
        if isinstance(other, Object):
            return set(self.items()) == set(other.items())
        else:
            return False
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            raise TypeError('Cannot slice jqsh objects')
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return self.value_store[key]
    
    def __hash__(self):
        return functools.reduce(operator.xor, (hash(key) for key in self), 0)
    
    def __init__(self, values=(), terminated=True):
        if isinstance(values, dict) or isinstance(values, Object):
            values = values.items()
        self.value_store = collections.OrderedDict()
        super().__init__(*values, terminated=terminated)
    
    def __iter__(self):
        return iter(self.keys())
    
    def __len__(self):
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return len(self.value_store)
    
    @jqsh.channel.coerce_other
    def __lt__(self, other):
        if any(isinstance(other, other_class) for other_class in (JQSHException, Null, Boolean, Number, String, Array)):
            return False
        elif isinstance(other, Object):
            self_keys = sorted(list(self.keys()))
            other_keys = sorted(list(other.keys()))
            if self_keys < other_keys:
                return True
            elif self_keys > other_keys:
                return False
            for key in self_keys:
                if self[key] < other[key]:
                    return True
                elif self[key] > other[key]:
                    return False
            return False
        else:
            return True
    
    def __str__(self):
        return '{' + ', '.join(str(key) + ': ' + str(item) for key, item in sorted(self.items())) + '}'
    
    def items(self):
        return ObjectItemsView(self)
    
    def keys(self):
        return ObjectKeysView(self)
    
    @jqsh.channel.coerce_other
    def push(self, value):
        error_message = 'Object channel only accepts pairs (arrays of 2 values)'
        if not isinstance(value, Array):
            raise TypeError(error_message)
        if len(value) != 2:
            raise ValueError(error_message)
        super().push(value)
    
    def serializable(self):
        return all(serializable(key) for key in self.keys()) and all(serializable(item) for item in self.values())
    
    def store_value(self, value):
        key, value = value
        self.value_store[key] = value
    
    def syntax_highlight_lines(self, terminal):
        if not terminal.does_styling:
            yield str(self)
            return
        has_items = False
        iter_self = more_itertools.peekable(sorted(list(self.keys())))
        for item in iter_self:
            if not has_items:
                yield terminal.bold(terminal.color(15)('{'))
            iter_key = more_itertools.peekable(item.syntax_highlight_lines(terminal))
            for line in iter_key:
                try:
                    iter_key.peek()
                except StopIteration:
                    last_key_line = line
                else:
                    yield ' ' * 2 + line
            try:
                iter_self.peek()
            except StopIteration:
                for line in self[item].syntax_highlight_lines(terminal):
                    if last_key_line is None:
                        yield ' ' * 2 + line
                    else:
                        yield ' ' * 2 + last_key_line + terminal.color(15)(': ') + line
                        last_key_line = None
            else:
                iter_item = more_itertools.peekable(self[item].syntax_highlight_lines(terminal))
                for line in iter_item:
                    try:
                        iter_item.peek()
                    except StopIteration:
                        if last_key_line is None:
                            yield ' ' * 2 + line + terminal.color(15)(',')
                        else:
                            yield ' ' * 2 + last_key_line + terminal.color(15)(': ') + line + terminal.color(15)(',')
                            last_key_line = None
                    else:
                        if last_key_line is None:
                            yield ' ' * 2 + line
                        else:
                            yield ' ' * 2 + last_key_line + terminal.color(15)(': ') + line
                            last_key_line = None
            has_items = True
        if has_items:
            yield terminal.bold(terminal.color(15)('}'))
        else:
            yield terminal.bold(terminal.color(15)('{}'))
    
    @property
    def value(self):
        while not self.terminated:
            with contextlib.suppress(StopIteration):
                self.pop()
        return [(key.value, item.value) for key, item in self.value_store.items()]
    
    def values(self):
        return ObjectValuesView(self)

class ObjectView:
    def __init__(self, obj):
        self._mapping = obj
    
    def __len__(self):
        return len(self._mapping)

class ObjectKeysView(ObjectView, collections.abc.KeysView):
    def __iter__(self):
        i = 0
        obj_iterator = iter(self._mapping.value_store)
        while not self._mapping.terminated:
            if i < len(self._mapping.value_store):
                i += 1
                yield next(obj_iterator)
            else:
                with contextlib.suppress(StopIteration):
                    self._mapping.pop()
        yield from obj_iterator

class ObjectValuesView(ObjectView, collections.abc.ValuesView):
    def __iter__(self):
        while not self._mapping.terminated:
            with contextlib.suppress(StopIteration):
                self._mapping.pop()
        yield from self._mapping.value_store.values()

class ObjectItemsView(ObjectView, collections.abc.ItemsView):
    def __iter__(self):
        while not self._mapping.terminated:
            with contextlib.suppress(StopIteration):
                self._mapping.pop()
        yield from self._mapping.value_store.items()
