# -*- coding: utf-8 -*-

import htmlentitydefs
import ast
from ast import Load, Store, Param


UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))


def escape(obj):
    if hasattr(obj, '__html__'):
        return obj.__html__()
    text = unicode(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


class TextNode(object):
    '''Simple node, represents text'''

    def __init__(self, value, escaping=True, lineno=None, col_offset=None, level=None):
        #TODO: remove this checking, use Markup instead
        if escaping:
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
        return '%s("%s")' % (self.__class__.__name__, self.value)


class ExprNode(object):
    '''Simple node, represents python expression'''

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        self.lineno = lineno
        self.col_offset = col_offset

    def to_ast(self, writer_name):
        value = ast.Call(func=ast.Name(id='unicode', ctx=Load(), lineno=self.lineno, col_offset=self.col_offset),
                         args=[ast.parse(self.value).body[0].value],
                         keywords=[], starargs=None, kwargs=None,
                         lineno=self.lineno, col_offset=self.col_offset)
        return ast.Expr(value=ast.Call(func=ast.Name(id=writer_name, ctx=Load(), 
                                                     lineno=self.lineno, col_offset=self.col_offset),
                                       args=[value],
                                       keywords=[], starargs=None, kwargs=None,
                                       lineno=self.lineno, col_offset=self.col_offset),
                        lineno=self.lineno, col_offset=self.col_offset)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.value)


class AttrNode(object):

    def __init__(self, name):
        self.name = TextNode(name)
        self.nodes = []

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
        self._attrs_if = {}
        self.level = level

    def set_attr(self, node):
        #TODO: we need to be sure that user did not set same attr
        # twice
        self._attrs.append(node)

    def set_attr_if(self, expr, name, value):
        self._attrs_if[name] = value

    def to_list(self, nodes_list=None):
        if nodes_list is None:
            nodes_list = []

        # open tag
        if self.name:
            nodes_list.append(TextNode(u'<%s' % self.name, escaping=False))
        if self._attrs:
            for attr in self._attrs:
                nodes_list += attr.to_list()
        if self.name in self._selfclosed:
            nodes_list.append(TextNode(u' />', escaping=False))
            if self.nodes:
                raise TemplateError('Tag "%s" can not have childnodes' % self.name)
            return
        else:
            if self.name:
                nodes_list.append(TextNode(u'>', escaping=False))

        # collect other nodes
        for node in self.nodes:
            if isinstance(node, self.__class__):
                node.to_list(nodes_list=nodes_list)
            else:
                nodes_list.append(node)
        # close tag
        if self.name:
            nodes_list.append(TextNode(u'</%s>' % self.name, escaping=False))
        return nodes_list

    def __repr__(self):
        return '%s("%s", level=%r, nodes=%r, attrs=%r)' % (self.__class__.__name__, self.name, self.level,
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
            n.to_list(nodes_list=nodes_list)
        else:
            nodes_list.append(n)
    return nodes_list


def merge(a, b):
    if isinstance(a, TextNode):
        if isinstance(b, TextNode):
            a.value += b.value
            return None
    return b


def merged_nodes(nodes_list):
    '''Returns generator of merged nodes.
    nodes_list - list of simple nodes.'''
    last = None
    for n in nodes_list:
        if last is not None:
            result = merge(last, n)
            if result is None:
                continue
            yield last
            last = result
        else:
            last = n
            continue
    if last is not None:
        yield last
