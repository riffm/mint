# -*- coding: utf-8 -*-

from collections import deque


class SyntaxError(SyntaxError):
    pass


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

    _tag_start = '@'
    _tag_body_open = '['
    _tag_body_close = ']'

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
        self.indent_level = 0
        self.indent = ''
        self.last_char = ''

    def next(self):
        'Moves current position marker, returns next char'
        # pos always points to next char
        pos = self.pos
        assert pos <= self.size
        if self.last_char == '\n':
            line_end_pos = self.lines[-1][1]
            line = self.source[line_end_pos:pos]
            self.lines.append((line, pos))
        if pos == self.size:
            char = ''
        else:
            self.last_char = char = self.source[pos]
        self.pos += 1
        return char

    def backup(self):
        'Undo `next` call'
        assert self.pos > self.start
        self.pos -= 1
        if self.pos > 0:
            self.last_char = self.source[self.pos - 1]
        else:
            self.last_char = ''
        if len(self.lines) > 1 and self.lines[-1][1] == self.pos:
            self.lines.pop()

    def emit(self, tok, value=None):
        if tok is not token.eof and value is None:
            assert self.pos > self.start
        self._tokens.appendleft(
                TokenValue(tok,
                           value or self.source[self.start:self.pos],
                           self.line_no,
                           self.line_pos))
        self.ignore()

    def ignore(self):
        self.start = self.pos
        self.line_no = len(self.lines)
        if self.last_char == '\n':
            self.line_no += 1
            self.line_pos = 0
        else:
            self.line_pos = self.pos - self.lines[-1][1]

    def peek(self):
        char = self.next()
        self.backup()
        return char

    def accept(self, chars):
        if self.next() in chars:
            return True
        self.backup()
        return False

    def accept_run(self, chars):
        char = self.next()
        while char != '' and char in chars:
            char = self.next()
        self.backup()

    def __iter__(self):
        state = self.initial_state
        while state is not None:
            state = state()
            while self._tokens:
                yield self._tokens.pop()

    def error(self, msg):
        raise SyntaxError(msg)

    def indent_state(self):
        char = self.peek()
        if char == ' ':
            self.accept_run(' ')
            value = self.source[self.start:self.pos]
            if self.indent_level == 0:
                self.indent_level = 1
                self.indent = value
                self.emit(token.indent, 1)
            else:
                if len(value) % len(self.indent):
                    self.error('wrong indention level')
                delta = len(value)/len(self.indent) - self.indent_level
                if delta > 0:
                    if delta > 1:
                        self.error('wrong indention level')
                    self.emit(token.indent, delta)
                elif delta < 0:
                    self.emit(token.unindent, abs(delta))
                else:
                    self.ignore()
                self.indent_level += delta
        elif self.indent_level:
            self.emit(token.unindent, self.indent_level)
            self.indent_level = 0
        if char == '':
            self.emit(token.eof)
            return None
        return self.line_state

    initial_state = indent_state

    def line_state(self):
        char = self.next()
        if char == '\n':
            self.emit(token.text)
            return self.indent_state
        if char == self._tag_start:
            self.ignore()
            return self.tag_state
        self.backup()
        return self.text_state
