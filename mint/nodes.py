# -*- coding: utf-8 -*-

import ast
from .escape import escape


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
