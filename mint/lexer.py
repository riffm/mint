# -*- coding: utf-8 -*-

import mmap
import re


class TokenWrapper(object):

    def __init__(self, token, value=None, regex_str=None):
        assert value or regex_str, 'Provide token text value or regex'
        self.token = intern(token)
        if regex_str is not None:
            self.regex = re.compile(regex_str)
        else:
            self.regex = re.compile(r'%s' % re.escape(value))

    def __str__(self):
        return self.token

    __repr__ = __str__


class EOF(object):
    def __str__(self):
        return 'eof'
    __repr__ = __str__


# Tokens
TOKEN_WORD = TokenWrapper('word', regex_str=r'[a-zA-Z_]+')
TOKEN_DOT = TokenWrapper('dot', value='.')
TOKEN_BRACKET_OPEN = TokenWrapper('bracket_open', value='(')
TOKEN_BRACKET_CLOSE = TokenWrapper('bracket_close', value=')')
TOKEN_PUNCTUATION = TokenWrapper('punctuation', regex_str=r'(,|;)')
TOKEN_COLON = TokenWrapper('colon', value=':')
#TOKEN_UNDERSCORE = TokenWrapper('underscore', value='_')
TOKEN_WHITESPACE = TokenWrapper('whitespace', regex_str=r'\s{1}')
TOKEN_QUOTE = TokenWrapper('quote', value="'")
TOKEN_DOUBLE_QUOTE = TokenWrapper('double_quote', value='"')
TOKEN_OPERATOR = TokenWrapper('operator', 
                              regex_str=r'(%s)' % '|'.join(
                                  [re.escape(v) for v in ('+', '-', '*', '**', '^', 
                                                          '=', '==', '<=', '>=' , '<',
                                                          '>', '|')]
                              ))
TOKEN_NEWLINE = TokenWrapper('newline', regex_str=r'\r\n|\r|\n')
TOKEN_BACKSLASH = TokenWrapper('backslash', value='\\')
TOKEN_EXPR_START = TokenWrapper('expr_start', value='{{')
TOKEN_EXPR_END = TokenWrapper('expr_end', value='}}')
TOKEN_EOF = EOF()


tokens = [v for v in locals().values() if isinstance(v, TokenWrapper)]

class TokensStream(object):

    def __init__(self, fp):
        self.fp = fp
        self.current = None

    def tokenize(self):
        map = mmap.mmap(self.fp.fileno(), 0, access=mmap.ACCESS_READ)
        lineno = 0
        pos = 0
        while 1:
            lineno += 1

            # end of file
            if map.tell() == map.size():
                yield TOKEN_EOF
                break

            # now we tokinoxe line by line
            line = map.readline()
            while line:
                line_len = len(line)
                for token in tokens:
                    if line:
                        m = token.regex.match(line)
                        if m:
                            offset, value = m.end(), m.group()
                            line = line[offset:]
                            yield token, value, lineno, pos
                            pos += offset

                # we do not get right token for the rest of the line
                if line_len == len(line):
                    raise ValueError(line)

        # all work is done
        map.close()

if __name__ == '__main__':
    import sys
    file_name = sys.argv[1]
    stream = TokensStream(open(file_name, 'r'))
    for t in stream.tokenize():
        print t
