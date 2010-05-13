# -*- coding: utf-8 -*-

import re
import ast
import StringIO
import lexer
from nodes import *
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
        (lexer.TOKEN_STATEMENT_FOR, 'StatementForState'),
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


class StatementForState(State):
    variantes = [
        (lexer.TOKEN_NEWLINE, 'InitialState'),
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
        self.base = None
        # final module, which stores all prepaired nodes
        # current scope
        self.ctx = TagNode('') # root tag node
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
        #print 'push: ', ctx
        self.stack.append(self.ctx)
        self.ctx = ctx

    def pop_stack(self):
        #print 'pop:  ', self.ctx
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
        module_tree = ast.Module(body=[
            ast.Assign(targets=[ast.Name(id=self.OUTPUT_NAME, ctx=Store(), lineno=1, col_offset=0)], 
                       value=ast.Call(func=ast.Name(id='StringIO', ctx=Load(), lineno=1, col_offset=0),
                                      args=[], keywords=[], starargs=None, kwargs=None, lineno=1, col_offset=0),
                       lineno=1, col_offset=0),
            ast.Assign(targets=[ast.Name(id=self.OUTPUT_WRITER, ctx=Store(), lineno=1, col_offset=0)], 
                       value=ast.Attribute(value=ast.Name(id=self.OUTPUT_NAME, ctx=Load(), lineno=1, col_offset=0),
                                           attr='write', ctx=Load(), lineno=1, col_offset=0),
                                 lineno=1, col_offset=0)], lineno=1, col_offset=0)
        nodes_list = self.ctx.to_list()
        for i in merged_nodes(nodes_list):
            module_tree.body.append(i.to_ast(self.OUTPUT_WRITER))
        return module_tree

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
                #print last_state.__name__, token, state.__name__#, state_data
                state_data = self.process(last_state, state, state_data)
                last_state = state

        while self.stack:
            self.pop_stack()

    def _get_level(self, line):
        level = len(line)/self.indent_level
        if self.ctx_type == 'slot':
            return level - self._slot_level
        return level

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
            self.add_tag(data[1:])
            return []
        if state is InitialState and last_state is TagNameState:
            self.add_tag(data[1:])
            self.ctx.nodes.append(TextNode(u'\n'))
            return []
        # @div.
        if last_state is TagNameState and state is TagAttrState:
            self.add_tag(data[1:-1])
            return []
        # @div.class(
        if last_state is TagAttrNameState and state is TagAttrTextState:
            self.add_attr_name(data[0][1])
            return []
        # @div.class( text)
        if last_state is TagAttrTextState and state is EndTagAttrState:
            self.add_text(data[:-1])
            # we have attr node last in stack
            self.pop_stack()
            return []
        # @div.class( {{ expr }})
        if last_state is TagAttrExpressionState and state is EndTagAttrState:
            self.add_expression(data[1:-1])
            self.pop_stack()
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
            return []
        if last_state is EndTagAttrState and state is InitialState:
            self.ctx.nodes.append(TextNode(u'\n'))
            return []
        if last_state is StatementForState and state is InitialState:
            self.add_statement_for(data)
            return []
        return data

    def add_tag(self, data):
        #print 'add tag:', ''.join((v[1] for v in data ))
        t, val = data[0]
        node = TagNode(val)
        self.ctx.nodes.append(node)
        self.push_stack(node)

    def add_text(self, data):
        #print 'add text:', ''.join((v[1] for v in data ))
        self.ctx.nodes.append(TextNode(u''.join([v[1] for v in data ]), 
                                       lineno=self.lineno, col_offset=self.col_offset))

    def add_expression(self, data):
        #print 'add expression:', ''.join((v[1] for v in data ))
        self.ctx.nodes.append(ExprNode(u''.join([v[1] for v in data ]).lstrip(), 
                              lineno=self.lineno, col_offset=self.col_offset))

    def add_attr_name(self, data):
        #print 'add attr name:', data
        attr = AttrNode(data)
        self.ctx.set_attr(attr)
        self.push_stack(attr)

    def set_level(self, data):
        level = self._get_level(data)
        self.ctx.nodes.append(TextNode(data))
        #print 'set indention:', level, self.level
        if level <= self.level:
            for y in range(self.level - level):
                self.pop_stack()

    def add_statement_for(self, data):
        node = ForStatementNode(u''.join([v[1] for v in data ]), 
                                lineno=self.lineno, col_offset=self.col_offset)
        self.ctx.nodes.append(node)
        self.push_stack(node)


if __name__ == '__main__':
    import sys
    file_name = sys.argv[1]
    parser = Parser()
    parser.parse(open(file_name, 'r'))
