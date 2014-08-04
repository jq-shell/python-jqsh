import sys

import blessings
import jqsh.filter
import jqsh.parser
import jqsh.values

def print_output(filter_thread, output_file=None):
    terminal = blessings.Terminal()
    if output_file is None:
        output_file = sys.stdout
    if isinstance(filter_thread, jqsh.filter.Filter):
        filter_thread = jqsh.filter.FilterThread(filter_thread)
    filter_thread.start()
    while True:
        try:
            value = filter_thread.output_channel.pop()
        except StopIteration:
            break
        for line in value.syntax_highlight_lines(terminal):
            print(line, file=output_file, flush=True)
    return filter_thread.output_channel.namespaces()
