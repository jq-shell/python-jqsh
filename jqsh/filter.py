import decimal
import jqsh
import jqsh.channel
import jqsh.functions
import threading

class NotAllowed(Exception):
    pass

class FilterThread(threading.Thread):
    def __init__(self, the_filter, input_channel=None):
        super().__init__(name='jqsh FilterThread')
        self.filter = the_filter
        self.input_channel = jqsh.channel.Channel(terminated=True) if input_channel is None else input_channel
        self.output_channel = jqsh.channel.Channel()
    
    def run(self):
        self.filter.run_raw(self.input_channel, self.output_channel)

class Filter:
    """Filters are the basic building block of the jqsh language. This base class implements the empty filter."""
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '()'
    
    def __str__(self):
        """The filter's representation in jqsh."""
        return ''
    
    def run(self, input_channel):
        """This is called from run_raw, and should be overridden by subclasses.
        
        Yielded values are pushed onto the output channel, and it is terminated on return. Exceptions are handled by run_raw.
        """
        return
        yield # the empty generator #FROM http://stackoverflow.com/a/13243870/667338
    
    def run_raw(self, input_channel, output_channel):
        """This is called from the filter thread, and may be overridden by subclasses instead of run."""
        def run_thread(bridge):
            try:
                for value in self.run(input_channel=bridge):
                    output_channel.push(value)
                    if isinstance(value, Exception):
                        break
            except:
                output_channel.push(Exception('internal'))
        
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
    
    def start(self, input_channel=None):
        filter_thread = FilterThread(self, input_channel=input_channel)
        filter_thread.start()
        return filter_thread.output_channel

class Parens(Filter):
    def __init__(self, attribute=Filter()):
        self.attribute = attribute
    
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '(' + ('' if self.attribute.__class__ == Filter else repr(self.attribute)) + ')'
    
    def __str__(self):
        return '(' + str(self.attribute) + ')'
    
    def run(self, input_channel):
        yield from self.attribute.start(input_channel)

class Array(Parens):
    def __str__(self):
        return '[' + str(self.attribute) + ']'
    
    def run(self, input_channel):
        yield list(self.attribute.start(input_channel))

class Name(Filter):
    def __init__(self, name):
        self.name = name
    
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '(' + repr(self.name) + ')'
    
    def __str__(self):
        return self.name
    
    def run_raw(self, input_channel, output_channel):
        try:
            builtin = jqsh.functions.get_builtin(self.name)
        except KeyError:
            output_channel.push(Exception('numArgs' if self.name in jqsh.functions.builtin_functions else 'name'))
            output_channel.terminate()
        else:
            builtin(input_channel=input_channel, output_channel=output_channel)

class NumberLiteral(Filter):
    def __init__(self, number):
        self.number_string = str(number)
        self.number = number if isinstance(number, decimal.Decimal) else decimal.Decimal(number)
    
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '(' + repr(self.number_string) + ')'
    
    def __str__(self):
        return self.number_string
    
    def run(self, input_channel):
        yield decimal.Decimal(self.number)

class StringLiteral(Filter):
    def __init__(self, text):
        self.text = text
    
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '(' + repr(self.text) + ')'
    
    def __str__(self):
        return '"' + ''.join(self.escape(c) for c in self.name) + '"'
    
    @staticmethod
    def escape(character):
        if character == '\b':
            return '\\b'
        elif character == '\t':
            return '\\t'
        elif character == '\n':
            return '\\n'
        elif character == '\f':
            return '\\f'
        elif character == '\r':
            return '\\r'
        elif character == '"':
            return '\\"'
        elif character == '\\':
            return '\\\\'
        elif ord(character) <= 0x1f:
            return '\\u{:04x}'.format(ord(character))
        else:
            return character
    
    @staticmethod
    def representation(the_string):
        return '"' + ''.join(StringLiteral.escape(character) for character in str(the_string)) + '"'
    
    def run(self, input_channel):
        yield self.text

class Operator(Filter):
    """Abstract base class for operator filters."""
    
    def __init__(self, *, left=Filter(), right=Filter()):
        self.left_operand = left
        self.right_operand = right
    
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '(' + ('' if self.left_operand.__class__ == Filter else 'left=' + repr(self.left_operand) + ('' if self.right_operand.__class__ == Filter else ', ')) + ('' if self.right_operand.__class__ == Filter else 'right=' + repr(self.right_operand)) + ')'

class Pipe(Operator):
    def __str__(self):
        return str(self.left_operand) + ' | ' + str(self.right_operand)
    
    def run(self, input_channel):
        left_output = self.left_operand.start(input_channel)
        yield from self.right_operand.start(left_output)

class Apply(Operator):
    def __init__(self, *attributes, left=Filter(), right=Filter()):
        if len(attributes):
            self.attributes = attributes
            self.variadic_form = True
        else:
            self.attributes = [left, right]
            self.variadic_form = False
    
    def __repr__(self):
        if self.variadic_form:
            return 'jqsh.filter.' + self.__class__.__name__ + '(' + ', '.join(repr(attribute) for attribute in self.attributes) + ')'
        else:
            return 'jqsh.filter.' + self.__class__.__name__ + '(' + ('' if self.attributes[0].__class__ == Filter else 'left=' + repr(self.attributes[0]) + ('' if self.attributes[1].__class__ == Filter else ', ')) + ('' if self.attributes[1].__class__ == Filter else 'right=' + repr(self.attributes[1])) + ')'
    
    def __str__(self):
        if self.variadic_form:
            return ' '.join(str(attribute) for attribute in self.attributes)
        else:
            return str(self.attributes[0]) + '.' + str(self.attributes[1])
    
    def run(self, input_channel):
        if all(attribute.__class__ == Filter for attribute in self.attributes):
            yield from input_channel
        elif len(self.attributes) == 2 and all(attribute.__class__ == NumberLiteral for attribute in self.attributes):
            yield decimal.Decimal(str(self.attributes[0]) + '.' + str(self.attributes[1]))
        else:
            yield Exception('notImplemented')
            

class Comma(Operator):
    def __str__(self):
        return str(self.left_operand) + ', ' + str(self.right_operand)
    
    def run(self, input_channel):
        left_input, right_input = input_channel / 2
        right_output = self.right_operand.start(right_input)
        yield from self.left_operand.start(left_input)
        yield from right_output
