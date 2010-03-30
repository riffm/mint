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

TAG_CHAR = '@'
STMT_CHAR = '#'
COMMENT_CHAR = '//'

# Tokens
TOKEN_TAG_START = TokenWrapper('tag_start', value=TAG_CHAR)
TOKEN_STATEMENT_IF = TokenWrapper('statement_if', value='%sif ' % STMT_CHAR)
TOKEN_STATEMENT_ELIF = TokenWrapper('statement_elif', value='%selif ' % STMT_CHAR)
TOKEN_STATEMENT_ELSE = TokenWrapper('statement_else', value='%selse:' % STMT_CHAR)
TOKEN_STATEMENT_FOR = TokenWrapper('statement_for', value='%sfor ' % STMT_CHAR)
TOKEN_COMMENT = TokenWrapper('comment', value=COMMENT_CHAR)
TOKEN_BACKSLASH = TokenWrapper('backslash', value='\\')
TOKEN_WORD = TokenWrapper('word', regex_str=r'[a-zA-Z_]+')
TOKEN_DIGIT = TokenWrapper('digit', regex_str=r'[0-9]+')
TOKEN_DOT = TokenWrapper('dot', value='.')
TOKEN_PARENTHESES_OPEN = TokenWrapper('parentheses_open', value='(')
TOKEN_PARENTHESES_CLOSE = TokenWrapper('parentheses_close', value=')')
TOKEN_SQUARE_BRACKETS_OPEN = TokenWrapper('square_bracket_open', value='[')
TOKEN_SQUARE_BRACKETS_CLOSE = TokenWrapper('square_bracket_close', value=']')
TOKEN_EXPRESSION_START = TokenWrapper('expression_start', value='{{')
TOKEN_EXPRESSION_END = TokenWrapper('expression_end', value='}}')
TOKEN_PUNCTUATION = TokenWrapper('punctuation', regex_str=r'(,|;)')
TOKEN_COLON = TokenWrapper('colon', value=':')
TOKEN_WHITESPACE = TokenWrapper('whitespace', regex_str=r'\s+')
TOKEN_QUOTE = TokenWrapper('quote', value="'")
TOKEN_DOUBLE_QUOTE = TokenWrapper('double_quote', value='"')
TOKEN_MINUS = TokenWrapper('minus', value='-')
TOKEN_OPERATOR = TokenWrapper('operator',
                              regex_str=r'(%s)' % '|'.join(
                                  [re.escape(v) for v in ('+', '*', '**', '^', 
                                                          '=', '==', '<=', '>=' , '<',
                                                          '>', '|')]
                              ))
TOKEN_NEWLINE = TokenWrapper('newline', regex_str=r'(\r\n|\r|\n)')
TOKEN_EOF = EOF()


tokens = [v for v in locals().values() if isinstance(v, TokenWrapper)]

re_comment = re.compile(r'\s*//')

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
                yield TOKEN_EOF, 'EOF', lineno, 0
                break

            # now we tokinoxe line by line
            line = map.readline()
            line = line.replace('\n', '')
            is_comment = re_comment.match(line)
            if is_comment:
                continue
            while line:
                line_len = len(line)
                for token in tokens:
                    if line:
                        m = token.regex.match(line)
                        if m:
                            if token is TOKEN_COMMENT:
                                line=''
                                continue
                            offset, value = m.end(), m.group()
                            line = line[offset:]
                            yield token, value, lineno, pos
                            pos += offset

                # we did not get right token for the rest of the line
                if line_len == len(line):
                    raise ValueError(line)

            yield TOKEN_NEWLINE, '\n', lineno, pos

        # all work is done
        map.close()


if __name__ == '__main__':
    import sys
    file_name = sys.argv[1]
    stream = TokensStream(open(file_name, 'r'))
    for t in stream.tokenize():
        print t
