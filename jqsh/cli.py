import sys

import jqsh
import jqsh.filter
import json

def print_output(filter_thread, output_file=None):
    if output_file is None:
        output_file = sys.stdout
    if isinstance(filter_thread, jqsh.filter.Filter):
        filter_thread = jqsh.filter.FilterThread(filter_thread)
    filter_thread.start()
    for value in filter_thread.output_channel:
        if isinstance(value, Exception):
            print('jqsh: uncaught exception: ' + str(value), file=output_file, flush=True)
        else:
            json.dump(value, output_file, sort_keys=True, indent=2)
            print(file=output_file, flush=True) # add a newline because json.dump doesn't end its values with newlines
