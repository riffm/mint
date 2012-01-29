# -*- coding: utf-8 -*-

import os
import ast
import itertools
from ast import Load, Store
from functools import partial
from xml.etree.ElementTree import TreeBuilder as _TreeBuilder

from .lexer import *
from .nodes import *
from .escape import escape, Markup


# variables names (we do not want to override user variables and vise versa)
TREE_BUILDER = '__MINT_TREE_BUILDER__'
TREE_FACTORY = '__MINT_TREE_FACTORY__'
MAIN_FUNCTION = '__MINT_MAIN__'
TAG_START = '__MINT_TAG_START__'
TAG_END = '__MINT_TAG_END__'
DATA = '__MINT_DATA__'
ESCAPE_HELLPER = '__MINT_ESCAPE__'
CURRENT_NODE = '__MINT_CURRENT_NODE__'


class AstWrapper(object):
    def __init__(self, lineno, col_offset):
        assert lineno is not None and col_offset is not None
        self.lineno = lineno
        self.col_offset = col_offset
    def __getattr__(self, name):
        attr = getattr(ast, name)
        return partial(attr, lineno=self.lineno, col_offset=self.col_offset,
                       ctx=Load())


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


def correct_inheritance(new_slots, old_slots):
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
from .escape import Markup


class TemplateError(Exception): pass
class WrongToken(Exception): pass



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


def get_mint_tree(tokens_stream):
    '''
    This function is wrapper to normal parsers (tag_parser, block_parser, etc.).
    Returns mint tree.
    '''
    smart_stack = RecursiveStack()
    block_parser.parse(tokens_stream, smart_stack)
    return MintTemplate(body=smart_stack.stack)
