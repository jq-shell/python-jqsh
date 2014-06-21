import sys
import traceback

class JQSHException:
    def __eq__(self, other):
        return isinstance(other, JQSHException) and self.name == other.name
    
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
    
    def print(self, output_file=None):
        if output_file is None:
            output_file=sys.stdout
        print('\rjqsh: uncaught exception:', end=' ', file=output_file, flush=True)
        print(self.name, file=output_file, flush=True)
        if self.name == 'internal' and 'exc_info' in self.kwargs:
            traceback.print_exception(*self.kwargs['exc_info'])
