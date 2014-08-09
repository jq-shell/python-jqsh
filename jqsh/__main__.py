#!/usr/bin/env python3

"""A shell based on jq.

Usage:
  jqsh [<module_file> [<arguments>...]]
  jqsh -c <filter> | --filter=<filter> [<arguments>...]
  jqsh -h | --help

Options:
  -c, --filter=<filter>  Apply this filter to the standard input instead of starting interactive mode.
  -h, --help             Print this message and exit.
"""

import sys

sys.path.append('/opt/py')

import jqsh.channel
import jqsh.context
import jqsh.cli
import jqsh.filter
import jqsh.parser
import json
import pathlib

arguments = sys.argv[1:]

filter_argument = None
module = None
parse_options = True

while len(arguments):
    if parse_options and (arguments[0].startswith('-c') or arguments[0].startswith('--filter=') or arguments[0] == '--filter'):
        if arguments[0] == '-c' and len(arguments) > 1:
            filter_argument = arguments[1]
            arguments = arguments[2:]
        elif arguments[0].startswith('-c'):
            filter_argument = arguments[0][len('-c'):]
            arguments.pop(0)
        elif arguments[0].startswith('--filter='):
            filter_argument = arguments[0][len('--filter='):]
            arguments.pop(0)
        elif arguments[0] == '--filter':
            filter_argument = arguments[1]
            arguments = arguments[2:]
    elif parse_options and (arguments[0] == '--help' or arguments[0].startswith('-h')):
        print('jqsh:', __doc__)
        sys.exit()
    elif parse_options and arguments[0] == '--':
        parse_options = False
        arguments.pop(0)
    elif parse_options and arguments[0].startswith('-') and len(arguments[0]) > 1:
        sys.exit('[!!!!] jqsh: invalid option: ' + arguments[0])
    elif filter_argument is None and module is None:
        module = pathlib.Path(arguments[0]) #TODO handle reading from stdin
        arguments.pop(0)
        parse_options = False
    else:
        break

if filter_argument is not None or module is not None:
    if sys.stdin.isatty():
        stdin_channel = jqsh.channel.Channel(context=jqsh.context.FilterContext.command_line_context(['--filter' if filter_argument is not None else module] + arguments), terminated=True)
    else:
        stdin_channel = jqsh.channel.Channel(*jqsh.parser.parse_json_values(sys.stdin.read()), context=jqsh.context.FilterContext.command_line_context(['--filter' if filter_argument is not None else module] + arguments), terminated=True) #TODO fix: this currently waits to read the entire stdin before even looking at the filter
    if module is None:
        try:
            the_filter = jqsh.parser.parse(filter_argument)
        except (SyntaxError, jqsh.parser.Incomplete) as e:
            sys.exit('[!!!!] jqsh: syntax error in filter: ' + str(e))
    else:
        with module.resolve().open() as module_file:
            try:
                the_filter = jqsh.parser.parse(module_file.read(), line_numbers=True)
            except (SyntaxError, jqsh.parser.Incomplete) as e:
                sys.exit('[!!!!] jqsh: syntax error reading module: ' + str(e))
    jqsh.cli.print_output(jqsh.filter.FilterThread(the_filter, input_channel=stdin_channel)) #TODO fix: this currently waits to read the entire module file before starting to tokenize it
    sys.exit()

global_namespace = {}
local_namespace = {}
format_strings = {}
while True: # a simple repl
    try:
        global_namespace, local_namespace, format_strings = jqsh.cli.print_output(jqsh.filter.FilterThread(jqsh.parser.parse(input('jqsh> ')), input_channel=jqsh.channel.Channel(global_namespace=global_namespace, local_namespace=local_namespace, format_strings=format_strings, terminated=True)))
    except EOFError:
        print('^D')
        break
    except KeyboardInterrupt:
        print() # add a newline after the Python-provided '^C'
        continue
    except (SyntaxError, jqsh.parser.Incomplete) as e:
        print('jqsh: syntax error: ' + str(e))
