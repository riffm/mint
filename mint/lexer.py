# -*- coding: utf-8 -*-

import os
import re
import mmap
from StringIO import StringIO
from collections import deque


class TokenWrapper(object):

    def __init__(self, token, value=None, regex_str=None):
        assert value or regex_str, 'Provide token text value or regex'
        self.token = intern(token)
        if regex_str is not None:
            self.regex = re.compile(regex_str, re.U)
        else:
            self.regex = re.compile(r'%s' % re.escape(value), re.U)

    def __str__(self):
        return self.token

    __repr__ = __str__


class TextToken(object):
    'Special token for text'
    def __str__(self):
        return 'text'
    __repr__ = __str__


class TokenIndent(object):
    def __str__(self):
        return 'indent'
    __repr__ = __str__


class TokenUnindent(object):
    def __str__(self):
        return 'unindent'
    __repr__ = __str__


class EOF(object):
    'Special token'
    def __str__(self):
        return 'eof'
    __repr__ = __str__


# constants
TAG_CHAR = '@'
STMT_CHAR = '#'
COMMENT_CHAR = '--'

# Tokens
TOKEN_TAG_START = TokenWrapper('tag_start', value=TAG_CHAR)
TOKEN_TAG_ATTR_SET = TokenWrapper('tag_attr_set', value='%s.' % TAG_CHAR)
TOKEN_TAG_ATTR_APPEND = TokenWrapper('tag_attr_append', value='%s+' % TAG_CHAR)
TOKEN_BASE_TEMPLATE = TokenWrapper('base_template', value='%sbase: ' % STMT_CHAR)
TOKEN_STATEMENT_IF = TokenWrapper('statement_if', value='%sif ' % STMT_CHAR)
TOKEN_STATEMENT_ELIF = TokenWrapper('statement_elif', regex_str=r'(%selif |%selse if )' % (
    re.escape(STMT_CHAR), re.escape(STMT_CHAR)))
TOKEN_STATEMENT_ELSE = TokenWrapper('statement_else', value='%selse:' % STMT_CHAR)
TOKEN_STATEMENT_FOR = TokenWrapper('statement_for', value='%sfor ' % STMT_CHAR)
TOKEN_SLOT_DEF = TokenWrapper('slot_def', regex_str=r'(%sdef |%sfunction )' % (re.escape(STMT_CHAR),
                                                                               re.escape(STMT_CHAR)))
TOKEN_STMT_CHAR = TokenWrapper('hash', value=STMT_CHAR)
TOKEN_COMMENT = TokenWrapper('comment', value=COMMENT_CHAR)
TOKEN_BACKSLASH = TokenWrapper('backslash', value='\\')
TOKEN_DOT = TokenWrapper('dot', value='.')
TOKEN_PLUS = TokenWrapper('plus', value='+')
TOKEN_MINUS = TokenWrapper('minus', value='-')
TOKEN_COLON = TokenWrapper('colon', value=':')
TOKEN_PARENTHESES_OPEN = TokenWrapper('parentheses_open', value='(')
TOKEN_PARENTHESES_CLOSE = TokenWrapper('parentheses_close', value=')')
TOKEN_EXPRESSION_START = TokenWrapper('expression_start', value='{{')
TOKEN_EXPRESSION_END = TokenWrapper('expression_end', value='}}')
TOKEN_WHITESPACE = TokenWrapper('whitespace', regex_str=r'\s+')
TOKEN_NEWLINE = TokenWrapper('newline', regex_str=r'(\r\n|\r|\n)')
TOKEN_EOF = EOF()
TOKEN_TEXT = TextToken()
TOKEN_INDENT = TokenIndent()
TOKEN_UNINDENT = TokenUnindent()


tokens = (
    TOKEN_TAG_ATTR_SET,
    TOKEN_TAG_ATTR_APPEND,
    TOKEN_TAG_START,
    TOKEN_BASE_TEMPLATE,
    TOKEN_STATEMENT_IF,
    TOKEN_STATEMENT_ELIF,
    TOKEN_STATEMENT_ELSE,
    TOKEN_STATEMENT_FOR,
    TOKEN_SLOT_DEF,
    TOKEN_STMT_CHAR,
    TOKEN_COMMENT,
    TOKEN_BACKSLASH,
    TOKEN_DOT,
    TOKEN_PLUS,
    TOKEN_MINUS,
    TOKEN_PARENTHESES_OPEN,
    TOKEN_PARENTHESES_CLOSE,
    TOKEN_EXPRESSION_START,
    TOKEN_EXPRESSION_END,
    TOKEN_COLON,
    TOKEN_WHITESPACE,
    TOKEN_NEWLINE,
)

all_tokens = list(tokens) + [TOKEN_EOF, TOKEN_TEXT, TOKEN_INDENT, TOKEN_UNINDENT]
all_except = lambda *t: filter(lambda x: x not in t, all_tokens)
re_comment = re.compile(r'\s*//')


def base_tokenizer(fp):
    'Tokenizer. Generates tokens stream from text'
    if isinstance(fp, StringIO):
        template_file = fp
        size = template_file.len
    else:
        #empty file check
        if os.fstat(fp.fileno()).st_size == 0:
            yield TOKEN_EOF, 'EOF', 0, 0
            return
        template_file = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
        size = template_file.size()
    lineno = 0
    while 1:
        lineno += 1
        pos = 1

        # end of file
        if template_file.tell() == size:
            yield TOKEN_EOF, 'EOF', lineno, 0
            break

        # now we tokinize line by line
        line = template_file.readline().decode('utf-8')
        line = line.replace('\r\n', '')
        line = line.replace('\n', '')
        # ignoring non XML comments
        if re_comment.match(line):
            continue

        last_text = deque()
        while line:
            line_len = len(line)
            for token in tokens:
                m = token.regex.match(line)
                if m:
                    if last_text:
                        yield TOKEN_TEXT, ''.join(last_text), lineno, pos
                        pos += len(last_text)
                        last_text.clear()
                    offset, value = m.end(), m.group()
                    line = line[offset:]
                    yield token, value, lineno, pos
                    pos += offset
                    break

            # we did not get right in tokens list, so next char is text
            if line_len == len(line):
                last_text.append(line[0])
                line = line[1:]

        if last_text:
            yield TOKEN_TEXT, ''.join(last_text), lineno, pos
            pos += len(last_text)
            last_text.clear()
        yield TOKEN_NEWLINE, '\n', lineno, pos

    # all work is done
    template_file.close()


def indent_tokenizer(tokens_stream):
    current_indent = 0
    indent = 0
    for tok in tokens_stream:
        token, value, lineno, pos = tok
        # backslashed line transfer
        if token is TOKEN_BACKSLASH:
            next_tok = tokens_stream.next()
            next_token, next_value, next_lineno, next_pos = next_tok
            if next_token is TOKEN_NEWLINE:
                next_tok = tokens_stream.next()
                while next_tok[0] in (TOKEN_WHITESPACE, TOKEN_NEWLINE):
                    next_tok = tokens_stream.next()
                # first not newline or whitespace token
                yield next_tok
                continue
            yield tok
            tok = next_tok
            token, value, lineno, pos = next_tok
        # indenting and unindenting
        if token is TOKEN_NEWLINE or (token is TOKEN_WHITESPACE and (lineno, pos) == (1, 1)):
            if token is TOKEN_NEWLINE:
                yield tok
                next_tok = tokens_stream.next()
                while next_tok[0] is TOKEN_NEWLINE:
                    next_tok = tokens_stream.next()
            else:
                next_tok = tok
            next_token, next_value, next_lineno, next_pos = next_tok
            if next_token is TOKEN_WHITESPACE:
                ws_count = len(next_value)
                if indent == 0:
                    indent = ws_count
                if ws_count >= indent:
                    times = ws_count/indent
                    rest = ws_count % indent
                    range_ = times - current_indent
                    if range_ > 0:
                        # indenting
                        tmp_curr_indent = current_indent
                        for i in range(range_):
                            yield TOKEN_INDENT, ' '*indent, next_lineno, (i+tmp_curr_indent)*indent+1
                            current_indent += 1
                    elif range_ < 0:
                        # unindenting
                        for i in range(abs(range_)):
                            yield TOKEN_UNINDENT, ' '*indent, next_lineno, next_pos
                            current_indent -= 1
                    if rest:
                        yield TOKEN_WHITESPACE, ' '*rest, next_lineno, times*indent+1
                    continue
            # next token is the whitespace lighter than indent or any other
            # token, so unindenting to zero level
            for i in range(current_indent):
                yield TOKEN_UNINDENT, ' '*indent, lineno, pos
            current_indent = 0
            yield next_tok
            # we do not yielding newline tokens
            continue
        yield tok


def tokenizer(fileobj):
    return indent_tokenizer(base_tokenizer(fileobj))
