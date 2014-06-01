#!/usr/bin/env python3

"""A shell based on jq.

Usage:
  jqsh
  jqsh -c <filter> | --filter=<filter>
  jqsh -h | --help

Options:
  -c, --filter=<filter>  Apply this filter to the standard input instead of starting interactive mode.
  -h, --help             Print this message and exit.
"""

import sys

import jqsh
import jqsh.channel
import jqsh.cli
import jqsh.filter
import jqsh.parser
import json

arguments = sys.argv[1:]

filter_argument = None

while len(arguments):
    if arguments[0].startswith('-c') or arguments[0].startswith('--filter=') or arguments[0] == '--filter':
        if arguments[0] == '-c' and len(arguments) > 1:
            filter_argument = arguments[1]
            arguments = arguments[2:]
        elif arguments[0].startswith('-c'):
            filter_argument = arguments[0][len('-c'):]
            arguments = arguments[1:]
        elif arguments[0].startswith('--filter='):
            filter_argument = arguments[0][len('--filter='):]
            arguments = arguments[1:]
        elif arguments[0] == '--filter':
            filter_argument = arguments[1]
            arguments = arguments[2:]
    elif arguments[0] == '--help' or arguments[0].startswith('-h'):
        print('jqsh:', __doc__)
        sys.exit()
    else:
        sys.exit('[!!!!] invalid argument: ' + arguments[0])

if filter_argument is not None:
    stdin_channel = jqsh.channel.Channel(*jqsh.parser.parse_json_values(sys.stdin.read()), terminated=True)
    jqsh.cli.print_output(jqsh.filter.FilterThread(jqsh.parser.parse(filter_argument), input_channel=stdin_channel))
    sys.exit()

while True: # a simple repl
    try:
        jqsh.cli.print_output(jqsh.parser.parse(input('jqsh> ')))
    except EOFError:
        print('^D')
        break
    except KeyboardInterrupt:
        print() # add a newline after the Python-provided '^C'
        continue
    except (SyntaxError, jqsh.parser.Incomplete) as e:
        print('jqsh: syntax error: ' + str(e))
