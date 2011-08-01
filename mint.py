# -*- coding: utf-8 -*-

'''
mint - small, fast and simple template engine.
'''

import os
import re
import ast
import mmap
import time
import fnmatch
import logging
import weakref
import itertools
import htmlentitydefs
from ast import Load, Store, Param
from StringIO import StringIO
from functools import partial
from collections import deque
from xml.etree.ElementTree import TreeBuilder as _TreeBuilder, Element

############# LEXER

class BaseToken(object):
    pass

class TokenWrapper(BaseToken):
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


class TextToken(BaseToken):
    'Special token for text'
    def __str__(self):
        return 'text'
    __repr__ = __str__


class TokenIndent(BaseToken):
    def __str__(self):
        return 'indent'
    __repr__ = __str__


class TokenUnindent(BaseToken):
    def __str__(self):
        return 'unindent'
    __repr__ = __str__


class EOF(BaseToken):
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

############# LEXER END

UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES_IN_ATTR = [(k, CHARS_ENTITIES[k]) for k in '<>"']
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))
UNSAFE_CHARS_ENTITIES_IN_ATTR.append(("'",'&#39;'))
UNSAFE_CHARS_ENTITIES_REVERSED = [(v,k) for k,v in UNSAFE_CHARS_ENTITIES]


def escape(obj, ctx='tag'):
    if hasattr(obj, '__html__'):
        safe_markup = obj.__html__()
        if ctx == 'tag':
            return safe_markup
        else:
            for k, v in UNSAFE_CHARS_ENTITIES_IN_ATTR:
                safe_markup = safe_markup.replace(k, v)
            return safe_markup
    obj = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        obj = obj.replace(k, v)
    return obj


def unescape(obj):
    text = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES_REVERSED:
        text = text.replace(k, v)
    return text


class TemplateError(Exception): pass
class WrongToken(Exception): pass

# variables names (we do not want to override user variables and vise versa)
TREE_BUILDER = '__MINT_TREE_BUILDER__'
TREE_FACTORY = '__MINT_TREE_FACTORY__'
MAIN_FUNCTION = '__MINT_MAIN__'
TAG_START = '__MINT_TAG_START__'
TAG_END = '__MINT_TAG_END__'
DATA = '__MINT_DATA__'
ESCAPE_HELLPER = '__MINT_ESCAPE__'
CURRENT_NODE = '__MINT_CURRENT_NODE__'


##### MINT NODES

class Node(ast.AST):
    def __repr__(self):
        return '%s' % self.__class__.__name__


class MintTemplate(Node):
    def __init__(self, body=None):
        self.body = body or []

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.body==other.body
        return False

    def __repr__(self):
        return '%s(body=%r)' % (self.__class__.__name__, self.body)


class BaseTemplate(Node):
    def __init__(self, name):
        self.name = name

    def to_ast(self):
        return self

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name == other.name
        return False


class TextNode(Node):
    def __init__(self, text, lineno=None, col_offset=None):
        self.text = text
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.text==other.text and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.text,
                                                     self.lineno, self.col_offset)


class ExpressionNode(Node):
    def __init__(self, text, lineno=None, col_offset=None):
        self.text = text.strip()
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.text==other.text and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.text,
                                                     self.lineno, self.col_offset)


class TagAttrNode(Node):
    def __init__(self, name, value=None, lineno=None, col_offset=None):
        self.name = escape(name, ctx='attr')
        self.value = value or []
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name==other.name and self.value==other.value and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, value=%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.name,
                                                               self.value, self.lineno, self.col_offset)


class SetAttrNode(Node):
    def __init__(self, attr_node):
        self.attr = attr_node

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.attr==other.attr
        return False


class AppendAttrNode(Node):
    def __init__(self, attr_node):
        self.attr = attr_node

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.attr==other.attr
        return False


class TagNode(Node):
    def __init__(self, name, attrs=None, body=None, lineno=None, col_offset=None):
        self.name = name
        self.attrs = attrs or []
        self.body = body or []
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name==other.name and self.body==other.body and self.attrs==other.attrs\
                   and self.lineno==other.lineno and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, attrs=%r, body=%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.name,
            self.attrs, self.body, self.lineno, self.col_offset)


class ForStmtNode(Node):
    def __init__(self, text, body=None, lineno=None, col_offset=None):
        self.text = text.strip()
        self.body = body or []
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.text==other.text and self.body==other.body and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, body=%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.text,
                                                              self.body, self.lineno, self.col_offset)


class IfStmtNode(Node):
    def __init__(self, text, body=None, orelse=None, lineno=None, col_offset=None):
        self.text = text
        self.body = body or []
        self.orelse = orelse or []
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.text==other.text and self.body==other.body and self.orelse==other.orelse\
                   and self.lineno==other.lineno and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, body=%r, orelse=%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, 
                                                self.text, self.body,
                                                self.orelse, self.lineno, self.col_offset)


class ElseStmtNode(Node):
    def __init__(self, body=None, lineno=None, col_offset=None):
        self.body = body or []
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.body==other.body and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(body=%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.body,
                                                          self.lineno, self.col_offset)


class SlotDefNode(Node):
    def __init__(self, text, body=None, lineno=None, col_offset=None):
        self.text = text.strip()
        self.body = body or []
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.text==other.text and self.body==other.body and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, body=%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.text,
                                                              self.body, self.lineno, self.col_offset)


class SlotCallNode(Node):
    def __init__(self, text, lineno=None, col_offset=None):
        self.text = text.strip()
        self.lineno = lineno
        self.col_offset = col_offset

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.text==other.text and self.lineno==other.lineno \
                   and self.col_offset==other.col_offset
        return False

    def __repr__(self):
        return '%s(%r, lineno=%d, col_offset=%d)' % (self.__class__.__name__, self.text, 
                                                     self.lineno, self.col_offset)

##### NODES END


##### PARSER

class RecursiveStack(object):
    'Stack of stacks'
    def __init__(self):
        self.stacks = [[]]

    @property
    def stack(self):
        return self.stacks[-1]

    @property
    def current(self):
        return self.stack and self.stack[-1] or None

    def push(self, item):
        self.stack.append(item)
        return True

    def pop(self):
        return self.stack.pop()
        return True

    def push_stack(self, new_stack):
        self.stacks.append(new_stack)

    def pop_stack(self):
        return self.stacks.pop()

    def __nonzero__(self):
        return len(self.stacks)

    def __repr__(self):
        return repr(self.stacks)

    def __iter__(self):
        return reversed(self.stack[:])


class Parser(object):
    def __init__(self, states):
        self.states = dict(states)

    def parse(self, tokens_stream, stack):
        current_state = 'start'
        variantes = self.states[current_state]
        for tok in tokens_stream:
            token, tok_value, lineno, pos = tok

            # accept new token
            new_state = None
            for item in variantes:
                variante, state, callback = item
                # tokens sequence
                if isinstance(variante, basestring):
                    variante = globals().get(variante)
                if isinstance(variante, (list, tuple)):
                    if token in variante:
                        new_state = state
                        break
                elif variante is token:
                    new_state = state
                    break
                elif isinstance(variante, Parser):
                    variante.parse(itertools.chain([tok], tokens_stream), stack)
                    new_state = state
                    #NOTE: tok still points to first token

            if new_state is None:
                raise WrongToken('[%s] Unexpected token "%s(%r)" at line %d, pos %d' \
                        % (current_state, token, tok_value, lineno, pos))
            # process of new_state
            elif new_state != current_state:
                if new_state == 'end':
                    #print current_state, '%s(%r)' % (token, tok_value), new_state
                    callback(tok, stack)
                    #_print_stack(stack)
                    break
                current_state = new_state
                variantes = self.states[current_state]
            # state callback
            #print current_state, '%s(%r)' % (token, tok_value), new_state
            callback(tok, stack)
            #_print_stack(stack)


def _print_stack(s):
    print '[stack]'
    for i in s:
        print ' '*4, i
    print '[end of stack]\n'


# utils functions
def get_tokens(s):
    my_tokens = []
    while s.current and isinstance(s.current, (list, tuple)):
        my_tokens.append(s.pop())
    my_tokens.reverse()
    return my_tokens

#NOTE: Callbacks are functions that takes token and stack
skip = lambda t, s: None
push = lambda t, s: s.push(t)
pop_stack = lambda t, s: s.pop_stack()
def push_stack(t, s):
    if isinstance(s.current, ElseStmtNode):
        stmt = s.pop()
        s.push_stack(stmt.body)
    elif isinstance(s.current, IfStmtNode) and s.current.orelse:
        s.push_stack(s.current.orelse[-1].body)
    else:
        if not hasattr(s.current, 'body'):
            raise SyntaxError('Unexpected indent at line %d' % t[2])
        s.push_stack(s.current.body)


# text data and inline python expressions
def py_expr(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3] - 2
    s.push(ExpressionNode(u''.join([t[1] for t in my_tokens]), 
                                lineno=lineno, col_offset=col_offset))

def text_value(t, s):
    my_tokens = get_tokens(s)
    if my_tokens:
        lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
        s.push(TextNode(u''.join([t[1] for t in my_tokens]), 
                        lineno=lineno, col_offset=col_offset))

def text_value_with_last(t, s):
    s.push(t)
    text_value(t, s)

# parser of attribute value
attr_data_parser = Parser((
    # state name
    ('start', (
        # variantes (token, new_state, callback)
        #           ((token, token,...), new_state, callback)
        #           (other_parser, new_state, callback)
        #           ('other_parser', new_state, callback)
        (TOKEN_EXPRESSION_START, 'expr', text_value),
        (TOKEN_PARENTHESES_CLOSE, 'end', text_value),
        (all_except(TOKEN_NEWLINE), 'start', push),
        )),
    ('expr', (
        (TOKEN_EXPRESSION_END, 'start', py_expr),
        (all_tokens, 'expr', push),
        )),
))


# parser of text data and inline python expressions
data_parser = Parser((
    ('start', (
        (TOKEN_EXPRESSION_START, 'expr', text_value),
        (TOKEN_NEWLINE, 'end', text_value_with_last),
        (all_except(TOKEN_INDENT), 'start', push),
        )),
    ('expr', (
        (TOKEN_EXPRESSION_END, 'start', py_expr),
        (all_tokens, 'expr', push),
        )),
))


# tag and tag attributes callbacks
def tag_name(t, s):
    #if isinstance(s.current, (list, tuple)):
    my_tokens = get_tokens(s)
    if my_tokens:
        lineno, col_offset = my_tokens[0][2], my_tokens[0][3] - 1
        s.push(TagNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset))

def tag_attr_name(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(TagAttrNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset))

def tag_attr_value(t, s):
    nodes = []
    while not isinstance(s.current, TagAttrNode):
        nodes.append(s.pop())
    attr = s.current
    nodes.reverse()
    attr.value = nodes

def set_attr(t, s):
    nodes = []
    while not isinstance(s.current, TagAttrNode):
        nodes.append(s.pop())
    attr = s.pop()
    nodes.reverse()
    attr.value = nodes
    s.push(SetAttrNode(attr))

def append_attr(t, s):
    nodes = []
    while not isinstance(s.current, TagAttrNode):
        nodes.append(s.pop())
    attr = s.pop()
    nodes.reverse()
    attr.value = nodes
    s.push(AppendAttrNode(attr))

def tag_node(t, s):
    attrs = []
    while isinstance(s.current, TagAttrNode):
        attrs.append(s.pop())
    tag = s.pop()
    # if there were no attrs
    if isinstance(tag, (list, tuple)):
        my_tokens = get_tokens(s)
        my_tokens.append(tag)
        lineno, col_offset = my_tokens[0][2], my_tokens[0][3] - 1
        tag = TagNode(u''.join([t[1] for t in my_tokens]), 
                      lineno=lineno, col_offset=col_offset)
    if attrs:
        tag.attrs = attrs
    s.push(tag)

def tag_node_with_data(t, s):
    tag_node(t, s)
    push_stack(t, s)

# tag parser
tag_parser = Parser((
    ('start', (
        (TOKEN_TEXT, 'start', push),
        (TOKEN_MINUS, 'start', push),
        (TOKEN_COLON, 'start', push),
        (TOKEN_DOT, 'attr', tag_name),
        (TOKEN_WHITESPACE, 'continue', tag_node_with_data),
        (TOKEN_NEWLINE, 'end', tag_node),
        )),
    ('attr', (
        (TOKEN_TEXT, 'attr', push),
        (TOKEN_MINUS, 'attr', push),
        (TOKEN_COLON, 'attr', push),
        (TOKEN_PARENTHESES_OPEN, 'attr_value', tag_attr_name),
        )),
    ('attr_value', (
        (attr_data_parser, 'start', tag_attr_value),
        )),
    ('continue', (
        (TOKEN_TAG_START, 'nested_tag', skip),
        (TOKEN_NEWLINE, 'end', pop_stack),
        (data_parser, 'end', pop_stack),
        )),
    ('nested_tag', (
        ('nested_tag_parser', 'end', pop_stack),
        )),
))

# this is modified tag parser, supports inline tags with data
nested_tag_parser = Parser(dict(tag_parser.states, start=(
        (TOKEN_TEXT, 'start', push),
        (TOKEN_MINUS, 'start', push),
        (TOKEN_COLON, 'start', push),
        (TOKEN_DOT, 'attr', tag_name),
        (TOKEN_WHITESPACE, 'continue', tag_node_with_data),
        (TOKEN_NEWLINE, 'end', tag_node),
        )
).iteritems())


# base parser callbacks
def base_template(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(BaseTemplate(u''.join([t[1] for t in my_tokens])))

def html_comment(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(TextNode(Markup(u'<!-- %s -->' % (u''.join([t[1] for t in my_tokens])).strip()), 
                       lineno=lineno, col_offset=col_offset))

def for_stmt(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(ForStmtNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset))

def if_stmt(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(IfStmtNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset))

def elif_stmt(t, s):
    if not isinstance(s.current, IfStmtNode):
        pass
        #XXX: raise TemplateError
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    stmt = IfStmtNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset)
    s.current.orelse.append(stmt)

def else_stmt(t, s):
    lineno, col_offset = t[2], t[3] - 6
    if not isinstance(s.current, IfStmtNode):
        pass
        #XXX: raise TemplateError
    stmt = ElseStmtNode(lineno=lineno, col_offset=col_offset)
    # elif
    if s.current.orelse:
        s.current.orelse[-1].orelse.append(stmt)
    # just else
    else:
        s.current.orelse.append(stmt)
    s.push(stmt)

def slot_def(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(SlotDefNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset))

def slot_call(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(SlotCallNode(u''.join([t[1] for t in my_tokens]), 
                       lineno=lineno, col_offset=col_offset))

# base parser (MAIN PARSER)
block_parser = Parser((
    # start is always the start of a new line
    ('start', (
        (TOKEN_TEXT, 'text', push),
        (TOKEN_EXPRESSION_START, 'expr', skip),
        (TOKEN_TAG_ATTR_SET, 'set_attr', skip),
        (TOKEN_TAG_ATTR_APPEND, 'append_attr', skip),
        (TOKEN_TAG_START, 'tag', skip),
        (TOKEN_STATEMENT_FOR, 'for_stmt', push),
        (TOKEN_STATEMENT_IF, 'if_stmt', push),
        (TOKEN_STATEMENT_ELIF, 'elif_stmt', push),
        (TOKEN_STATEMENT_ELSE, 'else_stmt', skip),
        (TOKEN_SLOT_DEF, 'slot_def', push),
        (TOKEN_BASE_TEMPLATE, 'base', skip),
        (TOKEN_STMT_CHAR, 'slot_call', skip),
        (TOKEN_COMMENT, 'comment', skip),
        (TOKEN_BACKSLASH, 'escaped_text', skip),
        (TOKEN_INDENT, 'indent', push_stack),
        (TOKEN_UNINDENT, 'start', pop_stack),
        (TOKEN_NEWLINE, 'start', skip),
        (TOKEN_EOF, 'end', skip),
        (all_tokens, 'text', push),
        )),
    # to prevent multiple indentions in a row
    ('indent', (
        (TOKEN_TEXT, 'text', push),
        (TOKEN_EXPRESSION_START, 'expr', skip),
        (TOKEN_TAG_ATTR_APPEND, 'append_attr', skip),
        (TOKEN_TAG_ATTR_SET, 'set_attr', skip),
        (TOKEN_TAG_START, 'tag', skip),
        (TOKEN_STATEMENT_FOR, 'for_stmt', push),
        (TOKEN_STATEMENT_IF, 'if_stmt', push),
        (TOKEN_STATEMENT_ELIF, 'elif_stmt', push),
        (TOKEN_STATEMENT_ELSE, 'else_stmt', skip),
        (TOKEN_SLOT_DEF, 'slot_def', push),
        (TOKEN_STMT_CHAR, 'slot_call', skip),
        (TOKEN_COMMENT, 'comment', skip),
        (TOKEN_BACKSLASH, 'escaped_text', skip),
        (TOKEN_NEWLINE, 'start', skip),
        (TOKEN_UNINDENT, 'start', pop_stack),
        )),
    ('base', (
        (TOKEN_NEWLINE, 'start', base_template),
        (all_tokens, 'base', push),
        )),
    ('text', (
        (TOKEN_EXPRESSION_START, 'expr', text_value),
        (TOKEN_NEWLINE, 'start', text_value_with_last),
        (all_except(TOKEN_INDENT), 'text', push),
        )),
    ('expr', (
        (TOKEN_EXPRESSION_END, 'text', py_expr),
        (all_tokens, 'expr', push),
        )),
    ('escaped_text', (
        (TOKEN_NEWLINE, 'start', text_value_with_last),
        (all_except(TOKEN_INDENT), 'escaped_text', push),
        )),
    ('tag', (
        (tag_parser, 'start', skip),
        )),
    ('comment', (
        (TOKEN_NEWLINE, 'start', html_comment),
        (all_tokens, 'comment', push),
        )),
    ('set_attr', (
        (TOKEN_TEXT, 'set_attr', push),
        (TOKEN_MINUS, 'set_attr', push),
        (TOKEN_COLON, 'set_attr', push),
        (TOKEN_PARENTHESES_OPEN, 'set_attr_value', tag_attr_name),
        )),
    ('set_attr_value', (
        (attr_data_parser, 'start', set_attr),
        )),
    ('append_attr', (
        (TOKEN_TEXT, 'append_attr', push),
        (TOKEN_MINUS, 'append_attr', push),
        (TOKEN_COLON, 'append_attr', push),
        (TOKEN_PARENTHESES_OPEN, 'append_attr_value', tag_attr_name),
        )),
    ('append_attr_value', (
        (attr_data_parser, 'start', append_attr),
        )),
    ('for_stmt', (
        (TOKEN_NEWLINE, 'start', for_stmt),
        (all_tokens, 'for_stmt', push),
        )),
    ('if_stmt', (
        (TOKEN_NEWLINE, 'start', if_stmt),
        (all_tokens, 'if_stmt', push),
        )),
    ('elif_stmt', (
        (TOKEN_NEWLINE, 'start', elif_stmt),
        (all_tokens, 'elif_stmt', push),
        )),
    ('else_stmt', (
        (TOKEN_NEWLINE, 'start', else_stmt),
        #(all_tokens, 'else_stmt', push),
        )),
    ('slot_def', (
        (TOKEN_NEWLINE, 'start', slot_def),
        (all_tokens, 'slot_def', push),
        )),
    ('slot_call', (
        (TOKEN_NEWLINE, 'start', slot_call),
        (all_tokens, 'slot_call', push),
        )),
))

############# PARSER END

class AstWrapper(object):
    def __init__(self, lineno, col_offset):
        assert lineno is not None and col_offset is not None
        self.lineno = lineno
        self.col_offset = col_offset
    def __getattr__(self, name):
        attr = getattr(ast, name)
        return partial(attr, lineno=self.lineno, col_offset=self.col_offset, ctx=Load())


class MintToPythonTransformer(ast.NodeTransformer):

    def visit_MintTemplate(self, node):
        ast_ = AstWrapper(1,1)
        module = ast_.Module(body=[
            ast_.FunctionDef(name=MAIN_FUNCTION, 
                             body=[], 
                             args=ast_.arguments(args=[], vararg=None, kwargs=None, defaults=[]),
                             decorator_list=[])])
        body = module.body[0].body
        for n in node.body:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    body.append(i)
            else:
                body.append(result)
        return module

    def visit_TextNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        return ast_.Expr(value=ast_.Call(func=ast_.Name(id=DATA),
                                         args=[self.get_value(node, ast_)],
                                         keywords=[], starargs=None, kwargs=None))

    def visit_ExpressionNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        return ast_.Expr(value=ast_.Call(func=ast_.Name(id=DATA),
                                         args=[self.get_value(node, ast_)],
                                         keywords=[], starargs=None, kwargs=None))

    def visit_SetAttrNode(self, node):
        ast_ = AstWrapper(node.attr.lineno, node.attr.col_offset)
        key, value = self.get_value(node.attr, ast_)
        return ast_.Expr(value=ast_.Call(func=ast_.Attribute(value=ast_.Name(id=CURRENT_NODE),
                                                            attr='set'),
                                        args=[key, value],
                                        keywords=[],
                                        starargs=None, kwargs=None))

    def visit_AppendAttrNode(self, node):
        ast_ = AstWrapper(node.attr.lineno, node.attr.col_offset)
        key, value = self.get_value(node.attr, ast_)
        value = ast_.BinOp(
            left=ast_.BoolOp(
                values=[ast_.Call(
                    func=ast_.Attribute(value=ast_.Name(id=CURRENT_NODE),
                                        attr='get'),
                    args=[key],
                    keywords=[],
                    starargs=None, kwargs=None), ast_.Str(s=u'')],
                op=ast.Or()),
            op=ast.Add(), 
            right=value)
        return ast_.Expr(value=ast_.Call(func=ast_.Attribute(value=ast_.Name(id=CURRENT_NODE),
                                                            attr='set'),
                                        args=[key, value],
                                        keywords=[],
                                        starargs=None, kwargs=None))

    def visit_TagNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        name = CURRENT_NODE
        attrs = ast_.Dict(keys=[], values=[])
        for a in node.attrs:
            k, v = self.get_value(a, ast_)
            attrs.keys.append(k)
            attrs.values.append(v)
        nodes = []
        # tag start
        node_start = ast_.Assign(targets=[ast_.Name(id=name, ctx=Store())],
                           value=ast_.Call(func=ast_.Name(id=TAG_START),
                                           args=[ast_.Str(s=escape(node.name)), attrs],
                                           keywords=[], starargs=None, kwargs=None))
        nodes.append(node_start)
        for n in node.body:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    nodes.append(i)
            else:
                nodes.append(result)
        # tag end
        node_end = ast_.Expr(value=ast_.Call(func=ast_.Name(id=TAG_END),
                                             args=[ast_.Str(s=escape(node.name))],
                                             keywords=[], starargs=None, kwargs=None))
        nodes.append(node_end)
        return nodes

    def visit_ForStmtNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        result = []
        expr = node.text[1:]
        if not expr.endswith(':'):
            expr += ':'
        expr += 'pass'
        value = ast.parse(expr).body[0]
        for n in node.body:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    value.body.append(i)
            else:
                value.body.append(result)
        value.lineno = ast_.lineno
        value.col_offset = ast_.col_offset
        return value

    def visit_IfStmtNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        result = []
        expr = node.text[1:]
        if not expr.endswith(':'):
            expr += ':'
        expr += 'pass'
        if expr.startswith('el'):
            expr = expr[2:]
        value = ast.parse(expr).body[0]
        value.body = []
        value.lineno = ast_.lineno
        value.col_offset = ast_.col_offset
        #XXX: if nodes is empty list raise TemplateError
        for n in node.body:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    value.body.append(i)
            else:
                value.body.append(result)
        for n in node.orelse:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    value.orelse.append(i)
            else:
                value.orelse.append(result)
        return value

    def visit_ElseStmtNode(self, node):
        value = []
        for n in node.body:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    value.append(i)
            else:
                value.append(result)
        return value

    def visit_SlotDefNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        result = []
        expr = node.text[1:]
        if not expr.endswith(':'):
            expr += ':'
        expr += 'pass'
        value = ast.parse(expr).body[0]
        value.lineno = ast_.lineno
        value.col_offset = ast_.col_offset
        #XXX: if self.nodes is empty list raise TemplateError
        for n in node.body:
            result = self.visit(n)
            if isinstance(result, (list, tuple)):
                for i in result:
                    value.body.append(i)
            else:
                value.body.append(result)
        return value

    def visit_SlotCallNode(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        expr = node.text
        value = ast.parse(expr).body[0].value
        value.lineno = ast_.lineno
        value.col_offset = ast_.col_offset
        return ast_.Expr(value=ast_.Call(func=ast_.Name(id=DATA),
                                         args=[value], keywords=[]))

    def get_value(self, node, ast_, ctx='tag'):
        if isinstance(node, TextNode):
            return ast_.Str(s=escape(node.text, ctx=ctx))
        elif isinstance(node, ExpressionNode):
            expr = ast.parse(node.text).body[0].value
            return ast_.Call(func=ast_.Name(id=ESCAPE_HELLPER),
                             args=[expr],
                             keywords=[ast.keyword(arg='ctx', value=ast_.Str(s=ctx))], 
                             starargs=None, kwargs=None)
        elif isinstance(node, TagAttrNode):
            key = ast_.Str(s=node.name)
            value = ast_.Str(s=u'')
            nodes = list(node.value)
            if nodes:
                value = ast_.Call(func=ast_.Attribute(value=ast_.Str(s=u''),
                                                      attr='join'),
                                  args=[ast_.Tuple(elts=[self.get_value(n, ast_, ctx='attr') for n in nodes])],
                                  keywords=[], starargs=None, kwargs=None)
            return key, value


class SlotsGetter(ast.NodeTransformer):
    'Node transformer, collects slots'
    def __init__(self):
        self.slots = {}
        self.base = None
    def visit_FunctionDef(self, node):
        ast_ = AstWrapper(node.lineno, node.col_offset)
        new_tree_call = ast_.Assign(targets=[ast_.Tuple(elts=[
                                                         ast_.Name(id=TREE_BUILDER, ctx=Store()),
                                                         ast_.Name(id=TAG_START, ctx=Store()),
                                                         ast_.Name(id=TAG_END, ctx=Store()),
                                                         ast_.Name(id=DATA, ctx=Store())],
                                                       ctx=Store())],
                                    value=ast_.Call(func=ast_.Name(id=TREE_FACTORY),
                                                    args=[],
                                                    keywords=[], starargs=None, kwargs=None))
        tree_to_unicode_call = ast_.Return(value=ast_.Call(func=ast_.Attribute(
                                                value=ast_.Name(id=TREE_BUILDER),
                                                attr='to_unicode'),
                                           args=[],
                                           keywords=[]))
        node.body.insert(0, new_tree_call)
        node.body.append(tree_to_unicode_call)
        if node.name == MAIN_FUNCTION:
            _nones = []
            for n in node.body:
                v = self.visit(n)
                if v is None:
                    _nones.append(n)
            for n in _nones:
                node.body.remove(n)
            return node
        self.slots[node.name] = node
        node.name = 'slot_' + os.urandom(5).encode('hex')
    def visit_BaseTemplate(self, node):
        self.base = node.name


def _correct_inheritance(new_slots, old_slots):
    slots = {}
    for k, value in new_slots.items():
        if k in old_slots:
            name = '__base__'
            old_value = old_slots[k]
            ast_ = AstWrapper(old_value.lineno + 1, old_value.col_offset)
            value.body.insert(0, ast_.Assign(targets=[ast_.Name(id=name, ctx=Store())],
                                             value=ast_.Name(id=old_value.name)))
            del old_slots[k]
            # this slot is overrided in child template
            old_slots[k+'__overrided'] = old_value
        slots[k] = value
    slots.update(old_slots)
    return slots


def get_mint_tree(tokens_stream):
    '''
    This function is wrapper to normal parsers (tag_parser, block_parser, etc.).
    Returns mint tree.
    '''
    smart_stack = RecursiveStack()
    block_parser.parse(tokens_stream, smart_stack)
    return MintTemplate(body=smart_stack.stack)


############# API
class TemplateNotFound(Exception):
    pass


class TreeBuilder(_TreeBuilder):
    'Tree with root element already set'
    def __init__(self, *args, **kwargs):
        _TreeBuilder.__init__(self, *args, **kwargs)
        self.start('root', {})

    def to_unicode(self):
        class dummy: pass
        data = []
        out = dummy()
        out.write = data.append
        # out - fast writable object
        self.end('root')
        root = self.close()
        if root.text:
            out.write(root.text)
        for node in root:
            self._node_to_unicode(out, node)
        if root.tail:
            out.write(root.tail)
        return Markup(u''.join(data))

    def _node_to_unicode(self, out, node):
        #NOTE: all data must be escaped during tree building
        tag = node.tag
        items = node.items()
        selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']
        out.write(u'<' + tag)
        if items:
            items.sort() # lexical order
            for k, v in items:
                out.write(u' %s="%s"' % (k, v))
        if tag in selfclosed:
            out.write(u' />')
        else:
            out.write(u'>')
            if node.text or len(node):
                if node.text:
                    out.write(node.text)
                for n in node:
                    self._node_to_unicode(out, n)
            out.write(u'</' + tag + '>')
            if node.tail:
                out.write(node.tail)


class PprintTreeBuilder(_TreeBuilder):
    'Tree with root element already set'
    def __init__(self, *args, **kwargs):
        _TreeBuilder.__init__(self, *args, **kwargs)
        self.start('root', {})
        self._level = -1

    @property
    def indention(self):
        return self._level > 0 and '  '*self._level or ''

    def to_unicode(self):
        class dummy: pass
        data = []
        out = dummy()
        out.write = data.append
        # out - fast writable object
        self.end('root')
        root = self.close()
        if root.text:
            out.write(self.indent_text(root.text))
            out.write('\n')
        for node in root:
            self._node_to_unicode(out, node)
        if root.tail:
            out.write(self.indent_text(root.tail))
        return Markup(u''.join(data))

    def _node_to_unicode(self, out, node):
        #NOTE: all data must be escaped during tree building
        self.indent()
        tag = node.tag
        items = node.items()
        selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']
        children = list(node)
        text = node.text
        tail = node.tail
        out.write(self.indention)
        out.write(u'<' + tag)
        if items:
            items.sort() # lexical order
            for k, v in items:
                out.write(u' %s="%s"' % (k, v))
        if tag in selfclosed:
            out.write(u' />')
        else:
            out.write(u'>')
            if text:
                if text.endswith('\n'):
                    text = text[:-1]
                self.indent()
                out.write('\n')
                out.write(self.indent_text(text))
                out.write('\n')
                self.unindent()
            if children:
                out.write('\n')
                for n in children:
                    self._node_to_unicode(out, n)

            if children or text:
                out.write(self.indention)
            out.write(u'</' + tag + '>')
            if node.tail:
                out.write('\n')
                tail = node.tail
                if tail.endswith('\n'):
                    tail = tail[:-1]
                out.write(self.indent_text(tail))
        out.write('\n')
        self.unindent()

    def indent_text(self, text):
        return '\n'.join([self.indention+t for t in text.split('\n')])

    def indent(self):
        self._level += 1
    def unindent(self):
        self._level -= 1


def new_tree(pprint):
    def wrapper():
        tree = pprint and PprintTreeBuilder() or TreeBuilder()
        return tree, tree.start, tree.end, tree.data
    return wrapper


class Template(object):

    def __init__(self, source, filename=None, loader=None, globals=None, pprint=False):
        assert source or filename, 'Please provide source code or filename'
        self.source = source
        self.filename = filename if filename else '<string>'
        self._loader = loader
        self.compiled_code = compile(self.tree(), self.filename, 'exec')
        self.globals = globals or {}
        self.pprint = pprint

    def tree(self, slots=None):
        slots = slots or {}
        source = StringIO(self.source) if self.source else open(self.filename, 'r')
        mint_tree = get_mint_tree(tokenizer(source))
        tree = MintToPythonTransformer().visit(mint_tree)
        slots_getter = SlotsGetter()
        slots_getter.visit(tree.body[0])
        _slots, base_template_name = slots_getter.slots, slots_getter.base
        # we do not want to override slot's names,
        # so prefixing existing slots with underscore
        slots = _correct_inheritance(slots, _slots)
        if base_template_name:
            base_template = self._loader.get_template(base_template_name)
            tree = base_template.tree(slots=slots)
        elif slots is not None:
            # insert implementation of slots
            # def slot_bb13e100d5(): ...
            # and insert assings of slots
            # real_slot_name = slot_bb13e100d5
            for k,v in slots.items():
                if not k.endswith('__overrided'):
                    ast_ = AstWrapper(v.lineno, v.col_offset)
                    tree.body.insert(0, ast_.Assign(targets=[ast_.Name(id=k, ctx=Store())],
                                                     value=ast_.Name(id=v.name)))
                tree.body.insert(0, v)
        # tree already has slots definitions and ready to be compiled
        return tree

    def render(self, **kwargs):
        ns = {
            'utils':utils,
            ESCAPE_HELLPER:escape,
            TREE_FACTORY:new_tree(self.pprint),
        }
        ns.update(self.globals)
        ns.update(kwargs)
        exec self.compiled_code in ns
        # execute template main function
        return ns[MAIN_FUNCTION]()

    def slot(self, name, **kwargs):
        ns = {
            'utils':utils,
            ESCAPE_HELLPER:escape,
            TREE_FACTORY:new_tree(self.pprint),
        }
        ns.update(self.globals)
        ns.update(kwargs)
        exec self.compiled_code in ns
        return ns[name]


class Loader(object):

    def __init__(self, *dirs, **kwargs):
        self.dirs = []
        # dirs - list of directories. Order matters
        for d in dirs:
            self.dirs.append(os.path.abspath(d))
        self.cache = kwargs.get('cache', False)
        self._templates_cache = {}
        self.globals = kwargs.get('globals', {})
        self.pprint = kwargs.get('pprint', 0)

    def get_template(self, template):
        if template in self._templates_cache:
            return self._templates_cache[template]
        for dir in self.dirs:
            location = os.path.join(dir, template)
            if os.path.exists(location) and os.path.isfile(location):
                with open(location, 'r') as f:
                    tmpl = Template(source=f.read(), filename=f.name,
                                    loader=self, globals=self.globals, pprint=self.pprint)
                    if self.cache:
                        self._templates_cache[template] = tmpl
                    return tmpl
        raise TemplateNotFound(template)

    def __add__(self, other):
        dirs = self.dirs + other.dirs
        return self.__class__(cache=self.cache, globals=self.globals,*dirs)


#NOTE: Taken from jinja2
class Markup(unicode):

    def __new__(cls, obj=u'', **kwargs):
        if hasattr(obj, '__html__'):
            obj = obj.__html__()
        return super(Markup, cls).__new__(cls, obj, **kwargs)

    def __html__(self):
        return self

    def __add__(self, other):
        if hasattr(other, '__html__') or isinstance(other, basestring):
            return self.__class__(unicode(self) + unicode(escape(other)))
        return NotImplemented

    def __radd__(self, other):
        if hasattr(other, '__html__') or isinstance(other, basestring):
            return self.__class__(unicode(escape(other)) + unicode(self))
        return NotImplemented

    def __mul__(self, num):
        if isinstance(num, (int, long)):
            return self.__class__(unicode.__mul__(self, num))
        return NotImplemented
    __rmul__ = __mul__

    def join(self, seq):
        return self.__class__(unicode.join(self, itertools.imap(escape, seq)))
    join.__doc__ = unicode.join.__doc__

    def split(self, *args, **kwargs):
        return map(self.__class__, unicode.split(self, *args, **kwargs))
    split.__doc__ = unicode.split.__doc__

    def rsplit(self, *args, **kwargs):
        return map(self.__class__, unicode.rsplit(self, *args, **kwargs))
    rsplit.__doc__ = unicode.rsplit.__doc__

    def splitlines(self, *args, **kwargs):
        return map(self.__class__, unicode.splitlines(self, *args, **kwargs))
    splitlines.__doc__ = unicode.splitlines.__doc__

    def __repr__(self):
        return 'Markup(%s)' % super(Markup, self).__repr__()


class utils(object):

    class doctype:
        html_strict = Markup('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                                '"http://www.w3.org/TR/html4/strict.dtd">')
        html_transitional = Markup('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 '
                          'Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">')
        xhtml_strict = Markup('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
                                 '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')
        xhtml_transitional = Markup('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 '
        'Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">')
        html5 = Markup('<!DOCTYPE html>')

    markup = Markup

    @staticmethod
    def loop(iterable):
        return Looper(iterable)

    @staticmethod
    def entity(char):
        return Markup(CHARS_ENTITIES.get(char, char))

    @staticmethod
    def script(src=None, data=None, type='text/javascript'):
        if src:
            return Markup('<script type="%s" src="%s"></script>' % (type, src))
        elif data:
            return Markup('<script type="%s">%s</script>' % (type, data))
        return ''

    @staticmethod
    def scripts(*args, **kwargs):
        result = []
        for name in args:
            result.append(utils.script(name, **kwargs))
        return ''.join(result)

    @staticmethod
    def link(href, rel='stylesheet', type='text/css'):
        return Markup('<link rel="%s" type="%s" href="%s" />' % (rel, type, href))


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

    def visit_Return(self, node):
        self.make_tab()
        self.src.write('return ')
        self.visit(node.value)

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

    def visit_Dict(self, node):
        self.src.write('{')
        total_keys = len(node.keys)
        for i in range(total_keys):
            if i != 0:
                self.src.write(', ')
            self.visit(node.keys[i])
            self.src.write(': ')
            self.visit(node.values[i])
        self.src.write('}')

    def visit_Assign(self, node):
        self.make_tab()
        for i, target in enumerate(node.targets):
            if i != 0:
                self.src.write(', ')
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

    def visit_BoolOp(self, node):
        for i, n in enumerate(node.values):
            self.visit(n)
            if not i:
                self.src.write(' ')
                self.visit(node.op)
                self.src.write(' ')

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
    def visit_Or(self, node):
        self.src.write('or')


def all_files_by_mask(mask):
    for root, dirs, files in os.walk('.'):
        for basename in files:
            if fnmatch.fnmatch(basename, mask):
                filename = os.path.join(root, basename)
                yield filename


def render_templates(*templates, **kw):
    loader = kw['loader']
    for template_name in templates:
        result = loader.get_template(template_name).render()
        if result:
            open(template_name[:-4]+'html', 'w').write(result)


def iter_changed(interval=1):
    mtimes = {}
    while 1:
        for filename in all_files_by_mask('*.mint'):
            try:
                mtime = os.stat(filename).st_mtime
            except OSError:
                continue
            old_time = mtimes.get(filename)
            if old_time is None:
                mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                mtimes[filename] = mtime
                yield filename
        time.sleep(interval)


if __name__ == '__main__':
    import datetime
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-c', '--code', dest='code', action='store_true',
                      default=False,
                      help='Show only python code of compiled template.')
    parser.add_option('-t', '--tokenize', dest='tokenize', action='store_true',
                      default=False,
                      help='Show tokens stream of template.')
    parser.add_option('-r', '--repeat', dest='repeat',
                      default=0, metavar='N', type='int',
                      help='Try to render template N times and display average time result.')
    parser.add_option('-p', '--pprint', dest='pprint', action='store_true',
                      default=False,
                      help='Turn pretty print on.')
    parser.add_option('-m', '--monitor', dest='monitor', action='store_true',
                      default=False,
                      help='Monitor current directory and subdirectories for changes in mint files. '
                           'And render corresponding html files.')
    (options, args) = parser.parse_args()
    loader = Loader('.', pprint=options.pprint)
    if len(args) > 0:
        template_name = args[0]
        template = loader.get_template(template_name)
        if options.code:
            printer = Printer()
            printer.visit(template.tree())
            print printer.src.getvalue()
        elif options.tokenize:
            for t in tokenizer(StringIO(template.source)):
                print t
        else:
            print template.render()
        if options.repeat > 0:
            now = datetime.datetime.now
            results = []
            for i in range(options.repeat):
                start = now()
                template.render()
                results.append(now() - start)
            print 'Total time (%d repeats): ' % options.repeat, reduce(lambda a,b: a+b, results)
            print 'Average:                 ', reduce(lambda a,b: a+b, results)/len(results)
    elif options.monitor:
        curdir = os.path.abspath(os.getcwd())
        try:
            render_templates(*all_files_by_mask('*.mint'), loader=loader)
            print 'Monitoring for file changes...'
            for changed_file in iter_changed():
                print 'Changes in file: ', changed_file, datetime.datetime.now().strftime('%H:%M:%S')
                render_templates(changed_file, loader=loader)
        except KeyboardInterrupt:
            pass
    else:
        print 'Try --help'
