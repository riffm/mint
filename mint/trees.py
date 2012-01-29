# -*- coding: utf-8 -*-

import os
import ast
from ast import Load, Store
from functools import partial
from xml.etree.ElementTree import TreeBuilder as _TreeBuilder

from .escape import escape, Markup
from .nodes import TagAttrNode, ExpressionNode, TextNode


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
