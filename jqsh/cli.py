import sys

import jqsh
import jqsh.filter
import jqsh.parser

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
        if token.type is jqsh.parser.TokenType.name and token.text == 'raise':
            print('\rjqsh: uncaught exception:', end=' ', file=output_file, flush=True)
            print(filter_thread.output_channel.pop().text, file=output_file, flush=True)
            break
        else:
            print(syntax_highlight(token), end='', file=output_file, flush=True)

def syntax_highlight(token):
    #TODO add actual highlighting
    return str(token)
