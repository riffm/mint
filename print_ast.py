# -*- coding: utf-8 -*-

import ast
from mint import Loader
from tests import Examples
from StringIO import StringIO

class Printer(ast.NodeVisitor):

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
        for i, arg in enumerate(node.args.args):
            if i != 0:
                self.src.write(', ')
            self.visit(arg)
        self._in_args = False
        self.src.write('):\n')
        self._indent += 1
        for n in node.body:
            self.visit(n)
        self._indent -= 1

    def visit_Name(self, node):
        self.src.write(node.id)

    def visit_Str(self, node):
        self.src.write('"%s"' % node.s)

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
    l = Loader('.')
    t = l.get_template(argv[1])
    printer = Printer()
    printer.visit(t.tree)
    print printer.src.getvalue()
