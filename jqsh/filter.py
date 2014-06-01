import jqsh
import jqsh.channel
import jqsh.functions
import threading

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
            for value in self.run(input_channel=bridge):
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
    def __init__(self, text):
        self.name = text
    
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
