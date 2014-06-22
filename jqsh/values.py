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
        if self.name == 'assignment' and 'target_filter' in self.kwargs:
            print('cannot assign to filter of type ' + self.kwargs['target_filter'].__class__.__name__, file=output_file, flush=True)
        elif self.name == 'internal' and 'exc_info' in self.kwargs:
            traceback.print_exception(*self.kwargs['exc_info'], file=output_file)
        elif self.name == 'name' and 'missing_name' in self.kwargs:
            print('name ' + self.kwargs['missing_name'] + ' is not defined', file=output_file, flush=True)
        elif self.name == 'notImplemented' and 'filter' in self.kwargs:
            print('filter ' + self.kwargs['filter'].__class__.__name__ + ' not yet implemented' + (' for attributes ' + repr(self.kwargs['attributes']) if 'attributes' in self.kwargs else ''), file=output_file, flush=True)
        elif self.name == 'numArgs' and 'expected' in self.kwargs:
            print('wrong number of function arguments: ' + ('received ' + str(self.kwargs['received']) + ', ') + 'expected ' + ('any of ' if len(self.kwargs['expected']) > 1 else '') + ', '.join(str(num_args) for num_args in sorted(self.kwargs['expected'])), file=output_file, flush=True)
