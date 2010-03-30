# -*- coding: utf-8 -*-

import re
import ast
import StringIO
import htmlentitydefs
import lexer
from ast import Load, Store, Param


#TODO
# - Text escaping
# - "IF-ELIF-ELSE" statement
# - "IF-ELIF-ELSE" templates error handling
# - "FOR" statement
# - blocks (inheritance)
# - python variables (i.e. !a = 'hello')
# - '%' chars escaping in strings
# - '\' escaping of ':' '!' '@'

class TemplateError(Exception): pass
class WrongToken(Exception): pass


UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))


def escape(obj):
    text = str(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


_selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']


# States
class State(object):
    # shows state to deligate to and stop_token
    deligate = []

    @classmethod
    def accept(cls, token):
        for item in cls.variantes:
            if len(item) == 2:
                variante, new_state = item
                new_state = globals().get(new_state)
            else:
                variante, new_state = item[0], cls
            if isinstance(variante, (list, tuple)):
                if token in variante:
                    return new_state
            elif variante is token:
                return new_state
        msg = '"%s" got unexpected token "%s"' % (cls.__name__, token)
        raise WrongToken(msg)


#states = [v for v in locals().values() if isinstance(v, State)]


def AnyToken(exclude=None):
    if exclude is None:
        return lexer.tokens
    else:
        return [t for t in lexer.tokens if t not in exclude]


class InitialState(State):
    variantes = [
        (lexer.TOKEN_TAG_START , 'TagState'),
        ((lexer.TOKEN_WHITESPACE, lexer.TOKEN_NEWLINE), ),
        (lexer.TOKEN_EXPRESSION_START, 'ExpressionState'),
        (lexer.TOKEN_BACKSLASH, 'EscapedTextLineState'),
        (lexer.tokens, 'TextState'),
    ]

class EscapedTextLineState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.tokens, ),
    ]


class TagState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_WORD, 'TagNameState'),
    ]

class TagNameState(State):
    variantes = [
        (lexer.TOKEN_DOT, 'TagAttrState'),
        (lexer.TOKEN_WHITESPACE, 'EndTagState'),
        (lexer.TOKEN_NEWLINE, 'InitialState'),
    ]


class TagAttrState(State):
    variantes = [
        (lexer.TOKEN_WORD, 'TagAttrNameState'),
    ]


class TagAttrNameState(State):
    variantes = [
        ((lexer.TOKEN_WORD, lexer.TOKEN_COLON, lexer.TOKEN_MINUS), ),
        (lexer.TOKEN_PARENTHESES_OPEN, 'TagAttrTextState'),
    ]


class TagAttrTextState(State):
    variantes = [
        (lexer.TOKEN_PARENTHESES_CLOSE, 'EndTagAttrState'),
        (lexer.TOKEN_EXPRESSION_START, 'TagAttrExpressionState'),
        (lexer.tokens,),
    ]


class TagAttrExpressionState(State):
    variantes = [
        (lexer.TOKEN_PARENTHESES_CLOSE, 'EndTagAttrState'),
        (lexer.TOKEN_EXPRESSION_END, 'TagAttrTextState'),
        (lexer.tokens,),
    ]


class EndTagAttrState(State):
    variantes = [
        (lexer.TOKEN_DOT, 'TagAttrState'),
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_WHITESPACE, 'TextState'),
    ]


class EndTagState(State):
    variantes = [
        (lexer.TOKEN_TAG_START, 'TagState'),
        (lexer.TOKEN_EXPRESSION_START, 'ExpressionState'),
        (lexer.tokens, 'TextState'),
    ]


class TextState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_EXPRESSION_START, 'ExpressionState'),
        (lexer.tokens,),
    ]


class ExpressionState(State):
    variantes = [
        (lexer.TOKEN_EXPRESSION_END, 'TextState'),
        (lexer.tokens,),
    ]


class Parser(object):

    # Variable's names for generated code
    ESCAPE_HELLPER = '__MINT_TEXT_ESCAPE'
    OUTPUT_NAME = '__MINT__OUTPUT__'
    OUTPUT_WRITER = '__MINT__OUTPUT__WRITER__'

    NAMESPACE = {
        ESCAPE_HELLPER:escape,
        'StringIO':StringIO.StringIO,
        '__builtins__':__builtins__,
    }

    def __init__(self, slots=None, indent=4):
        self.indent_level = indent
        self.indent = u' ' *indent
        self.__id = 0
        # parent nodes stack
        self.stack = []
        self.tags_stack = []
        self.base = None
        # final module, which stores all prepaired nodes
        self.module = ast.Module(body=[
            ast.Assign(targets=[ast.Name(id=self.OUTPUT_NAME, ctx=Store(), lineno=1, col_offset=0)], 
                       value=ast.Call(func=ast.Name(id='StringIO', ctx=Load(), lineno=1, col_offset=0),
                                  args=[], keywords=[], starargs=None, kwargs=None, lineno=1, col_offset=0), lineno=1, col_offset=0),
            ast.Assign(targets=[ast.Name(id=self.OUTPUT_WRITER, ctx=Store(), lineno=1, col_offset=0)], 
                       value=ast.Attribute(value=ast.Name(id=self.OUTPUT_NAME, ctx=Load(), lineno=1, col_offset=0),
                                           attr='write', ctx=Load(), lineno=1, col_offset=0),
                                 lineno=1, col_offset=0)], lineno=1, col_offset=0)
        # current scope
        self.ctx = self.module.body
        # indicates if we are in text block
        self._text_block = []
        # if elif else
        self._if_blocks = []
        self.slots = slots if slots else {}
        self._slot_level = None
        self.store = {}
        self.ctx_type = 'normal'

    def push_stack(self, ctx):
        '''
        ctx - scope (list actualy)
        '''
        self.stack.append(self.ctx)
        self.ctx = ctx

    def pop_stack(self):
        self.ctx = self.stack.pop()

    @property
    def level(self):
        return len(self.tags_stack)
        #return len(self.stack)

    def switch_ctx(self, to='normal'):
        self.ctx_type = to
        if to == 'normal':
            self.ctx, self.stack = self.store[to]
        elif to == 'slot':
            self.store['normal'] = (self.ctx, self.stack)
            self.ctx = None
            self.stack = []
        else:
            raise ValueError('Unknown context "%s"' % to)

    def _id(self):
        self.__id += 1
        return self.__id

    @property
    def tree(self):
        return self.module

    def parse(self, input):
        '''
        input - file like object
        '''
        last_state = InitialState
        state_data = []
        stream = lexer.TokensStream(input)
        for token, value, lineno, pos in stream.tokenize():
            self.lineno = lineno
            self.col_offset = pos
            if token is lexer.TOKEN_EOF:
                break
            state_data.append((token, value))
            state = last_state.accept(token)
            # if state changed, we need to process data
            if state is not last_state:
                print last_state.__name__, token, state.__name__#, state_data
                state_data = self.process(last_state, state, state_data)
                last_state = state

        # if we have data in tags_stack, we need to write it
        total_last = len(self.tags_stack)
        for i in range(total_last):
            self._write(self.indent*(total_last - 1 - i))
            last_tag_end = self.tags_stack.pop()
            self._write(last_tag_end)

    def _get_level(self, line):
        level = len(line)/self.indent_level
        if self.ctx_type == 'slot':
            return level - self._slot_level
        return level

    def _write(self, data, value_type='text'):
        if value_type == 'text':
            value = ast.Str(s=data, lineno=self.lineno, col_offset=self.col_offset)
        elif value_type == 'expr':
            value = ast.parse(data).body[0].value
        expr = ast.Expr(value=ast.Call(func=ast.Name(id=self.OUTPUT_WRITER, ctx=Load(), 
                                                     lineno=self.lineno, col_offset=self.col_offset),
                                       args=[value],
                                       keywords=[], starargs=None, kwargs=None,
                                       lineno=self.lineno, col_offset=self.col_offset),
                        lineno=self.lineno, col_offset=self.col_offset)
        self.ctx.append(expr)

    def process(self, last_state, state, data):
        # set level and ctx
        if last_state is InitialState and data[0][0] is lexer.TOKEN_WHITESPACE:
            self.set_level(data[0][1])
            data = data[1:]
        # \ text text
        if last_state is EscapedTextLineState and state is InitialState:
            # first token - TOKEN_BACKSLASH, last - TOKEN_NEWLINE
            self.add_text(data[1:])
            return []
        # text at the end of line
        if last_state is TextState and state is InitialState:
            self.add_text(data)
            return []
        # text text {{
        if last_state is TextState and state is ExpressionState:
            self.add_text(data[:-1])
            return data[-1:]
        if last_state is ExpressionState and state is not ExpressionState:
            self.add_expression(data[1:-1])
            return []
        # @div\n
        if state is EndTagState:
            self.add_tag(data[1:], attrs=False)
            return []
        if state is InitialState and last_state is TagNameState:
            self.add_tag(data[1:], attrs=False)
            self._write(u'\n')
            return []
        # @div.
        if last_state is TagNameState and state is TagAttrState:
            self.add_tag(data[1:-1], attrs=True)
            return []
        # @div.class(
        if last_state is TagAttrNameState and state is TagAttrTextState:
            self.add_attr_name(data[0][1])
            return []
        # @div.class( text)
        if last_state is TagAttrTextState and state is EndTagAttrState:
            self.add_text(data[:-1])
            # close attr
            self._write(u'"')
            return []
        # @div.class( {{ expr }})
        if last_state is TagAttrExpressionState and state is EndTagAttrState:
            self.add_expression(data[1:-1])
            self._write(u'"')
            return []
        # @div.class( text {{ expr }})
        if last_state is TagAttrTextState and state is TagAttrExpressionState:
            self.add_text(data[:-1])
            return []
        # @div.class({{ expr }} text )
        if last_state is TagAttrExpressionState and state is TagAttrTextState:
            self.add_expression(data[1:-1])
            return []
        # @div.attr(value)\n
        if last_state is EndTagAttrState and state is not TagAttrState:
            self._write(u'>')
            return []
        if last_state is EndTagAttrState and state is InitialState:
            self._write(u'\n')
            return []
        return data

    def add_tag(self, data, attrs=False):
        print 'add tag:', ''.join((v[1] for v in data ))
        t, val = data[0]
        self.tags_stack.append(u'</%s>' % val)
        if attrs:
            self._write(u'<%s' % val)
        else:
            self._write(u'<%s>' % val)

    def add_text(self, data):
        print 'add text:', ''.join((v[1] for v in data ))
        self._write(u''.join((v[1] for v in data )))

    def add_expression(self, data):
        print 'add expression:', ''.join((v[1] for v in data ))
        self._write(u''.join((v[1] for v in data )).lstrip(), value_type='expr')

    def add_attr_name(self, data):
        print 'add attr name:', data
        self._write(u' %s="' % data)

    def set_level(self, data):
        level = self._get_level(data)
        self._write(data)
        #print 'set indention:', level, self.level
        if level <= self.level:
            total_pops = level - self.level
            for y in range(self.level - level):
                last_tag_end = self.tags_stack.pop()
                # indention
                #self._write(self.indent * (total_pops - 1 - y + level))
                self._write(last_tag_end)


if __name__ == '__main__':
    import sys
    file_name = sys.argv[1]
    parser = Parser()
    parser.parse(open(file_name, 'r'))
