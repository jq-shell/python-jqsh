import jqsh.channel
import threading

class FilterThread(threading.Thread):
    def __init__(self, the_filter, input_channel=None):
        super().__init__(name='jqsh FilterThread')
        self.filter = the_filter
        if input_channel is None:
            input_channel = jqsh.channel.Channel()
            input_channel.terminate()
        self.input_channel = input_channel
        self.output_channel = jqsh.channel.Channel()

    def run(self):
        for value in self.filter.run(self.input_channel):
            self.output_channel.push(value)
        self.output_channel.terminate()

class Filter:
    """Filters are the basic building block of the jqsh language. This base class implements the empty filter."""
    def __repr__(self):
        return 'jqsh.filter.' + self.__class__.__name__ + '()'
    
    def __str__(self):
        """The filter's representation in jqsh."""
        return ''
    
    def run(self, input_channel):
        """This is called from the filter thread, and should be overridden by subclasses.
        
        Yielded values are pushed onto the output channel, and it is terminated on return.
        """
        return
        yield # the empty generator #FROM http://stackoverflow.com/a/13243870/667338
    
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
