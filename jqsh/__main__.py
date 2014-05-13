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
    #TODO parse stdin
    for value in jqsh.parser.parse(filter_argument).start():
        json.dump(value, sys.stdout, sort_keys=True, indent=2, separators=(',', ': '))
        print() # add a newline because json.dump doesn't end its values with newlines
    sys.exit()

while True: # a simple repl
    try:
        for value in jqsh.parser.parse(input('jqsh> ')).start():
            json.dump(value, sys.stdout, sort_keys=True, indent=2, separators=(',', ': '))
            print() # add a newline because json.dump doesn't end its values with newlines
    except EOFError:
        print('^D')
        break
    except KeyboardInterrupt:
        print() # add a newline after the Python-provided '^C'
        continue
    except SyntaxError as e:
        print('jqsh: syntax error: ' + str(e))
