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

tokenizer = lambda filename: indent_tokenizer(base_tokenizer(open(filename, 'r')))



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

from functools import partial

_selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']


class AstWrapper(object):
    def __init__(self, lineno, col_offset):
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

# NODES
class Node(object):
    def __repr__(self):
        return '%s' % self.__class__.__name__


class TextNode(Node):
    def __init__(self, text):
        self.text = text
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.text)


class PythonExpressionNode(Node):
    def __init__(self, text):
        self.text = text
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.text)


class TagAttrNode(Node):
    def __init__(self, name, value=None, lineno=None, pos=None):
        self.name = name
        self.nodes = value or []
        self.lineno = lineno
        self.pos = pos
    def __repr__(self):
        return '%s(%r, nodes=%r)' % (self.__class__.__name__, self.name, self.nodes)


class TagNode(Node):
    def __init__(self, name, attrs=None, lineno=None, pos=None):
        self.name = name
        self.attrs = attrs or []
        self.nodes = []
        self.lineno = lineno
        self.pos = pos
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
    while stack.current and isinstance(stack.current, (list, tuple)):
        my_tokens.append(stack.pop())
    return reversed(my_tokens)

# Callbacks are functions that takes token and stack
skip = lambda t, s: None
push = lambda t, s: s.push(t)
pop_stack = lambda t, s: s.pop_stack()
push_stack = lambda t, s: s.push_stack(s.current.nodes)


# data
py_expr = lambda t, s: s.push(PythonExpressionNode(u''.join([t[1] for t in get_tokens(s)])))
data_value = lambda t, s: s
text_value = lambda t, s: s.push(TextNode(u''.join([t[1] for t in get_tokens(s)])))
text_value_with_last = lambda t, s: s.push(t) and s.push(TextNode(u''.join([t[1] for t in get_tokens(s)])))
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
    if isinstance(s.current, (list, tuple)):
        s.push(TagNode(u''.join([t[1] for t in get_tokens(s)])))

tag_attr_name = lambda t, s: s.push(TagAttrNode(u''.join([t[1] for t in get_tokens(s)])))

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
    if isinstance(tag, (list, tuple)):
        tag = TagNode(tag[1], lineno=tag[2], pos=tag[3])
    if attrs:
        tag.attrs = attrs
    s.push(tag)
    if t[0] is not TOKEN_NEWLINE:
        s.push(t)

tag_parser = Parser((
    ('start', (
        (TOKEN_TEXT, 'start', push),
        (TOKEN_MINUS, 'start', push),
        (TOKEN_COLON, 'start', push),
        (TOKEN_DOT, 'attr', tag_name),
        (all_tokens, 'end', tag_node),
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


block_parser = Parser((
    ('start', (
        (TOKEN_TEXT, 'data', push),
        (TOKEN_EXPRESSION_START, 'data', push),
        (TOKEN_TAG_START, 'tag', skip),
        (TOKEN_EOF, 'end', skip),
        )),
    ('data', (
        (data_parser, 'start', data_value),
        )),
    ('tag', (
        (tag_parser, 'start', skip),
        )),
))


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
        builder = TreeBuilder()
        ns[TREE_BUILDER] = builder
        # NOTE: TreeBuilder will ignore first zero level elements
        # if there are any
        builder.start('root', {})
        ns.update(kwargs)
        exec code in ns
        builder.end('root')
        root = builder.close()
        return u''.join([tostring(e) for e in root.getchildren()])


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

    stack = RecursiveStack()
    #tag_parser.parse(tokenizer(template_name), stack)
    block_parser.parse(tokenizer(template_name), stack)
    #for t in tokenizer(template_name):
        #print t
    import pprint
    print stack
