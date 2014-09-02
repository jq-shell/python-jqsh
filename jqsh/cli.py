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
    for value in filter_thread.output_channel:
        value.print_to_terminal(terminal, output_file)
    return filter_thread.output_channel.namespaces()
