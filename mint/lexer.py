# -*- coding: utf-8 -*-

from collections import deque
from StringIO import StringIO


class _TokensCollection(object):

    _tokens = (
        'indent',
        'unindent',
        'tag_block',
        'inline_tag',
        'text',
        'keyword',
        'macro_call',
        'macro_def',
        'eof',
    )

    def __getattr__(self, name):
        if name in self._tokens:
            value = intern(name)
            setattr(self, name, value)
            return value
        raise AttributeError(name)

    def __getitem__(self, name):
        try:
            value = getattr(self, name)
        except AttributeError:
            raise KeyError(name)
        else:
            return value


token = _TokensCollection()


class TokenValue(tuple):

    def __new__(cls, tok, value, line, pos):
        self = tuple.__new__(cls, (tok, value, line, pos))
        self.token = tok
        self.value = value
        self.line = line
        self.pos = pos
        return self


class Lexer(object):

    def __init__(self, source, chunk_size=4096, charset='utf-8'):
        if not isinstance(source, basestring):
            source = source.read()
        if not isinstance(source, unicode):
            source = unicode(source, charset)
        self.source = source
        self.size = len(source)
        self.lines = [('', 0)]
        self.line_no = 1
        self.line_pos = 0
        self.start = 0
        self.pos = 0
        self._tokens = deque()

    def next(self):
        'Moves current position marker, returns next char'
        if self.pos >= self.size:
            return ''
        char = self.source[self.pos]
        self.pos += 1
        if char == '\n':
            last_line, line_end_pos = self.lines[-1]
            line = self.source[line_end_pos:self.pos]
            self.lines.append((line, self.pos))
        return char

    def backup(self):
        'Undo `next` call'
        if self.pos > self.start:
            self.pos -= 1
            if self.pos > 0 and self.lines[-1][1] == self.pos:
                self.lines.pop()

    def emit(self, token):
        self._tokens.appendleft(TokenValue(token,
                                           self.source[self.start:self.pos],
                                           self.line_no,
                                           self.line_pos))
        self.ignore()

    def ignore(self):
        pos = self.start = self.pos
        self.line_no = len(self.lines)
        self.line_pos = pos - self.lines[-1][1]

    def __iter__(self):
        state = self.initial_state
        while state is not None:
            state = state(self)
            while self._tokens:
                yield self._tokens.pop()
