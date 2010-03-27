# -*- coding: utf-8 -*-

import re
import ast
import functools
import weakref
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


class GrandNode(object):

    def __init__(self):
        self.nodes = []

    def render(self, out):
        for node in self.nodes:
            node.render(out)


UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))


def escape(obj):
    text = str(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


class Node(object): pass


class Tag(Node):

    _selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']

    def __init__(self, tag_name, parent):
        parent.nodes.append(self)
        self.tag_name = tag_name
        self.nodes = []
        self.attrs = []
        self.closed = tag_name in self._selfclosed

    def set_attr(self, name, value):
        self.attrs.append((name, value))

    def render(self, out, indent=0):
        out.write('    '*indent)
        out.write('<%s' % self.tag_name)
        for item in self.attrs:
            out.write(' %s="%s"' % item )
        if self.closed:
            out.write('/>\n')
            return
        else:
            out.write('>\n')
        for node in self.nodes:
            node.render(out, indent=indent+1)
        out.write('    '*indent)
        out.write('</%s>\n' % self.tag_name)


class TextNode(Node):

    def __init__(self, text, parent):
        parent.nodes.append(self)
        self.text = text

    def render(self, out, indent=0):
        out.write('%s\n' % self.text)

# States
class State(object):

    # Indicates that this state need stored data
    # to process. After store is cleared

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
        (lexer.TOKEN_WORD , 'MayBeTagState'),
        ((lexer.TOKEN_WHITESPACE, lexer.TOKEN_NEWLINE), ),
        (lexer.TOKEN_BRACE_OPEN, 'MayBeExpressionState'),
        (AnyToken(), 'TextState'),
    ]


class MayBeTagState(State):
    variantes = [
        (lexer.TOKEN_COLON, 'TagState'),
        ((lexer.TOKEN_WHITESPACE, lexer.TOKEN_NEWLINE), 'TextState'),
    ]


class TagState(State):
    variantes = [
        (lexer.TOKEN_WHITESPACE, 'InsideTagState'),
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_WORD, 'MayBeTagState'),
    ]


class InsideTagState(State):
    variantes = [
        (lexer.TOKEN_WHITESPACE, ),
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_WORD, 'MayBeTagState'),
        (lexer.TOKEN_BRACE_OPEN, 'MayBeExpressionState'),
        (AnyToken(), 'TextState'),
    ]


class TextState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_BRACE_OPEN, 'MayBeExpressionState'),
        (AnyToken(exclude=[lexer.TOKEN_BRACE_OPEN]),),
    ]


class MayBeExpressionState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (lexer.TOKEN_BRACE_OPEN, 'ExpressionState'),
        (AnyToken(exclude=[lexer.TOKEN_NEWLINE]), 'TextState'),
    ]


class ExpressionState(State):
    variantes = [
        (lexer.TOKEN_BRACE_CLOSE, 'MayBeExpressionEndState'),
        (AnyToken(exclude=[lexer.TOKEN_BRACE_CLOSE]),),
    ]


class MayBeExpressionEndState(State):
    variantes = [
        (lexer.TOKEN_BRACE_CLOSE, 'ExpressionEndState'),
        (AnyToken(exclude=[lexer.TOKEN_BRACE_CLOSE]), 'ExpressionState'),
    ]

class ExpressionEndState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
        (AnyToken(), 'TextState'),
    ]


class Parser(object):

    # Variable's names for generated code
    NODE_NAME = '__MINT_NODE__'
    GRAND_NODE = '__MINT_GRAND_NODE'
    TAG_NODE_CLASS = '__MINT_TAG_NODE'
    TEXT_NODE_CLASS = '__MINT_TEXT_NODE'
    ESCAPE_HELLPER = '__MINT_TEXT_ESCAPE'

    NAMESPACE = {
        GRAND_NODE:GrandNode,
        TAG_NODE_CLASS:Tag,
        TEXT_NODE_CLASS:TextNode,
        ESCAPE_HELLPER:escape,
        '__builtins__':__builtins__,
    }

    def __init__(self, slots=None, indent=4):
        self.indent = indent
        self.__id = 0
        # parent nodes stack
        self.stack = []
        # final module, which stores all prepaired nodes
        self.module = ast.Module(body=[
            ast.Assign(targets=[ast.Name(id=self.NODE_NAME, ctx=Store())],
                       value=ast.Call(func=ast.Name(id=self.GRAND_NODE, ctx=Load()),
                                      args=[], keywords=[], lineno=1, col_offset=0))
        ])
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
        return len(self.stack)

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
            if token is lexer.TOKEN_EOF:
                break
            state_data.append((token, value, lineno, pos))
            state = last_state.accept(token)
            # State changed, we need to process data
            if state is not last_state:
                #print last_state.__name__, token, state.__name__#, state_data
                state_data = self.process(last_state, state, state_data)
                last_state = state

    def process(self, last_state, state, data):
        # text at the end of line
        if last_state is TextState and state is InitialState:
            getattr(self, 'handle_'+last_state.__name__)(data)
            return []
        if last_state is MayBeExpressionState and state is ExpressionState:
            self.handle_TextState(data[:-2])
            return data[-2:]
        if state in (TagState, ExpressionEndState):
            getattr(self, 'handle_'+state.__name__)(data)
            return []
        return data

    def handle_TagState(self, data):
        print 'TagState', ''.join((v[1] for v in data ))

    def handle_TextState(self, data):
        print 'TextState', ''.join((v[1] for v in data ))

    def handle_ExpressionEndState(self, data):
        print 'ExpressionEndState', ''.join((v[1] for v in data ))


if __name__ == '__main__':
    import sys
    file_name = sys.argv[1]
    parser = Parser()
    parser.parse(open(file_name, 'r'))
