import sys

import jqsh.parser
import json

while True: # a simple repl
    try:
        for value in jqsh.parser.parse(input('jqsh> ')).start():
            json.dump(value, sys.stdout, sort_keys=True, indent=4, separators=(',', ': '))
            print() # add a newline because json.dump doesn't end its values with newlines
    except EOFError:
        print('^D')
        break
    except KeyboardInterrupt:
        print() # add a newline after the Python-provided '^C'
        continue
    except SyntaxError as e:
        print('jqsh: syntax error: ' + str(e))
