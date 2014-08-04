import decimal
import enum
import jqsh.context
import jqsh.filter
import jqsh.values
import string
import unicodedata

class Incomplete(Exception):
    pass

TokenType = enum.Enum('TokenType', [
    'assign',
    'close_array',
    'close_object',
    'close_paren',
    'colon',
    'comma',
    'command',
    'comment',
    'dot',
    'format_string',
    'global_variable',
    'illegal',
    'minus',
    'modulo',
    'multiply',
    'name',
    'number',
    'open_array',
    'open_object',
    'open_paren',
    'pipe',
    'plus',
    'semicolon',
    'string',
    'string_end',
    'string_end_incomplete',
    'string_incomplete',
    'string_middle',
    'string_start',
    'trailing_whitespace'
], module=__name__)

class Token:
    def __eq__(self, other):
        return self.type is other.type and self.text == other.text
    
    def __init__(self, token_type, token_string=None, text=None, line=None, column=None):
        self.type = token_type
        self.string = token_string # ''.join(token.string for token in tokenize(jqsh_string)) == jqsh_string
        self.text = text # metadata like the name of a name token or the digits of a number literal. None for simple tokens
        self.line = line
        self.column = column
    
    def __repr__(self):
        return 'jqsh.parser.Token(' + repr(self.type) + ('' if self.string is None else ', token_string=' + repr(self.string)) + ('' if self.text is None else ', text=' + repr(self.text)) + ')'
    
    def __str__(self):
        if self.string is None:
            return "'" + repr(self) + "'"
        else:
            return self.string

atomic_tokens = {
    TokenType.name: jqsh.filter.Name,
    TokenType.number: jqsh.filter.NumberLiteral,
    TokenType.string: jqsh.filter.StringLiteral
}

escapes = { # string literal escape sequences, sans \u and \(
    '"': '"',
    '/': '/',
    '\\': '\\',
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t'
}

json_tokens = [ # token types that are allowed in pure JSON
    TokenType.close_array,
    TokenType.close_object,
    TokenType.colon,
    TokenType.comma,
    TokenType.name,
    TokenType.number,
    TokenType.open_array,
    TokenType.open_object,
    TokenType.string
]

matching_parens = { # a dictionary that maps opening parenthesis-like tokens (parens) to the associated closing parens
    TokenType.open_array: TokenType.close_array,
    TokenType.open_object: TokenType.close_object,
    TokenType.open_paren: TokenType.close_paren
}

operators = [
    {
        'binary': False,
        TokenType.command: jqsh.filter.Command,
        TokenType.global_variable: jqsh.filter.GlobalVariable
    },
    {
        TokenType.dot: jqsh.filter.Apply
    },
    'variadic apply',
    {
        TokenType.multiply: jqsh.filter.Multiply
    },
    {
        TokenType.plus: jqsh.filter.Add
    },
    {
        TokenType.colon: jqsh.filter.Pair
    },
    {
        TokenType.comma: jqsh.filter.Comma
    },
    {
        TokenType.assign: jqsh.filter.Assign
    },
    {
        'rtl': True,
        TokenType.pipe: jqsh.filter.Pipe
    },
    {
        TokenType.semicolon: jqsh.filter.Semicolon
    }
]

paren_filters = {
    TokenType.open_array: jqsh.filter.Array,
    TokenType.open_object: jqsh.filter.Object,
    TokenType.open_paren: jqsh.filter.Parens
}

symbols = {
    '!': TokenType.command,
    '$': TokenType.global_variable,
    '%': TokenType.modulo,
    '(': TokenType.open_paren,
    ')': TokenType.close_paren,
    '*': TokenType.multiply,
    '+': TokenType.plus,
    ',': TokenType.comma,
    '-': TokenType.minus,
    '.': TokenType.dot,
    ':': TokenType.colon,
    ';': TokenType.semicolon,
    '=': TokenType.assign,
    '@': TokenType.format_string,
    '[': TokenType.open_array,
    ']': TokenType.close_array,
    '{': TokenType.open_object,
    '|': TokenType.pipe,
    '}': TokenType.close_object
}

def illegal_token_exception(token, position=None, expected=None, line_numbers=False):
    if token.type is TokenType.illegal and token.text:
        return SyntaxError('illegal character' + ((' in line ' + str(token.line) if line_numbers and token.line is not None else '') if position is None else ' at position ' + repr(position)) + ': ' + repr(token.text[0]) + ' (U+' + format(ord(token.text[0]), 'x').upper() + ' ' + unicodedata.name(token.text[0], 'unknown character') + ')')
    else:
        return SyntaxError('illegal ' + ('' if token.type is TokenType.illegal else token.type.name + ' ') + 'token' + ((' in line ' + str(token.line) if line_numbers and token.line is not None else '') if position is None else ' at position ' + repr(position)) + ('' if expected is None else ' (expected ' + ' or '.join(sorted(expected_token_type.name for expected_token_type in expected)) + ')'))

def json_to_tokens(json_value, *, allow_extension_types=False, indent_level=0, indent_width=2):
    single_indent = '' if indent_width is None else ' ' * indent_width
    indent = single_indent * indent_level
    if allow_extension_types and isinstance(json_value, tuple) and len(json_value) == 2:
        yield Token(TokenType.open_paren, token_string='(' + ('' if indent_width is None else '\n' + indent + single_indent))
        yield from json_to_tokens(json_value[0], allow_extension_types=allow_extension_types, indent_level=indent_level + 1, indent_width=indent_width)
        yield Token(TokenType.colon, token_string=': ')
        yield from json_to_tokens(json_value[1], allow_extension_types=allow_extension_types, indent_level=indent_level + 1, indent_width=indent_width)
        yield Token(TokenType.close_paren, token_string=('' if indent_width is None else '\n' + indent) + ')' + ('\n' if indent_level == 0 else ''))
    elif json_value is False:
        yield Token(TokenType.name, token_string='false' + ('\n' if indent_level == 0 else ''), text='false')
    elif json_value is None:
        yield Token(TokenType.name, token_string='null' + ('\n' if indent_level == 0 else ''), text='null')
    elif allow_extension_types and isinstance(json_value, jqsh.values.JQSHException):
        yield json_value
    elif json_value is True:
        yield Token(TokenType.name, token_string='true' + ('\n' if indent_level == 0 else ''), text='true')
    elif isinstance(json_value, decimal.Decimal) or isinstance(json_value, int) or isinstance(json_value, float):
        yield Token(TokenType.number, token_string=str(json_value) + ('\n' if indent_level == 0 else ''), text=str(json_value))
    elif isinstance(json_value, list):
        yield Token(TokenType.open_array, token_string=('[' + '\n' + indent + single_indent if indent_width is not None and len(json_value) else '['))
        for i, item in enumerate(json_value):
            if i > 0:
                yield Token(TokenType.comma, token_string=',' + (' ' if indent_width is None else '\n' + indent + single_indent))
            yield from json_to_tokens(item, allow_extension_types=allow_extension_types, indent_level=indent_level + 1, indent_width=indent_width)
        yield Token(TokenType.close_array, token_string=('\n' + indent + ']' if indent_width is not None and len(json_value) else ']') + ('\n' if indent_level == 0 else ''))
    elif isinstance(json_value, dict):
        yield Token(TokenType.open_object, token_string=('{' + '\n' + indent + single_indent if indent_width is not None and len(json_value) else '{'))
        for i, (key, value) in enumerate(sorted(json_value.items(), key=lambda pair: pair[0])): # sort the pairs of an object by their names
            if i > 0:
                yield Token(TokenType.comma, token_string=',' + (' ' if indent_width is None else '\n' + indent + single_indent))
            yield Token(TokenType.string, token_string=jqsh.filter.StringLiteral.representation(key), text=key)
            yield Token(TokenType.colon, token_string=': ')
            yield from json_to_tokens(value, allow_extension_types=allow_extension_types, indent_level=indent_level + 1, indent_width=indent_width)
        yield Token(TokenType.close_object, token_string=('\n' + indent + '}' if indent_width is not None and len(json_value) else '}') + ('\n' if indent_level == 0 else ''))
    elif isinstance(json_value, str):
        yield Token(TokenType.string, token_string=jqsh.filter.StringLiteral.representation(json_value) + ('\n' if indent_level == 0 else ''), text=json_value)
    else:
        yield Token(TokenType.illegal)

def parse(tokens, *, line_numbers=False, allowed_filters={'default': True}, context=jqsh.context.FilterContext()):
    def filter_is_allowed(the_filter):
        if isinstance(allowed_filters, dict):
            if the_filter.__class__ in allowed_filters:
                if isinstance(allowed_filters[the_filter.__class__], bool):
                    return allowed_filters[the_filter.__class__]
                else:
                    return allowed_filters[the_filter.__class__](the_filter)
            else:
                if isinstance(allowed_filters.get('default', False), bool):
                    return allowed_filters.get('default', False)
                else:
                    return allowed_filters['default'](the_filter)
        elif the_filter.__class__ in allowed_filters:
            return True
        else:
            return False
    
    def raise_for_filter(the_filter):
        if filter_is_allowed(the_filter):
            return the_filter
        else:
            raise jqsh.filter.NotAllowed('disallowed filter: ' + str(the_filter))
    
    if isinstance(tokens, str):
        tokens = list(tokenize(tokens))
    tokens = [token for token in tokens if isinstance(token, jqsh.filter.Filter) or token.type is not TokenType.comment]
    if not len(tokens):
        return raise_for_filter(jqsh.filter.Filter()) # token list is empty, return an empty filter
    for token in tokens:
        if token.type is TokenType.illegal:
            raise illegal_token_exception(token, line_numbers=line_numbers)
    if isinstance(tokens[-1], Token) and tokens[-1].type is TokenType.trailing_whitespace:
        if len(tokens) == 1:
            return raise_for_filter(jqsh.filter.Filter()) # token list consists entirely of whitespace, return an empty filter
        else:
            tokens[-2].string += tokens[-1].string # merge the trailing whitespace into the second-to-last token
            tokens.pop() # remove the trailing_whitespace token
    
    # parenthesis-like filters
    paren_balance = 0
    paren_start = None
    for i, token in reversed(list(enumerate(tokens))): # iterating over the token list in reverse because we modify it in the process
        if not isinstance(token, Token):
            continue
        elif token.type in matching_parens.values():
            if paren_balance == 0:
                paren_start = i
            paren_balance += 1
        elif token.type in matching_parens.keys():
            paren_balance -= 1
            if paren_balance < 0:
                raise Incomplete('too many opening parens of type ' + repr(token.type))
            elif paren_balance == 0:
                if matching_parens[token.type] is tokens[paren_start].type:
                    tokens[i:paren_start + 1] = [raise_for_filter(paren_filters[token.type](attribute=parse(tokens[i + 1:paren_start], line_numbers=line_numbers, allowed_filters=allowed_filters)))] # parse the inside of the parens
                else:
                    raise SyntaxError('opening paren of type ' + repr(token.type) + ' does not match closing paren of type ' + repr(tokens[paren_start].type))
                paren_start = None
    if paren_balance != 0:
        raise SyntaxError('mismatched parens')
    
    # atomic filters
    for i, token in reversed(list(enumerate(tokens))):
        if isinstance(token, Token) and token.type in atomic_tokens:
            tokens[i] = raise_for_filter(atomic_tokens[token.type](token.text))
    
    # operators
    for precedence_group in operators:
        if precedence_group == 'variadic apply':
            start = None
            for i, token in reversed(list(enumerate(tokens))):
                if isinstance(token, jqsh.filter.Filter):
                    if start is None:
                        start = i
                else:
                    if start is not None and start > i + 1:
                        tokens[i + 1:start + 1] = [raise_for_filter(jqsh.filter.Apply(*tokens[i + 1:start + 1]))]
                    start = None
            if start is not None and start > 0:
                tokens[:start + 1] = [raise_for_filter(jqsh.filter.Apply(*tokens[:start + 1]))]
            continue
        if not precedence_group.get('binary', True):
            for i, token in reversed(list(enumerate(tokens))):
                if isinstance(token, Token) and token.type in precedence_group:
                    if len(tokens) == i + 1:
                        raise SyntaxError('expected a filter after ' + repr(token) + ', nothing found')
                    elif isinstance(tokens[i + 1], Token):
                        raise SyntaxError('expected a filter after ' + repr(token) + ', found ' + repr(tokens[i + 1]) + ' instead')
                    tokens[i:i + 2] = [raise_for_filter(precedence_group[token.type](attribute=tokens[i + 1]))]
            continue
        ltr = not precedence_group.get('rtl', False)
        if ltr:
            tokens.reverse()
        left_operand = None
        right_operand = None
        has_previous_operand = False
        has_next_operand = False
        for i, token in reversed(list(enumerate(tokens))):
            if isinstance(token, jqsh.filter.Filter) and has_next_operand:
                tokens[i:i + (3 if has_previous_operand else 2)] = [precedence_group[tokens[i + 1].type](left=left_operand, right=right_operand)]
                has_next_operand = False
            elif isinstance(token, Token) and token.type in precedence_group:
                left_operand, has_left_operand = (tokens[i - 1], True) if i > 0 and isinstance(tokens[i - 1], jqsh.filter.Filter) else (raise_for_filter(jqsh.filter.Filter()), False)
                right_operand, has_right_operand = (tokens[i + 1], True) if i + 1 < len(tokens) and isinstance(tokens[i + 1], jqsh.filter.Filter) else (raise_for_filter(jqsh.filter.Filter()), False)
                has_previous_operand = has_right_operand
                has_next_operand = has_left_operand
                if ltr:
                    left_operand, right_operand = right_operand, left_operand
                    has_left_operand, has_right_operand = has_right_operand, has_left_operand
                if not has_next_operand:
                    tokens[i:i + (2 if has_previous_operand else 1)] = [precedence_group[token.type](left=left_operand, right=right_operand)]
            else:
                has_next_operand = False
        if ltr:
            tokens.reverse()
    
    if len(tokens) == 1 and isinstance(tokens[0], jqsh.filter.Filter):
        return tokens[0] # finished parsing
    else:
        raise SyntaxError('Could not parse token list: ' + repr(tokens))

def parse_json(tokens, allow_extension_types=False):
    if isinstance(tokens, str):
        tokens = list(tokenize(tokens))
    if len(tokens) == 0 or len(tokens) == 1 and isinstance(tokens[0], Token) and tokens[0].type is TokenType.trailing_whitespace:
        raise Incomplete('JSON is empty')
    if isinstance(tokens[-1], Token) and tokens[-1].type is TokenType.trailing_whitespace:
        tokens.pop()
    ret_path = []
    key = None
    token_index = 0
    while token_index < len(tokens):
        token = tokens[token_index]
        if allow_extension_types and isinstance(token, jqsh.values.Value):
            ret_path = set_value_at_ret_path(ret_path, key, token)
            token_index += 1
        elif token.type is TokenType.name:
            if token.text == 'false':
                ret_path = set_value_at_ret_path(ret_path, key, jqsh.values.Boolean(False))
                token_index += 1
            elif token.text == 'null':
                ret_path = set_value_at_ret_path(ret_path, key, jqsh.values.Null())
                token_index += 1
            elif token.text == 'true':
                ret_path = set_value_at_ret_path(ret_path, key, jqsh.values.Boolean(True))
                token_index += 1
            else:
                raise SyntaxError('Illegal name token ' + repr(token.text) + ' at position ' + repr(token_index) + ' (expected false, null, or true)')
        elif token.type is TokenType.number:
            ret_path = set_value_at_ret_path(ret_path, key, jqsh.values.Number(token.text))
            token_index += 1
        elif token.type is TokenType.open_array:
            array = jqsh.values.Array(terminated=False)
            ret_path = set_value_at_ret_path(ret_path, key, array)
            token_index += 1
            if token_index >= len(tokens):
                raise Incomplete('Unclosed JSON array at position ' + str(token_index))
            if tokens[token_index].type is TokenType.close_array: # empty array parsed
                array.terminate()
                token_index += 1
            else:
                ret_path.append(array)
                continue
        elif token.type is TokenType.open_object:
            obj = jqsh.values.Object(terminated=False)
            ret_path = set_value_at_ret_path(ret_path, key, obj)
            token_index += 1
            if token_index >= len(tokens):
                raise Incomplete('Unclosed JSON object at position ' + str(token_index))
            token = tokens[token_index]
            if token.type is TokenType.close_object: # empty object parsed
                obj.terminate()
                token_index += 1
            elif token.type is TokenType.string:
                ret_path.append(obj)
                key = token.text
                token_index += 1
                if token_index >= len(tokens):
                    raise Incomplete('Unclosed JSON object at position ' + str(token_index))
                elif tokens[token_index].type is not TokenType.colon:
                    raise illegal_token_exception(token, position=token_index, expected={TokenType.colon})
                else:
                    token_index += 1
                    if token_index >= len(tokens):
                        raise Incomplete('Unclosed JSON object at position ' + str(token_index))
                    continue
            else:
                raise illegal_token_exception(token, position=token_index, expected={TokenType.close_object, TokenType.string})
        elif token.type is TokenType.string:
            ret_path = set_value_at_ret_path(ret_path, key, token.text)
            token_index += 1
        else:
            raise illegal_token_exception(token, position=token_index, expected={TokenType.name, TokenType.number, TokenType.open_array, TokenType.open_object, TokenType.string, TokenType.trailing_whitespace})
        keep_closing = True
        while keep_closing and len(ret_path):
            if isinstance(ret_path[-1], jqsh.values.Object): # we are in an object, get the next key or close it
                if token_index >= len(tokens):
                    raise Incomplete('Unclosed JSON object at position ' + str(token_index))
                token = tokens[token_index]
                if token.type is TokenType.close_object:
                    ret_path[-1].terminate()
                    if len(ret_path) == 1:
                        keep_closing = False
                    else:
                        ret_path.pop()
                    token_index += 1
                elif token.type is TokenType.comma:
                    token_index += 1
                    if token_index >= len(tokens):
                        raise Incomplete('Unclosed JSON object at position ' + str(token_index))
                    token = tokens[token_index]
                    if token.type is TokenType.string:
                        key = token.text
                        token_index += 1
                        if token_index >= len(tokens):
                            raise Incomplete('Unclosed JSON object at position ' + str(token_index))
                        elif tokens[token_index].type is not TokenType.colon:
                            raise illegal_token_exception(token, position=token_index, expected={TokenType.colon})
                        else:
                            token_index += 1
                            if token_index >= len(tokens):
                                raise Incomplete('Unclosed JSON object at position ' + str(token_index))
                            keep_closing = False
                    else:
                        raise illegal_token_exception(token, position=token_index, expected={TokenType.string})
                else:
                    raise illegal_token_exception(token, position=token_index, expected={TokenType.close_object, TokenType.comma})
            else: # we are in an array, check if it continues
                if token_index >= len(tokens):
                    raise Incomplete('Unclosed JSON array at position ' + str(token_index))
                token = tokens[token_index]
                if token.type is TokenType.close_array:
                    ret_path[-1].terminate()
                    if len(ret_path) == 1:
                        keep_closing = False
                    else:
                        ret_path.pop()
                    token_index += 1
                elif token.type is TokenType.comma:
                    token_index += 1
                    if token_index >= len(tokens):
                        raise Incomplete('Unclosed JSON array at position ' + str(token_index))
                    keep_closing = False
                else:
                    raise illegal_token_exception(token, position=token_index, expected={TokenType.close_array, TokenType.comma})
    if token_index < len(tokens):
        raise SyntaxError('Multiple top-level JSON values found')
    return ret_path[0]

def parse_json_values(tokens):
    if isinstance(tokens, str):
        tokens = list(tokenize(tokens))
    if len(tokens) and tokens[-1].type is TokenType.trailing_whitespace:
        tokens = tokens[:-1]
    prefix_length = 1
    last_exception = None
    while len(tokens):
        if prefix_length > len(tokens):
            raise last_exception
        try:
            yield parse_json(tokens[:prefix_length])
            tokens = tokens[prefix_length:]
            prefix_length = 1
        except Incomplete as e:
            last_exception = e
            prefix_length += 1

def set_value_at_ret_path(ret_path, key, value):
    if len(ret_path):
        if isinstance(ret_path[-1], jqsh.values.Object):
            ret_path[-1].push((key, value))
        else:
            ret_path[-1].push(value)
        return ret_path
    else:
        return [value]

def tokenize(jqsh_string):
    def shift(rest_string, line, column, amount=1):
        for _ in range(amount):
            removed_character = rest_string[0]
            rest_string = rest_string[1:]
            if removed_character == '\n':
                line += 1
                column = 0
            else:
                column += 1
        return rest_string, line, column
    
    rest_string = jqsh_string
    if not isinstance(rest_string, str):
        rest_string = rest_string.decode('utf-8')
    whitespace_prefix = ''
    if rest_string.startswith('\ufeff'):
        whitespace_prefix += rest_string[0]
        rest_string = rest_string[1:]
    line = 1
    column = 0
    parens_stack = []
    while len(parens_stack) and parens_stack[-1] < 0 or len(rest_string):
        if len(parens_stack) and parens_stack[-1] < 0 or rest_string[0] == '"':
            if len(parens_stack) and parens_stack[-1] < 0:
                token_type = TokenType.string_end_incomplete
                string_literal = ')'
                parens_stack.pop()
                string_start_line = line
                string_start_column = column - 1
            else:
                rest_string, line, column = shift(rest_string, line, column)
                token_type = TokenType.string_incomplete
                string_literal = '"'
                string_start_line = line
                string_start_column = column
            string_content = ''
            while len(rest_string):
                if rest_string[0] == '"':
                    token_type = {
                        TokenType.string_end_incomplete: TokenType.string_end,
                        TokenType.string_incomplete: TokenType.string
                    }[token_type]
                    string_literal += '"'
                    rest_string, line, column = shift(rest_string, line, column)
                    break
                elif rest_string[0] == '\\':
                    rest_string, line, column = shift(rest_string, line, column)
                    if rest_string[0] in escapes:
                        string_literal += '\\' + rest_string[0]
                        string_content += escapes[rest_string[0]]
                        rest_string, line, column = shift(rest_string, line, column)
                    elif rest_string[0] == 'u':
                        try:
                            escape_sequence = int(rest_string[1:5], 16)
                        except (IndexError, ValueError):
                            yield Token(token_type, token_string=whitespace_prefix + string_literal, text=string_content, line=string_start_line, column=string_start_column)
                            yield Token(TokenType.illegal, token_string=whitespace_prefix + rest_string, text=rest_string, line=line, column=column)
                            return
                        else:
                            string_literal += '\\' + rest_string[:5]
                            string_content += chr(escape_sequence) #TODO check for UTF-16 surrogate characters
                            rest_string, line, column = shift(rest_string, line, column, amount=5)
                    elif rest_string[0] == '(':
                        string_literal += '\\('
                        parens_stack.append(0)
                        token_type = {
                            TokenType.string_end_incomplete: TokenType.string_middle,
                            TokenType.string_incomplete: TokenType.string_start
                        }[token_type]
                        rest_string, line, column = shift(rest_string, line, column)
                        break
                    else:
                        yield Token(token_type, token_string=whitespace_prefix + string_literal, text=string_content, line=string_start_line, column=string_start_column)
                        yield Token(TokenType.illegal, token_string=whitespace_prefix + '\\' + rest_string, text='\\' + rest_string, line=line, column=column)
                        return
                else:
                    string_literal += rest_string[0]
                    string_content += rest_string[0]
                    rest_string, line, column = shift(rest_string, line, column)
            yield Token(token_type, token_string=whitespace_prefix + string_literal, text=string_content, line=string_start_line, column=string_start_column)
            whitespace_prefix = ''
        elif rest_string[0] in string.whitespace:
            whitespace_prefix += rest_string[0]
            rest_string, line, column = shift(rest_string, line, column)
        elif rest_string[0] == '#':
            comment_start_line = line
            comment_start_column = column
            rest_string, line, column = shift(rest_string, line, column)
            comment = ''
            while len(rest_string):
                if rest_string[0] == '\n':
                    break
                comment += rest_string[0]
                rest_string, line, column = shift(rest_string, line, column)
            yield Token(TokenType.comment, token_string=whitespace_prefix + '#' + comment, text=comment, line=comment_start_line, column=comment_start_column)
            whitespace_prefix = ''
        elif rest_string[0] in string.ascii_letters:
            name_start_line = line
            name_start_column = column
            name = ''
            while len(rest_string) and rest_string[0] in string.ascii_letters:
                name += rest_string[0]
                rest_string, line, column = shift(rest_string, line, column)
            yield Token(TokenType.name, token_string=whitespace_prefix + name, text=name, line=name_start_line, column=name_start_column)
            whitespace_prefix = ''
        elif rest_string[0] in string.digits:
            number_start_line = line
            number_start_column = column
            number = ''
            while len(rest_string) and rest_string[0] in string.digits:
                number += rest_string[0]
                rest_string, line, column = shift(rest_string, line, column)
            yield Token(TokenType.number, token_string=whitespace_prefix + number, text=number, line=number_start_line, column=number_start_column)
            whitespace_prefix = ''
        elif any(rest_string.startswith(symbol) for symbol in symbols):
            for symbol, token_type in sorted(symbols.items(), key=lambda pair: -len(pair[0])): # look at longer symbols first, so that a += is not mistakenly tokenized as a +
                if rest_string.startswith(symbol):
                    if len(parens_stack):
                        if token_type is TokenType.open_paren:
                            parens_stack[-1] += 1
                        elif token_type is TokenType.close_paren:
                            parens_stack[-1] -= 1
                    if len(parens_stack) == 0 or parens_stack[-1] >= 0:
                        yield Token(token_type, token_string=whitespace_prefix + rest_string[:len(symbol)], line=line, column=column)
                        whitespace_prefix = ''
                    rest_string, line, column = shift(rest_string, line, column, amount=len(symbol))
                    break
        else:
            yield Token(TokenType.illegal, token_string=whitespace_prefix + rest_string, text=rest_string, line=line, column=column)
            return
    if len(whitespace_prefix):
        yield Token(TokenType.trailing_whitespace, token_string=whitespace_prefix)
