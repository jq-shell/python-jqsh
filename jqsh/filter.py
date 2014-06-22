import sys

import copy
import decimal
import jqsh
import jqsh.channel
import jqsh.functions
import jqsh.values
import subprocess
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
    
    @staticmethod
    def handle_namespace(namespace_name, input_channel, output_channels):
        """Waits until the namespace is available in the input channel, then passes it unchanged to the output channels. Used by run_raw."""
        namespace_value = getattr(input_channel, namespace_name)
        for chan in output_channels:
            setattr(chan, namespace_name, namespace_value)
    
    def assign(self, value_channel, input_channel, output_channel):
        raise NotImplementedError('cannot assign to this filter')
    
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
                    if isinstance(value, jqsh.values.JQSHException):
                        break
            except Exception as e:
                output_channel.push(jqsh.values.JQSHException('internal', python_exception=e, exc_info=sys.exc_info()))
        
        bridge_channel = jqsh.channel.Channel()
        helper_thread = threading.Thread(target=run_thread, kwargs={'bridge': bridge_channel})
        handle_globals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'global_namespace', 'input_channel': input_channel, 'output_channels': [bridge_channel, output_channel]})
        handle_locals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'local_namespace', 'input_channel': input_channel, 'output_channels': [bridge_channel, output_channel]})
        handle_format_strings = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': input_channel, 'output_channels': [bridge_channel, output_channel]})
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
            if isinstance(token, jqsh.values.JQSHException):
                output_channel.push(token)
                break
        bridge_channel.terminate()
        helper_thread.join()
        handle_globals.join()
        handle_locals.join()
        handle_format_strings.join()
        output_channel.terminate()
    
    def sensible_string(self, input_channel=None):
        ret = next(self.start(input_channel))
        if isinstance(ret, str):
            return ret
        else:
            raise TypeError('got a ' + ret.__class__.__name__ + ', expected a string')
    
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
    
    def assign(self, value_channel, input_channel, output_channel):
        def handle_values():
            while True:
                try:
                    output_channel.push(input_channel.pop())
                except StopIteration:
                    break
            output_channel.terminate()
        
        handle_globals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'global_namespace', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_format_strings = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_values = threading.Thread(target=handle_values)
        handle_globals.start()
        handle_format_strings.start()
        handle_values.start()
        input_locals = copy.copy(input_channel.local_namespace)
        var = list(value_channel)
        for value in var:
            if isinstance(value, jqsh.values.JQSHException):
                output_channel.push(value)
                break
        else:
            input_locals[self.name] = var
        output_channel.local_namespace = input_locals
        output_channel.terminate()
        handle_globals.join()
        handle_format_strings.join()
        handle_values.join()
    
    def run_raw(self, input_channel, output_channel):
        handle_globals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'global_namespace', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_locals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'local_namespace', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_format_strings = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_globals.start()
        handle_locals.start()
        handle_format_strings.start()
        if self.name in input_channel.local_namespace:
            for value in input_channel.local_namespace[self.name]:
                output_channel.push(value)
            output_channel.terminate()
        else:
            try:
                builtin = jqsh.functions.get_builtin(self.name)
            except KeyError:
                output_channel.push(jqsh.values.JQSHException('numArgs', function_name=self.name, expected=set(jqsh.functions.builtin_functions[self.name]), received=0) if self.name in jqsh.functions.builtin_functions else jqsh.values.JQSHException('name', missing_name=self.name))
                output_channel.terminate()
            else:
                builtin(input_channel=input_channel, output_channel=output_channel)
        handle_globals.join()
        handle_locals.join()
        handle_format_strings.join()
    
    def sensible_string(self, input_channel=None):
        return self.name

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
        return '"' + ''.join(self.escape(c) for c in self.text) + '"'
    
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
    
    def __str__(self):
        return str(self.left_operand) + self.operator_string + str(self.right_operand)
    
    def output_pairs(self, input_channel):
        #TODO don't block until both operands have terminated
        left_input, right_input = input_channel / 2
        left_output = list(self.left_operand.start(left_input))
        right_output = list(self.right_operand.start(right_input))
        if len(left_output) == 0 and len(right_output) == 0:
            return
        elif len(left_output) == 0:
            yield from right_output
        elif len(right_output) == 0:
            yield from left_output
        else:
            for i in range(max(len(left_output), len(right_output))):
                yield left_output[i % len(left_output)], right_output[i % len(right_output)]

class Pipe(Operator):
    operator_string = ' | '
    
    def run(self, input_channel):
        left_output = self.left_operand.start(input_channel)
        yield from self.right_operand.start(left_output)

class Add(Operator):
    operator_string = ' + '
    
    def run(self, input_channel):
        for output in self.output_pairs(input_channel):
            if isinstance(output, tuple):
                left_output, right_output = output
            else:
                yield output
                continue
            if any(all(isinstance(output, value_type) for output in (left_output, right_output)) for value_type in (decimal.Decimal, list, str)):
                yield left_output + right_output
            elif all(isinstance(output, dict) for output in (left_output, right_output)):
                ret = copy.copy(left_output)
                ret.update(right_output)
                yield ret
            else:
                yield jqsh.values.JQSHException('type')

class Apply(Operator):
    operator_string = '.'
    
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
    
    def run_raw(self, input_channel, output_channel):
        if all(attribute.__class__ == Filter for attribute in self.attributes):
            output_channel.pull(input_channel)
        elif len(self.attributes) == 2 and all(attribute.__class__ == NumberLiteral for attribute in self.attributes):
            output_channel.push(decimal.Decimal(str(self.attributes[0]) + '.' + str(self.attributes[1])))
            output_channel.terminate()
        else:
            input_channel, string_input = input_channel / 2
            try:
                function_name = self.attributes[0].sensible_string(input_channel=string_input)
                builtin = jqsh.functions.get_builtin(function_name, *self.attributes[1:])
            except KeyError:
                output_channel.push(jqsh.values.JQSHException('numArgs') if function_name in jqsh.functions.builtin_functions else jqsh.values.JQSHException('name', missing_name=function_name))
                output_channel.terminate()
            else:
                builtin(*self.attributes[1:], input_channel=input_channel, output_channel=output_channel)

class Assign(Operator):
    operator_string = ' = '
    
    def run_raw(self, input_channel, output_channel):
        input_channel, assignment_input = input_channel / 2
        try:
            self.left_operand.assign(self.right_operand.start(input_channel), input_channel=assignment_input, output_channel=output_channel)
        except NotImplementedError:
            output_channel.push(jqsh.values.JQSHException('assignment', target_filter=self.left_operand))
            output_channel.get_namespaces(input_channel)
            output_channel.terminate()

class Comma(Operator):
    def __str__(self):
        return str(self.left_operand) + ', ' + str(self.right_operand)
    
    def run(self, input_channel):
        left_input, right_input = input_channel / 2
        right_output = self.right_operand.start(right_input)
        yield from self.left_operand.start(left_input)
        yield from right_output

class Multiply(Operator):
    operator_string = ' * '
    
    def run(self, input_channel):
        for output in self.output_pairs(input_channel):
            if isinstance(output, tuple):
                left_output, right_output = output
            else:
                yield output
                continue
            if isinstance(left_output, decimal.Decimal) and isinstance(right_output, decimal.Decimal):
                yield left_output * right_output
            elif any(isinstance(left_output, value_type) for value_type in (list, str)) and isinstance(right_output, decimal.Decimal):
                if right_output % 1 == 0:
                    yield left_output * int(right_output)
                else:
                    yield jqsh.values.JQSHException('integer')
            elif isinstance(left_output, decimal.Decimal) and any(isinstance(right_output, value_type) for value_type in (list, str)):
                if right_output % 1 == 0:
                    yield int(left_output) * right_output
                else:
                    yield jqsh.values.JQSHException('integer')
            else:
                yield jqsh.values.JQSHException('type')

class Semicolon(Operator):
    operator_string = '; '
    
    def run_raw(self, input_channel, output_channel):
        left_input, right_input = input_channel / 2
        left_output = self.left_operand.start(left_input)
        right_input.get_namespaces(left_output)
        right_output = self.right_operand.start(right_input)
        for value in right_output:
            output_channel.push(value)
        output_channel.terminate()
        output_channel.get_namespaces(right_output)

class UnaryOperator(Filter):
    """Abstract base class for unary-only operator filters."""
    
    def __init__(self, attribute):
        self.attribute = attribute
    
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '(' + repr(self.attribute) + ')'
    
    def __str__(self):
        return self.operator_string + str(self.attribute)

class Command(UnaryOperator):
    operator_string = '!'
    
    def run(self, input_channel):
        import jqsh.parser
        input_channel, attribute_input = input_channel / 2
        try:
            command_name = self.attribute.sensible_string(attribute_input)
        except (StopIteration, TypeError):
            yield jqsh.values.JQSHException('sensibleString')
            return
        try:
            popen = subprocess.Popen(command_name, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            yield jqsh.values.JQSHException('path')
            return
        except PermissionError:
            yield jqsh.values.JQSHException('permission')
            return
        for value in input_channel:
            popen.stdin.write(b''.join(str(token).encode('utf-8') for token in jqsh.parser.json_to_tokens(value, indent_width=None)))
        popen.stdin.write(b'\x04')
        try:
            yield from jqsh.parser.parse_json_values(popen.stdout.read().decode('utf-8'))
        except (UnicodeDecodeError, SyntaxError, jqsh.parser.Incomplete):
            yield jqsh.values.JQSHException('commandOutput')

class GlobalVariable(UnaryOperator):
    operator_string = '$'
    
    def assign(self, value_channel, input_channel, output_channel):
        def handle_values():
            while True:
                try:
                    output_channel.push(input_channel.pop())
                except StopIteration:
                    break
            output_channel.terminate()
        
        handle_locals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'local_namespace', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_format_strings = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_values = threading.Thread(target=handle_values)
        handle_locals.start()
        handle_format_strings.start()
        handle_values.start()
        input_globals = copy.copy(input_channel.global_namespace)
        try:
            variable_name = self.attribute.sensible_string(input_channel)
        except (StopIteration, TypeError):
            output_channel.push(jqsh.values.JQSHException('sensibleString'))
        else:
            var = list(value_channel)
            for value in var:
                if isinstance(value, jqsh.values.JQSHException):
                    output_channel.push(value)
                    break
            else:
                input_globals[variable_name] = var
        output_channel.global_namespace = input_globals
        output_channel.terminate()
        handle_locals.join()
        handle_format_strings.join()
        handle_values.join()
    
    def run_raw(self, input_channel, output_channel):
        handle_globals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'global_namespace', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_locals = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'local_namespace', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_format_strings = threading.Thread(target=self.handle_namespace, kwargs={'namespace_name': 'format_strings', 'input_channel': input_channel, 'output_channels': [output_channel]})
        handle_globals.start()
        handle_locals.start()
        handle_format_strings.start()
        try:
            variable_name = self.attribute.sensible_string(input_channel)
        except (StopIteration, TypeError):
            output_channel.push(jqsh.values.JQSHException('sensibleString'))
        else:
            if variable_name in input_channel.global_namespace:
                for value in input_channel.global_namespace[variable_name]:
                    output_channel.push(value)
            else:
                output_channel.push(jqsh.values.JQSHException('name', missing_name=variable_name))
        output_channel.terminate()
        handle_globals.join()
        handle_locals.join()
        handle_format_strings.join()
