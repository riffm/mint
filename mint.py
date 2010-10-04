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
import itertools
from os import path
from ast import Load, Store, Param
from StringIO import StringIO
from collections import deque
from xml.etree.ElementTree import TreeBuilder, tostring

logger = logging.getLogger(__name__)

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
        map = fp
        size = map.len
    else:
        map = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
        size = map.size()
    lineno = 0
    pos = 0
    while 1:
        lineno += 1

        # end of file
        if map.tell() == size:
            yield TOKEN_EOF, 'EOF', lineno, 0
            break

        # now we tokinize line by line
        line = map.readline().decode('utf-8')
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
                        yield TOKEN_TEXT, ''.join(last_text), lineno, pos - 1
                        last_text.clear()
                    #if token is TOKEN_COMMENT:
                    #    line=''
                    #    break
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


def indent_tokenizer(tokens_stream, indent=4):
    current_indent = 0
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
        # indenting and unindenting
        if token is TOKEN_NEWLINE:
            yield tok
            next_tok = tokens_stream.next()
            while next_tok[0] is TOKEN_NEWLINE:
                next_tok = tokens_stream.next()
            next_token, next_value, next_lineno, next_pos = next_tok
            if next_token is TOKEN_WHITESPACE:
                ws_count = len(next_value)
                if ws_count >= indent:
                    times = ws_count/indent
                    rest = ws_count % indent
                    range_ = times - current_indent
                    if range_ > 0:
                        # indenting
                        for i in range(range_):
                            yield TOKEN_INDENT, ' '*indent, lineno, pos
                            current_indent += 1
                    elif range_ < 0:
                        # unindenting
                        for i in range(abs(range_)):
                            yield TOKEN_UNINDENT, ' '*indent, lineno, pos
                            current_indent -= 1
                    if rest:
                        yield TOKEN_WHITESPACE, ' '*rest, lineno, pos
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
    return indent_tokenizer(
            base_tokenizer(fileobj))



############# LEXER END

############# NODES
# Theese nodes are additional nodes, which helps to
# optimize AST building

UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES_IN_ATTR = [(k, CHARS_ENTITIES[k]) for k in '<>"']
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))
UNSAFE_CHARS_ENTITIES_IN_ATTR.append(("'",'&#39;'))
UNSAFE_CHARS_ENTITIES_REVERSED = [(v,k) for k,v in UNSAFE_CHARS_ENTITIES]


def escape(obj, ctx='tag'):
    if hasattr(obj, '__html__'):
        if ctx == 'tag':
            return obj.__html__()
        else:
            text = obj.__html__()
            for k, v in UNSAFE_CHARS_ENTITIES_IN_ATTR:
                text = text.replace(k, v)
            return text
    text = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


def unescape(obj):
    text = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES_REVERSED:
        text = text.replace(k, v)
    return text

from functools import partial

_selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']


class AstWrapper(object):
    def __init__(self, lineno, col_offset):
        assert lineno is not None and col_offset is not None
        self.lineno = lineno
        self.col_offset = col_offset
    def __getattr__(self, name):
        attr = getattr(ast, name)
        if not attr:
            raise AttributeError(name)
        return partial(attr, lineno=self.lineno, col_offset=self.col_offset, ctx=Load())



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

# variables names (we do not want to override user variables and vise versa)
TREE_BUILDER = '__MINT_TREE_BUILDER__'
TAG_START = '__MINT_TAG_START__'
TAG_END = '__MINT_TAG_END__'
DATA = '__MINT_DATA__'
UNICODE = '__MINT__UNICODE__'
ESCAPE_HELLPER = '__MINT_ESCAPE__'


# NODES
class Node(object):
    def __repr__(self):
        return '%s' % self.__class__.__name__


class TextNode(Node):
    def __init__(self, text, lineno=None, col_offset=None, ctx='tag'):
        self.text = text
        self.ast_ = AstWrapper(lineno, col_offset)

    def to_ast(self):
        ast_ = self.ast_
        return ast_.Expr(value=ast_.Call(func=ast_.Name(id=DATA),
                                         args=[self.get_value()],
                                         keywords=[], starargs=None, kwargs=None))

    def get_value(self, ctx='tag'):
        return self.ast_.Str(s=escape(self.text, ctx=ctx))

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.text)


class PythonExpressionNode(Node):
    def __init__(self, text, lineno=None, col_offset=None):
        self.text = text.strip()
        self.ast_ = AstWrapper(lineno, col_offset)

    def to_ast(self):
        ast_ = self.ast_
        return ast_.Expr(value=ast_.Call(func=ast_.Name(id=DATA),
                                         args=[self.get_value()],
                                         keywords=[], starargs=None, kwargs=None))

    def get_value(self, ctx='tag'):
        ast_ = self.ast_
        expr = ast.parse(self.text).body[0].value
        return ast_.Call(func=ast_.Name(id=ESCAPE_HELLPER),
                         args=[ast_.Call(func=ast_.Name(id=UNICODE),
                                        args=[expr],
                                        keywords=[], starargs=None, kwargs=None)],
                         keywords=[ast.keyword(arg='ctx', value=ast_.Str(s=ctx))], 
                         starargs=None, kwargs=None)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.text)


class TagAttrNode(Node):
    def __init__(self, name, value=None, lineno=None, col_offset=None):
        self.name = escape(name, ctx='attr')
        self.nodes = value or []
        self.ast_ = AstWrapper(lineno, col_offset)

    def get_value(self):
        ast_ = self.ast_
        key = ast_.Str(s=self.name)
        value = ast_.Str(s=u'')
        nodes = list(self.nodes)
        if nodes:
            value = ast_.Call(func=ast_.Attribute(value=ast_.Str(s=u''),
                                                  attr='join'),
                              args=[ast_.Tuple(elts=[n.get_value(ctx='attr') for n in nodes])],
                              keywords=[], starargs=None, kwargs=None)
        return key, value

    def __repr__(self):
        return '%s(%r, nodes=%r)' % (self.__class__.__name__, self.name, self.nodes)


class TagNode(Node):
    def __init__(self, name, attrs=None, lineno=None, col_offset=None):
        self.name = name
        self.attrs = attrs or []
        self.nodes = []
        self.ast_ = AstWrapper(lineno, col_offset)

    def to_ast(self):
        ast_ = self.ast_
        name = '__node_%s' % id(self)
        attrs = ast_.Dict(keys=[], values=[])
        for a in self.attrs:
            k, v = a.get_value()
            attrs.keys.append(k)
            attrs.values.append(v)
        nodes = []
        # tag start
        node_start = ast_.Assign(targets=[ast_.Name(id=name, ctx=Store())],
                           value=ast_.Call(func=ast_.Name(id=TAG_START),
                                           args=[ast_.Str(s=escape(self.name)), attrs],
                                           keywords=[], starargs=None, kwargs=None))
        nodes.append(node_start)
        for n in self.nodes:
            result = n.to_ast()
            if isinstance(result, (list, tuple)):
                for i in result:
                    nodes.append(i)
            else:
                nodes.append(result)
        # tag end
        node_end = ast_.Expr(value=ast_.Call(func=ast_.Name(id=TAG_END),
                                             args=[ast_.Str(s=escape(self.name))],
                                             keywords=[], starargs=None, kwargs=None))
        nodes.append(node_end)
        return nodes

    def __repr__(self):
        return '%s(%r, attrs=%r, nodes=%r)' % (self.__class__.__name__, self.name, self.attrs, self.nodes)

# NODES END


class RecursiveStack(object):
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
    def __init__(self, states, value_processor=None):
        self.states = dict(states)
        self.value_processor = value_processor

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
                raise WrongToken('[%s] Unexpected token "%s(%s)" at %d line, pos %d' \
                        % (current_state, token, tok_value, lineno, pos))
            # process of new_state
            elif new_state != current_state:
                #print current_state, '%s(%r)' % (token, tok_value), new_state
                if new_state == 'end':
                    callback(tok, stack)
                    break
                current_state = new_state
                variantes = self.states[current_state]
            # state callback
            callback(tok, stack)
            #print 'callback: ', stack
        if self.value_processor:
            self.value_processor(stack)


# utils functions
def get_tokens(s):
    my_tokens = []
    while s.current and isinstance(s.current, (list, tuple)):
        my_tokens.append(s.pop())
    my_tokens.reverse()
    return my_tokens

# Callbacks are functions that takes token and stack
skip = lambda t, s: None
push = lambda t, s: s.push(t)
pop_stack = lambda t, s: s.pop_stack()
push_stack = lambda t, s: s.push_stack(s.current.nodes)


# data
def py_expr(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(PythonExpressionNode(u''.join([t[1] for t in my_tokens]), 
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

attr_data_parser = Parser((
    ('start', (
        (TOKEN_EXPRESSION_START, 'expr', text_value),
        (TOKEN_PARENTHESES_CLOSE, 'end', text_value),
        (all_except(TOKEN_NEWLINE), 'start', push),
        )),
    ('expr', (
        (TOKEN_EXPRESSION_END, 'start', py_expr),
        (all_tokens, 'expr', push),
        )),
))


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


#tag
def tag_name(t, s):
    #if isinstance(s.current, (list, tuple)):
    my_tokens = get_tokens(s)
    if my_tokens:
        lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
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
    attr.nodes = reversed(nodes)

def tag_node(t, s):
    attrs = []
    while isinstance(s.current, TagAttrNode):
        attrs.append(s.pop())
    tag = s.pop()
    # if there were no attrs
    if isinstance(tag, (list, tuple)):
        my_tokens = get_tokens(s)
        my_tokens.append(tag)
        lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
        tag = TagNode(u''.join([t[1] for t in my_tokens]), 
                      lineno=lineno, col_offset=col_offset)
    if attrs:
        tag.attrs = attrs
    s.push(tag)

tag_parser = Parser((
    ('start', (
        (TOKEN_TEXT, 'start', push),
        (TOKEN_MINUS, 'start', push),
        (TOKEN_COLON, 'start', push),
        (TOKEN_DOT, 'attr', tag_name),
        (TOKEN_WHITESPACE, 'end', tag_node),
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
))


def html_comment(t, s):
    my_tokens = get_tokens(s)
    lineno, col_offset = my_tokens[0][2], my_tokens[0][3]
    s.push(TextNode(Markup(u'<!-- %s -->' % u''.join([t[1] for t in my_tokens])), 
                       lineno=lineno, col_offset=col_offset))

block_parser = Parser((
    ('start', (
        (TOKEN_TEXT, 'text', push),
        (TOKEN_EXPRESSION_START, 'expr', skip),
        (TOKEN_TAG_START, 'tag', skip),
        (TOKEN_COMMENT, 'comment', skip),
        (TOKEN_INDENT, 'start', push_stack),
        (TOKEN_UNINDENT, 'start', pop_stack),
        (TOKEN_NEWLINE, 'start', skip),
        (TOKEN_EOF, 'end', skip),
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
    ('tag', (
        (tag_parser, 'start', skip),
        )),
    ('comment', (
        (TOKEN_NEWLINE, 'start', html_comment),
        (all_tokens, 'comment', push),
        )),
))


class MintParser(object):
    def __init__(self, indent=4, slots=None):
        self.indent = indent
        self.slots = slots or {}

    def parse(self, tokens_stream):
        ast_ = AstWrapper(1,0)
        module = ast_.Module(body=[
            ast_.Assign(targets=[ast_.Name(id=TAG_START, ctx=Store())],
                        value=ast_.Attribute(value=ast_.Name(id=TREE_BUILDER), 
                                             attr='start')),
            ast_.Assign(targets=[ast_.Name(id=TAG_END, ctx=Store())],
                        value=ast_.Attribute(value=ast_.Name(id=TREE_BUILDER), 
                                             attr='end')),
            ast_.Assign(targets=[ast_.Name(id=DATA, ctx=Store())],
                        value=ast_.Attribute(value=ast_.Name(id=TREE_BUILDER), 
                                             attr='data')),
            ])
        smart_stack = RecursiveStack()
        block_parser.parse(tokens_stream, smart_stack)
        for item in smart_stack.stack:
            result = item.to_ast()
            if isinstance(result, (list, tuple)):
                for i in result:
                    module.body.append(i)
            else:
                module.body.append(result)
        return module

############# PARSER END


############# API
class TemplateNotFound(Exception):
    pass


class Template(object):

    def __init__(self, sourcefile, cache=True, loader=None):
        self.sourcefile = StringIO(sourcefile) if isinstance(sourcefile, basestring) else sourcefile
        self.filename = '<string>' if isinstance(sourcefile, basestring) else sourcefile.name
        self.need_caching = cache
        # cached compiled code
        self.compiled_code = None
        #self._loader = weakref.proxy(loader) if loader else None
        self._loader = loader

    def tree(self, slots=None):
        parser = MintParser(indent=4, slots=slots)
        tree = parser.parse(tokenizer(self.sourcefile))
        # here we operate with base templates and so on
        return tree

    def compile(self):
        return compile(self.tree(), self.filename, 'exec')

    def render(self, **kwargs):
        if self.need_caching:
            if self.compiled_code:
                code = self.compiled_code
            else:
                code = self.compile()
                self.compiled_code = code
        else:
            code = self.compile()
        ns = {
            'utils':utils,
            UNICODE:unicode,
            ESCAPE_HELLPER:escape,
        }
        builder = TreeBuilder()
        ns[TREE_BUILDER] = builder
        # NOTE: TreeBuilder will ignore first zero level elements
        # if there are any
        builder.start('root', {})
        ns.update(kwargs)
        exec code in ns
        builder.end('root')
        #XXX: this is ugly. to not show root element we slice result
        return self.tostring(builder.close())[6:-7]

    def tostring(self, node):
        # This is updated for html purpose code
        # from xml.etree.ElementTree
        class dummy: pass
        data = []
        out = dummy()
        out.write = data.append
        tag = node.tag
        items = node.items()
        out.write(u'<' + tag)
        if items:
            items.sort() # lexical order
            for k, v in items:
                out.write(u' %s="%s"' % (k, v))
        if node.text or len(node):
            out.write(u'>')
            if node.text:
                # text must be escaped during tree building
                out.write(node.text)
            for n in node:
                out.write(self.tostring(n))
            out.write(u'</' + tag + '>')
        else:
            out.write(u' />')
        if node.tail:
            out.write(node.tail)
        return u''.join(data)



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
    template = Loader('.').get_template(template_name)
    printer = Printer()
    printer.visit(template.tree())
    print printer.src.getvalue()
