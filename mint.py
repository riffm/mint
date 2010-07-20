# -*- coding: utf-8 -*-

'''
mint - small, fast and simple template engine.
Inspired by haml.
'''

import weakref
import logging
import mmap
import re
import ast
import htmlentitydefs
from os import path
from ast import Load, Store, Param
from StringIO import StringIO
from collections import deque

logger = logging.getLogger(__name__)

############# LEXER

class TokenWrapper(object):
    '''
    Objects of this class reprezents tokens
    '''

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
TOKEN_BASE_TEMPLATE = TokenWrapper('base_template', value='%sbase: ' % STMT_CHAR)
TOKEN_STATEMENT_IF = TokenWrapper('statement_if', value='%sif ' % STMT_CHAR)
TOKEN_STATEMENT_ELIF = TokenWrapper('statement_elif', value='%selif ' % STMT_CHAR)
TOKEN_STATEMENT_ELSE = TokenWrapper('statement_else', value='%selse:' % STMT_CHAR)
TOKEN_STATEMENT_FOR = TokenWrapper('statement_for', value='%sfor ' % STMT_CHAR)
TOKEN_SLOT_DEF = TokenWrapper('slot_def', value='%sdef ' % STMT_CHAR)
TOKEN_STMT_CHAR = TokenWrapper('hash', value=STMT_CHAR)
TOKEN_COMMENT = TokenWrapper('comment', value=COMMENT_CHAR)
TOKEN_BACKSLASH = TokenWrapper('backslash', value='\\')
TOKEN_DOT = TokenWrapper('dot', value='.')
TOKEN_COLON = TokenWrapper('colon', value=':')
TOKEN_PARENTHESES_OPEN = TokenWrapper('parentheses_open', value='(')
TOKEN_PARENTHESES_CLOSE = TokenWrapper('parentheses_close', value=')')
TOKEN_EXPRESSION_START = TokenWrapper('expression_start', value='{{')
TOKEN_EXPRESSION_END = TokenWrapper('expression_end', value='}}')
TOKEN_WHITESPACE = TokenWrapper('whitespace', regex_str=r'\s+')
TOKEN_NEWLINE = TokenWrapper('newline', regex_str=r'(\r\n|\r|\n)')
TOKEN_EOF = EOF()
TOKEN_TEXT = TextToken()


#tokens = [v for v in locals().values() if isinstance(v, TokenWrapper)]

tokens = (
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
    TOKEN_PARENTHESES_OPEN,
    TOKEN_PARENTHESES_CLOSE,
    TOKEN_EXPRESSION_START,
    TOKEN_EXPRESSION_END,
    TOKEN_COLON,
    TOKEN_WHITESPACE,
    TOKEN_NEWLINE,
)

all_tokens = list(tokens) + [TOKEN_EOF, TOKEN_TEXT]

re_comment = re.compile(r'\s*//')

class TokensStream(object):
    'Tokenizer. Generates tokens stream from text'

    def __init__(self, fp):
        self.fp = fp
        self.current = None

    def tokenize(self):
        if isinstance(self.fp, StringIO):
            map = self.fp
            size = map.len
        else:
            map = mmap.mmap(self.fp.fileno(), 0, access=mmap.ACCESS_READ)
            size = map.size()
        lineno = 0
        pos = 0
        while 1:
            lineno += 1

            # end of file
            if map.tell() == size:
                yield TOKEN_EOF, 'EOF', lineno, 0
                break

            # now we tokinoxe line by line
            line = map.readline().decode('utf-8')
            line = line.replace('\n', '')
            is_comment = re_comment.match(line)
            if is_comment:
                continue

            last_text = deque()
            while line:
                line_len = len(line)
                for token in tokens:
                    if line:
                        m = token.regex.match(line)
                        if m:
                            if last_text:
                                yield TOKEN_TEXT, ''.join(last_text), lineno, pos - 1
                                last_text.clear()
                            if token is TOKEN_COMMENT:
                                line=''
                                continue
                            offset, value = m.end(), m.group()
                            line = line[offset:]
                            yield token, value, lineno, pos
                            pos += offset

                # we did not get right in tokens list, so next char is text
                if line_len == len(line):
                    last_text.append(line[0])
                    line = line[1:]

            if last_text:
                yield TOKEN_TEXT, ''.join(last_text), lineno, pos
                last_text.clear()
            yield TOKEN_NEWLINE, '\n', lineno, pos

        # all work is done
        map.close()


############# LEXER END

############# NODES
# Theese nodes are additional nodes, which helps to
# optimize AST building

UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))
UNSAFE_CHARS_ENTITIES_REVERSED = [(v,k) for k,v in UNSAFE_CHARS_ENTITIES]


def escape(obj, ctx='tag'):
    if hasattr(obj, '__html__'):
        if ctx == 'tag':
            return obj.__html__()
        else:
            return escape(unescape(obj))
    text = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


def unescape(obj):
    text = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES_REVERSED:
        text = text.replace(k, v)
    return text


class TextNode(object):
    '''Simple node, represents text'''

    def __init__(self, value, escaping=True, lineno=None, col_offset=None, level=None):
        if escaping:
            #value = unescape(value)
            self.value = escape(value)
        else:
            self.value = value
        # default values to lineno and col_offset
        self.lineno = lineno if lineno else 1
        self.col_offset = col_offset if col_offset else 1
        self.level = level if level else 0

    def to_ast(self, writer_name):
        value = ast.Str(s=self.value, lineno=self.lineno, col_offset=self.col_offset)
        return ast.Expr(value=ast.Call(func=ast.Name(id=writer_name, ctx=Load(), 
                                                     lineno=self.lineno, col_offset=self.col_offset),
                                       args=[value],
                                       keywords=[], starargs=None, kwargs=None,
                                       lineno=self.lineno, col_offset=self.col_offset),
                        lineno=self.lineno, col_offset=self.col_offset)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.value)


class ExprNode(object):
    '''Simple node, represents python expression'''

    def __init__(self, value, lineno=None, col_offset=None, ctx='tag'):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset
        self.ctx = ctx

    def to_ast(self, writer_name):
        unicode_call = ast.Call(func=ast.Name(id='unicode', ctx=Load(), 
                                              lineno=self.lineno, col_offset=self.col_offset),
                                args=[ast.parse(self.value).body[0].value],
                                keywords=[], starargs=None, kwargs=None,
                                lineno=self.lineno, col_offset=self.col_offset)
        value = ast.Call(func=ast.Name(id=ESCAPE_HELLPER, ctx=Load(), 
                                       lineno=self.lineno, col_offset=self.col_offset),
                         args=[unicode_call],
                         keywords=[ast.keyword(arg='ctx', value=ast.Str(s=self.ctx, 
                                                   lineno=self.lineno, 
                                                   col_offset=self.col_offset))], 
                         starargs=None, kwargs=None,
                         lineno=self.lineno, col_offset=self.col_offset)
        return ast.Expr(value=ast.Call(func=ast.Name(id=writer_name, ctx=Load(), 
                                                     lineno=self.lineno, 
                                                     col_offset=self.col_offset),
                                       args=[value],
                                       keywords=[], starargs=None, kwargs=None,
                                       lineno=self.lineno, col_offset=self.col_offset),
                        lineno=self.lineno, col_offset=self.col_offset)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.value)


class AttrNode(object):

    def __init__(self, name, append=False):
        self.name = TextNode(name)
        self.nodes = []
        self.append = append

    def to_list(self):
        nodes_list = []
        nodes_list.append(TextNode(u' '))
        nodes_list.append(self.name)
        nodes_list.append(TextNode(u'="', escaping=False))
        for node in self.nodes:
            nodes_list.append(node)
        nodes_list.append(TextNode(u'"', escaping=False))
        return nodes_list

    def __repr__(self):
        return '%s(%s=%r)' % (self.__class__.__name__, self.name, self.nodes)


class TagNode(object):
    '''This class represents tag and can store tag attributes
    and other nodes inside.

    to_list() returns list of simple nodes like TextNode, ExprNode
    List items are not merged, so you need to use merged_nodes(), to
    get merged nodes generator.
    '''

    _selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']

    def __init__(self, name, level):
        self.name = name
        self.nodes = []
        self._attrs = []
        self.level = level

    def set_attr(self, node):
        self._attrs.append(node)

    def to_list(self):
        nodes_list = []

        # open tag
        if self.name:
            nodes_list.append(TextNode(u'<%s' % self.name, escaping=False))
        if self._attrs:
            for attr in self._attrs:
                # here we need to process attrs with same name
                nodes_list += attr.to_list()
        if self.name in self._selfclosed:
            nodes_list.append(TextNode(u' />\n', escaping=False))
            #XXX: all child nodes of selfclosed tags are ignored
            return nodes_list
        elif self.name:
                nodes_list.append(TextNode(u'>\n', escaping=False))

        # collect other nodes
        for node in self.nodes:
            if isinstance(node, self.__class__):
                nodes_list += node.to_list()
            else:
                nodes_list.append(node)
        # close tag
        if self.name:
            nodes_list.append(TextNode(u'</%s>\n' % self.name, escaping=False))
        return nodes_list

    def __repr__(self):
        return '%s(%r, level=%r, nodes=%r, attrs=%r)' % (self.__class__.__name__,
                                                         self.name, self.level,
                                                         self.nodes, self._attrs)


class ForStatementNode(object):

    def __init__(self, expr, lineno, col_offset):
        self.expr = expr
        self.lineno = lineno
        self.col_offset = col_offset
        self.nodes = []

    def to_ast(self, writer_name):
        nodes = nodes_to_list(self.nodes)
        expr = self.expr.strip()
        if expr[-1] != ':':
            expr += ':'
        if expr.startswith('#'):
            expr = expr[1:]
        expr = expr + ' pass'
        tree = ast.parse(expr).body[0]
        # clear tree body from Pass()
        tree.body = []
        for node in merged_nodes(nodes):
            tree.body.append(node.to_ast(writer_name))
        return tree

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.expr,
                                   self.lineno, self.col_offset)


class IfStatementNode(object):

    def __init__(self, expr, lineno, col_offset, orelse=None):
        self.expr = expr
        self.lineno = lineno
        self.col_offset = col_offset
        self.orelse = orelse if orelse is not None else []
        self.nodes = []

    def to_ast(self, writer_name):
        expr = self.expr.strip()
        if expr[-1] != ':':
            expr += ':'
        if expr.startswith('#'):
            expr = expr[1:]
        if expr.startswith('elif'):
            expr = expr[2:]
        expr = expr + ' pass'
        tree = ast.parse(expr).body[0]
        # clear tree body from Pass()
        tree.body = []
        nodes = nodes_to_list(self.nodes)
        for node in merged_nodes(nodes):
            tree.body.append(node.to_ast(writer_name))
        for node in merged_nodes(nodes_to_list(self.orelse)):
            if isinstance(node, self.__class__):
                tree.orelse.append(node.to_ast(writer_name))
            elif isinstance(node, StatementElse):
                for n in merged_nodes(nodes_to_list(node.nodes)):
                    tree.orelse.append(n.to_ast(writer_name))
        return tree

    def __repr__(self):
        return '%s(%r, %r, %r, orelse=%r)' % (self.__class__.__name__, self.expr,
                                              self.lineno, self.col_offset, self.orelse)


class StatementElse(object):

    def __init__(self):
        self.nodes = []


class SlotDefNode(object):

    def __init__(self, expr, lineno, col_offset):
        self.expr = expr
        self.nodes = []
        self.name = expr[4:expr.find('(')]
        self.lineno = lineno
        self.col_offset = col_offset

    def to_ast(self, writer_name):
        nodes = nodes_to_list(self.nodes)
        expr = self.expr.strip()
        if expr[-1] != ':':
            expr += ':'
        if expr.startswith('#'):
            expr = expr[1:]
        expr = expr + ' pass'
        tree = ast.parse(expr).body[0]
        # clear tree body from Pass()
        tree.body = []
        for node in merged_nodes(nodes):
            tree.body.append(node.to_ast(writer_name))
        return tree

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.expr,
                           self.lineno, self.col_offset)


class SlotCallNode(object):
    '''Simple slot call, represents python function call'''

    def __init__(self, value, lineno, col_offset):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset

    def to_ast(self, writer_name):
        return ast.parse(self.value).body[0]

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.value)


def nodes_to_list(nodes, nodes_list=None):
    if nodes_list is None:
        nodes_list = []
    for n in nodes:
        if isinstance(n, TagNode):
            nodes_list += n.to_list()
        else:
            nodes_list.append(n)
    return nodes_list


def merge(a, b):
    if isinstance(a, TextNode) and isinstance(b, TextNode):
        return TextNode(a.value+b.value, escaping=False)
    return None


def merged_nodes(nodes_list):
    '''Returns generator of merged nodes.
    nodes_list - list of simple nodes.'''
    last = None
    for n in nodes_list:
        if last is not None:
            result = merge(last, n)
            if result is None:
                yield last
                last = n
                continue
            last = result
        else:
            last = n
            continue
    if last is not None:
        yield last

############# NODES END



############# PARSER
#TODO
# + Escaping
# + "IF-ELIF-ELSE" statement
# - "IF-ELIF-ELSE" templates error handling
# + "FOR" statement
# + blocks (inheritance)
# - python variables (i.e. #a = 'hello')
# + '\' escaping of '@' '#'

class TemplateError(Exception): pass
class WrongToken(Exception): pass

# States
class State(object):

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


def AnyToken(exclude=None):
    if exclude is None:
        return tokens
    else:
        return [t for t in tokens if t not in exclude]


class InitialState(State):
    variantes = [
        (TOKEN_BASE_TEMPLATE, 'BaseTemplatesNameState'),
        (TOKEN_SLOT_DEF, 'SlotDefState'),
        (TOKEN_TAG_START , 'TagState'),
        ((TOKEN_WHITESPACE, TOKEN_NEWLINE), ),
        (TOKEN_EXPRESSION_START, 'ExpressionState'),
        (TOKEN_BACKSLASH, 'EscapedTextLineState'),
        (TOKEN_STATEMENT_FOR, 'StatementForState'),
        (TOKEN_STATEMENT_IF, 'StatementIfState'),
        (TOKEN_STATEMENT_ELIF, 'StatementElifState'),
        (TOKEN_STATEMENT_ELSE, 'StatementElseState'),
        (TOKEN_STMT_CHAR, 'SlotCallState'),
        ((TOKEN_WHITESPACE, TOKEN_TEXT), 'TextState'),
    ]


class EscapedTextLineState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens, ),
    ]


class TagState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (TOKEN_TEXT, 'TagNameState'),
    ]

class TagNameState(State):
    variantes = [
        (TOKEN_DOT, 'TagAttrState'),
        (TOKEN_WHITESPACE, 'EndTagState'),
        (TOKEN_NEWLINE, 'InitialState'),
    ]


class TagAttrState(State):
    variantes = [
        (TOKEN_TEXT, 'TagAttrNameState'),
    ]


class TagAttrNameState(State):
    variantes = [
        ((TOKEN_TEXT, TOKEN_COLON), ),
        (TOKEN_PARENTHESES_OPEN, 'TagAttrTextState'),
    ]


class TagAttrTextState(State):
    variantes = [
        (TOKEN_PARENTHESES_CLOSE, 'EndTagAttrState'),
        (TOKEN_EXPRESSION_START, 'TagAttrExpressionState'),
        (all_tokens,),
    ]


class TagAttrExpressionState(State):
    variantes = [
        #(TOKEN_PARENTHESES_CLOSE, 'EndTagAttrState'),
        (TOKEN_EXPRESSION_END, 'TagAttrTextState'),
        (all_tokens,),
    ]


class EndTagAttrState(State):
    variantes = [
        (TOKEN_DOT, 'TagAttrState'),
        (TOKEN_NEWLINE, 'InitialState'),
        (TOKEN_WHITESPACE, 'EndTagState'),
        (all_tokens, 'TextState'),
    ]


class EndTagState(State):
    variantes = [
        (TOKEN_TAG_START, 'TagState'),
        (TOKEN_EXPRESSION_START, 'ExpressionState'),
        (TOKEN_WHITESPACE, ),
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens, 'TextState'),
    ]


class TextState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (TOKEN_EXPRESSION_START, 'ExpressionState'),
        (all_tokens,),
    ]


class ExpressionState(State):
    variantes = [
        (TOKEN_EXPRESSION_END, 'TextState'),
        (all_tokens,),
    ]


class StatementForState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


class StatementIfState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


class StatementElifState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


class StatementElseState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


class BaseTemplatesNameState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


class SlotDefState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


class SlotCallState(State):
    variantes = [
        (TOKEN_NEWLINE, 'InitialState'),
        (all_tokens,),
    ]


ESCAPE_HELLPER = '__MINT_TEXT_ESCAPE'


class Parser(object):

    # Variable's names for generated code
    OUTPUT_NAME = '__MINT__OUTPUT__'
    OUTPUT_WRITER = '__MINT__OUTPUT__WRITER__'

    NAMESPACE = {
        ESCAPE_HELLPER:escape,
        'StringIO':StringIO,
        '__builtins__':__builtins__,
    }

    def __init__(self, slots=None, indent=4, pprint=True):
        self.indent_level = indent
        self.indent = u' ' *indent
        self.__id = 0
        # parent nodes stack
        self.stack = []
        self.base = None
        # final module, which stores all prepaired nodes
        # current scope
        self.ctx = TagNode('', 0) # root tag node
        # indicates if we are in text block
        self._text_block = []
        # if elif else
        self._if_blocks = []
        # slots is dict, because any slot may be overriden in inherited templates
        self.slots = slots if slots else {}
        self.pprint = pprint

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

    def _id(self):
        self.__id += 1
        return self.__id

    @property
    def tree(self):
        module_tree = ast.Module(body=[
            ast.Assign(targets=[ast.Name(id=self.OUTPUT_NAME, ctx=Store(), 
                                         lineno=1, col_offset=0)], 
                       value=ast.Call(func=ast.Name(id='StringIO', ctx=Load(), 
                                                    lineno=1, col_offset=0),
                                      args=[], keywords=[], starargs=None, kwargs=None, 
                                      lineno=1, col_offset=0),
                       lineno=1, col_offset=0),
            ast.Assign(targets=[ast.Name(id=self.OUTPUT_WRITER, ctx=Store(), 
                                         lineno=1, col_offset=0)], 
                       value=ast.Attribute(value=ast.Name(id=self.OUTPUT_NAME, 
                                                          ctx=Load(), lineno=1, 
                                                          col_offset=0),
                                           attr='write', ctx=Load(), lineno=1, 
                                           col_offset=0),
                                 lineno=1, col_offset=0)], lineno=1, col_offset=0)

        # First we need to have slots in module_tree
        #print self.slots
        for slot in self.slots.values():
            module_tree.body.append(slot.to_ast(self.OUTPUT_WRITER))
        # Then other content
        nodes_list = self.ctx.to_list()
        #print nodes_list
        for i in merged_nodes(nodes_list):
            module_tree.body.append(i.to_ast(self.OUTPUT_WRITER))
        return module_tree

    def parse(self, tokens_stream):
        last_state = InitialState
        state_data = []
        for token, value, lineno, pos in tokens_stream:
            self.lineno = lineno
            self.col_offset = pos
            if token is TOKEN_EOF:
                break
            state_data.append((token, value))
            try:
                state = last_state.accept(token)
            except WrongToken:
                raise TemplateError('Syntax error at line %d, token "%s"' % (lineno, 
                                                                             value))
            # if state changed, we need to process data
            if state is not last_state:
                #print last_state.__name__, token, state.__name__, state_data
                state_data = self.process(last_state, state, state_data)
                last_state = state

        while self.stack:
            self.pop_stack()

    def _get_level(self, line):
        return len(line)/self.indent_level

    def _split_whitespaces(self, data):
        prefix, data = data[:-1], data[-1:]
        pos = None
        for i, d in enumerate(prefix):
            if d[0] is TOKEN_NEWLINE:
                pos = i

        if pos is None:
            return data, prefix and prefix[0][1] or u''
        else:
            if prefix[:pos+1]:
                #print 'add_text', prefix[:pos+1]
                self.add_text(prefix[:pos+1])
            if len(prefix) > pos + 1:
                return data, prefix[pos+1][1]
            return data, u''

    def process(self, last_state, state, data):
        # set level and ctx
        if last_state is InitialState:
            #print data
            data, whitespaces = self._split_whitespaces(data)
            #print '%r' % whitespaces, data
            self.set_level(whitespaces)
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
        if state is EndTagState and last_state is not EndTagAttrState:
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
            self.add_attr_name(data[1][1] if data[0][0] is TOKEN_DOT else data[0][1])
            return []
        # @div.class( text)
        if last_state is TagAttrTextState and state is EndTagAttrState:
            self.add_text(data[:-1])
            # we have attr node last in stack
            self.pop_stack()
            return []
        # @div.class( {{ expr }})
        if last_state is TagAttrExpressionState and state is EndTagAttrState:
            self.add_expression(data[1:-1], ctx='attr')
            self.pop_stack()
            return []
        # @div.class( text {{ expr }})
        if last_state is TagAttrTextState and state is TagAttrExpressionState:
            self.add_text(data[:-1])
            return []
        # @div.class({{ expr }} text )
        if last_state is TagAttrExpressionState and state is TagAttrTextState:
            self.add_expression(data[1:-1], ctx='attr')
            return []
        # @div.attr(value)\n
        if last_state is EndTagAttrState and state is not TagAttrState:
            return []
        if last_state is EndTagAttrState and state is InitialState:
            #self.ctx.nodes.append(TextNode(u'\n'))
            return []
        # #for i in range(4):
        if last_state is StatementForState and state is InitialState:
            self.add_statement_for(data)
            return []
        # #if a:
        if last_state is StatementIfState and state is InitialState:
            self.add_statement_if(data)
            return []
        # #elif a:
        if last_state is StatementElifState and state is InitialState:
            self.add_statement_elif(data)
            return []
        # #else:
        if last_state is StatementElseState and state is InitialState:
            self.add_statement_else(data)
            return []
        # #base:
        if last_state is BaseTemplatesNameState and state is InitialState:
            #XXX: should validation founds here?
            if self.lineno == 1:
                self.base_template(data[1:-1])
                return []
        # #def slot():
        if last_state is SlotDefState and state is InitialState:
            self.add_slot_def(data)
            return []
        # #slot():
        if last_state is SlotCallState and state is InitialState:
            # first token - '#'
            self.add_slot_call(data[1:])
            return []
        return data

    def add_tag(self, data):
        #print 'add tag:', ''.join((v[1] for v in data ))
        t, val = data[0]
        node = TagNode(val, self.level)
        self.ctx.nodes.append(node)
        self.push_stack(node)

    def add_text(self, data):
        #print 'add text:', '%r' % ''.join((v[1] for v in data ))
        self.ctx.nodes.append(TextNode(u''.join([v[1] for v in data ]), 
                                       lineno=self.lineno, col_offset=self.col_offset))

    def add_expression(self, data, ctx='tag'):
        #print 'add expression:', ''.join((v[1] for v in data ))
        self.ctx.nodes.append(ExprNode(u''.join([v[1] for v in data ]).lstrip(), 
                              lineno=self.lineno, col_offset=self.col_offset, ctx=ctx))

    def add_attr_name(self, data):
        #print 'add attr name:', data
        attr = AttrNode(data)
        self.ctx.set_attr(attr)
        self.push_stack(attr)

    def set_level(self, data):
        level = self._get_level(data)
        #print 'set indention:', level, self.level
        if level <= self.level:
            for y in range(self.level - level):
                self.pop_stack()

    def add_statement_for(self, data):
        node = ForStatementNode(u''.join([v[1] for v in data ]), 
                                lineno=self.lineno, col_offset=self.col_offset)
        self.ctx.nodes.append(node)
        self.push_stack(node)

    def add_statement_if(self, data):
        node = IfStatementNode(u''.join([v[1] for v in data ]), 
                                lineno=self.lineno, col_offset=self.col_offset)
        self.ctx.nodes.append(node)
        self._if_blocks.append((self.level, node))
        self.push_stack(node)

    def add_statement_elif(self, data):
        node = IfStatementNode(u''.join([v[1] for v in data ]), 
                                lineno=self.lineno, col_offset=self.col_offset)
        last = []
        for level, if_stmt in self._if_blocks:
            if self.level > level:
                last.append((level, if_stmt))
            elif self.level == level:
                if_stmt.orelse.append(node)
        last.append((self.level, node))
        self._if_blocks = last
        self.push_stack(node)

    def add_statement_else(self, data):
        node = StatementElse()
        last = []
        for level, if_stmt in self._if_blocks:
            if self.level > level:
                last.append((level, if_stmt))
            elif self.level == level:
                if_stmt.orelse.append(node)
        self._if_blocks = last
        self.push_stack(node)

    def base_template(self, data):
        self.base = u''.join([v[1] for v in data])

    def add_slot_def(self, data):
        slot_def = u''.join([v[1] for v in data])[1:]
        node = SlotDefNode(slot_def, self.lineno, self.col_offset)
        if not node.name in self.slots:
            self.slots[node.name] = node
        self.push_stack(node)

    def add_slot_call(self, data):
        #print 'add expression:', ''.join((v[1] for v in data ))
        self.ctx.nodes.append(SlotCallNode(u''.join([v[1] for v in data ]).lstrip(), 
                              lineno=self.lineno, col_offset=self.col_offset))
############# PARSER END


############# API
class TemplateNotFound(Exception):
    pass


class Template(object):

    def __init__(self, sourcefile, cache=True, loader=None):
        self.sourcefile = StringIO(sourcefile) if isinstance(sourcefile, basestring) else sourcefile
        self.filename = '<string>' if isinstance(sourcefile, basestring) else sourcefile.name
        self.need_caching = cache
        # ast
        self._tree = None
        self.compiled_code = None
        #self._loader = weakref.proxy(loader) if loader else None
        self._loader = loader

    @property
    def tree(self):
        if self._tree is None:
            tree = self.parse()
            if self.need_caching:
                self._tree = tree
            return tree
        else:
            return self._tree

    def parse(self, slots=None):
        parser = Parser(indent=4, slots=slots)
        stream = TokensStream(self.sourcefile)
        parser.parse(stream.tokenize())
        tree = parser.tree
        # templates inheritance
        if parser.base is not None:
            base_template = self._loader.get_template(parser.base)
            # one base template may have multiple childs, so
            # every time we need to get base template tree again
            tree = base_template.parse(slots=parser.slots)
        return tree

    def compile(self):
        compiled_souces = compile(self.tree, self.filename, 'exec')
        if self.need_caching:
            self.compiled_code = compiled_souces
        return compiled_souces

    def render(self, **kwargs):
        if self.compiled_code is None:
            code = self.compile()
        else:
            code = self.compiled_code
        ns = Parser.NAMESPACE.copy()
        ns['utils'] = utils
        ns.update(kwargs)
        exec code in ns
        return ns[Parser.OUTPUT_NAME].getvalue()


class Loader(object):

    def __init__(self, *dirs, **kwargs):
        cache = kwargs.get('cache', False)
        self.dirs = []
        for dir in dirs:
            self.dirs.append(path.abspath(dir))
        self.need_caching = cache
        self._templates_cache = {}

    def get_template(self, template):
        if template in self._templates_cache:
            return self._templates_cache[template]
        for dir in self.dirs:
            location = path.join(dir, template)
            if path.exists(location) and path.isfile(location):
                tmpl = Template(open(location, 'r'), cache=self.need_caching,
                                loader=self)
                self._templates_cache[template] = tmpl
                return tmpl
        raise TemplateNotFound(template)

    def __add__(self, other):
        self.dirs = self.dirs + other.dirs
        return self


#TODO: Implement string (unicode) interface
class Markup(unicode):

    def __new__(cls, obj=u'', **kwargs):
        if hasattr(obj, '__html__'):
            obj = obj.__html__()
        return super(Markup, cls).__new__(cls, obj, **kwargs)

    def __html__(self):
        return self

    def __unicode__(self):
        return self

    def __repr__(self):
        return 'Markup(%s)' % super(Markup, self).__repr__()


class utils(object):

    DT_HTML_STRICT = Markup('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                            '"http://www.w3.org/TR/html4/strict.dtd">')
    DT_HTML_TRANSITIONAL = Markup('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 '
                      'Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">')
    DT_XHTML_STRICT = Markup('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
                             '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')
    DT_XHTML_TRANSITIONAL = Markup('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 '
    'Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">')
    DT_HTML5 = Markup('<!DOCTYPE html>')
    markup = Markup

    @staticmethod
    def loop(iterable):
        return Looper(iterable)

    @staticmethod
    def entity(char):
        return CHARS_ENTITIES.get(char, char)


class Looper:
    'Cool class taken from PPA project'
    class _Item:
        def __init__(self, index, has_next):
            self.index = index
            self.has_next = has_next
            self.last = not has_next
            self.first = not index
        @property
        def odd(self):
            return self.index % 2
        @property
        def even(self):
            return not self.index % 2
        def cycle(self, *args):
            'Magic method (adopted ;)'
            return args[self.index % len(args)]

    def __init__(self, iterable):
        self._iterator = iter(iterable)

    def _shift(self):
        try:
            self._next = self._iterator.next()
        except StopIteration:
            self._has_next = False
        else:
            self._has_next = True

    def __iter__(self):
        self._shift()
        index = 0
        while self._has_next:
            value = self._next
            self._shift()
            yield value, self._Item(index, self._has_next)
            index += 1


############# API END

class Printer(ast.NodeVisitor):
    'AST printer'

    def __init__(self):
        self._indent = 0
        self._indent_tab = '    '
        self.src = StringIO()
        self.write = self.src.write
        self._in_args = False
        self._in_if = False

    def make_tab(self):
        self.src.write(self._indent*self._indent_tab)

    def visit_FunctionDef(self, node):
        self.make_tab()
        self.src.write('def %s(' % node.name)
        self._in_args = True
        total_args = len(node.args.args)
        default_args_len = len(node.args.defaults) if node.args.defaults else 0
        for i, arg in enumerate(node.args.args):
            if i != 0:
                self.src.write(', ')
            self.visit(arg)
            if default_args_len > 0 and i >= (total_args - default_args_len):
                self.src.write('=')
                y = (total_args - default_args_len) - i
                self.visit(node.args.defaults[y])
        self._in_args = False
        self.src.write('):\n')
        self._indent += 1
        for n in node.body:
            self.visit(n)
        self._indent -= 1

    def visit_Name(self, node):
        self.src.write(node.id)

    def visit_Str(self, node):
        self.src.write('%r' % node.s)

    def visit_Num(self, node):
        self.src.write('%d' % node.n)

    def visit_Pass(self, node):
        self.make_tab()
        self.src.write('pass\n')

    def visit_If(self, node):
        self.make_tab()
        if self._in_if:
            self.src.write('elif ')
        else:
            self.src.write('if ')
        self.visit(node.test)
        self.src.write(':\n')
        self._indent += 1
        for n in node.body:
            self.visit(n)
        self._indent -= 1
        if node.orelse:
            self._in_if = True
            if not isinstance(node.orelse[0], ast.If):
                self.make_tab()
                self.src.write('else:\n')
                self._indent += 1
            for orelse in node.orelse:
                self.visit(orelse)
            if not isinstance(node.orelse[0], ast.If):
                self._indent -= 1
            self._in_if = False

    def visit_Compare(self, node):
        self.visit(node.left)
        self.src.write(' ')
        for op in node.ops:
            self.visit(op)
        self.src.write(' ')
        for comp in node.comparators:
            self.visit(comp)

    def visit_For(self, node):
        self.make_tab()
        self.write('for ')
        self.visit(node.target)
        self.write(' in ')
        self._in_args = True
        self.visit(node.iter)
        self._in_args = False
        self.write(':\n')
        self._indent += 1
        for n in node.body:
            self.visit(n)
        self._indent -= 1

    #def visit_IfExp(self, node):
        #self.make_tab()
        #self.src.write('if ')
        #self.visit(node.test)
        #self.src.write(':\n')
        #self.indent += 1
        #self.generic_visit(node)
        #self.indent -= 1

    def visit_Tuple(self, node):
        self.src.write('(')
        for i,el in enumerate(node.elts):
            if i != 0:
                self.src.write(', ')
            self.visit(el)
        self.src.write(')')

    def visit_List(self, node):
        self.src.write('[')
        for i,el in enumerate(node.elts):
            if i != 0:
                self.src.write(', ')
            self.visit(el)
        self.src.write(']')

    def visit_Assign(self, node):
        self.make_tab()
        for target in node.targets:
            self.visit(target)
        self.src.write(' = ')
        self._in_args = True
        self.visit(node.value)
        self._in_args = False
        self.src.write('\n')

    def visit_Call(self, node):
        if self._in_args:
            self.visit(node.func)
            self.src.write('(')
            for i, arg in enumerate(node.args):
                if i != 0:
                    self.src.write(', ')
                self.visit(arg)
            self.src.write(')')
        else:
            self.make_tab()
            self.visit(node.func)
            self.src.write('(')
            self._in_args = True
            for i, arg in enumerate(node.args):
                if i != 0:
                    self.src.write(', ')
                self.visit(arg)
            self.src.write(')')
            self._in_args = False
            self.src.write('\n')

    def visit_Attribute(self, node):
        self.visit(node.value)
        self.src.write('.')
        self.src.write(node.attr)

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.src.write(' ')
        self.visit(node.op)
        self.src.write(' ')
        self.visit(node.right)

    # Operators
    def visit_Add(self, node):
        self.src.write('+')

    def visit_Mod(self, node):
        self.src.write('%')

    def visit_Eq(self, node):
        self.src.write('==')

    def visit_NotEq(self, node):
        self.src.write('!=')

    def visit_Lt(self, node):
        self.src.write('<=')

    def visit_Gt(self, node):
        self.src.write('>=')


if __name__ == '__main__':
    from sys import argv
    import datetime
    template_name = argv[1]
    print 'TEMPLATE:  %s' % template_name
    stream = TokensStream(open(template_name, 'r'))
    start = datetime.datetime.now()
    tokens_list = [t for t in stream.tokenize()]
    tokenizer_delta = datetime.datetime.now() - start
    print 'TOKENIZER: %s s' % (tokenizer_delta)
    template = Loader('.').get_template(template_name)
    parser = Parser()
    start = datetime.datetime.now()
    parser.parse(TokensStream(open(template_name, 'r')).tokenize())
    end = datetime.datetime.now()
    print 'PARSER:   %s s' % (end - start)
    start = datetime.datetime.now()
    compiled_souces = compile(template.tree, template_name, 'exec')
    end = datetime.datetime.now()
    print 'COMPILING: %s s' % (end - start)
    printer = Printer()
    printer.visit(template.tree)
    print printer.src.getvalue()
