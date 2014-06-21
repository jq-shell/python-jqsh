import sys

import jqsh
import jqsh.filter
import jqsh.parser
import jqsh.values

def print_output(filter_thread, output_file=None):
    if output_file is None:
        output_file = sys.stdout
    if isinstance(filter_thread, jqsh.filter.Filter):
        filter_thread = jqsh.filter.FilterThread(filter_thread)
    filter_thread.start()
    while True:
        try:
            token = filter_thread.output_channel.pop()
        except StopIteration:
            break
        if isinstance(token, jqsh.values.JQSHException):
            token.print(output_file=output_file)
            break
        else:
            print(syntax_highlight(token), end='', file=output_file, flush=True)

def syntax_highlight(token):
    #TODO add actual highlighting
    return str(token)
