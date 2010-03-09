# -*- coding: utf-8 -*-

import re
import ast
import functools
import weakref
import htmlentitydefs


#TODO
# + Text escaping
# + "IF-ELIF-ELSE" statement
# - "IF-ELIF-ELSE" templates error handling
# + "FOR" statement
# - blocks (inheritance)
# + python variables (i.e. !a = 'hello')
# + '%' chars escaping in strings

class TemplateError(Exception):
    pass


class GrandNode(object):

    def __init__(self):
        self.nodes = []

    def render(self, out):
        for node in self.nodes:
            node.render(out)

UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))


def escape(obj):
    text = str(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


class Node(object):
    pass


class Tag(Node):

    _selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']

    def __init__(self, tag_name, parent):
        parent.nodes.append(self)
        self.tag_name = tag_name
        self.nodes = []
        self.attrs = []
        self.closed = tag_name in self._selfclosed

    def set_attr(self, name, value):
        self.attrs.append((name, value))

    def render(self, out, indent=0):
        out.write('  '*indent)
        out.write('<%s' % self.tag_name)
        for item in self.attrs:
            out.write(' %s="%s"' % item )
        if self.closed:
            out.write('/>\n')
            return
        else:
            out.write('>\n')
        for node in self.nodes:
            node.render(out, indent=indent+1)
        out.write('  '*indent)
        out.write('</%s>\n' % self.tag_name)


class TextNode(Node):

    def __init__(self, text, parent):
        parent.nodes.append(self)
        self.text = text

    def render(self, out, indent=0):
        out.write('%s\n' % self.text)


class AstWrap(object):

    def __init__(self, owner):
        self.owner = weakref.proxy(owner)

    def __getattr__(self, name):
        return functools.partial(getattr(ast, name),
                                 col_offset=0,
                                 lineno=self.owner.lineno)

    def _name(self, id, ctx='load'):
        if ctx == 'load':
            ctx = ast.Load()
        elif ctx == 'store':
            ctx = ast.Store()
        elif ctx == 'param':
            ctx = ast.Param()
        else:
            raise RuntimeError('unknown ctx %r' % ctx)
        return self.Name(id=id, ctx=ctx)

    def _call(self, fn, args=None, kwargs=None):
        if not args:
            args = []
        return self.Call(func=fn, args=args, keywords=[],
                         starargs=None, kwargs=kwargs)


# Some usefull constants
EXPR_TAG_START = '{{'
EXPR_TAG_END = '}}'
STMT_IF = '!if'
STMT_ELIF = '!elif'
STMT_ELSE = '!else'
STMT_FOR = '!for'
PYTHON_VARIABLE_START = '!'
SLOT_DEF = '!def '
HTML_TAG_START = '<'
COMMENT = '#'
ESCAPE_CHAR = '\\'
ATTR_CHAR = ':'

# re
_tag_re = re.compile(r'''
                      ^%s\w+$   # tag name
                      ''' % (re.escape(HTML_TAG_START),), re.VERBOSE)
_attr_re = re.compile(r'''
                      ^:\w+\s+
                      ''', re.VERBOSE)
_text_inline_python = re.compile(r'''
                      (%s.*?%s)   # inline python expressions, i.e. {{ expr }}
                      ''' % (re.escape(EXPR_TAG_START), re.escape(EXPR_TAG_END)), re.VERBOSE)
_python_variable = re.compile(r'''
                      ^%s\s*[1-9_a-zA-Z, ]+\s*=
                      ''' % re.escape(PYTHON_VARIABLE_START), re.VERBOSE)
_slot_def = re.compile(r'''
                      ^%sdef\s+(?P<name>[a-zA-Z_]{1}[a-zA-Z1-9_]*)\(
                      ''' % re.escape(PYTHON_VARIABLE_START), re.VERBOSE)
_slot_call = re.compile(r'''
                      ^%s(?P<name>[a-zA-Z_]{1}[a-zA-Z1-9_]*)\(
                      ''' % re.escape(PYTHON_VARIABLE_START), re.VERBOSE)

# Variable's names for generated code
CTX = '__JAM_CTX__'
GRAND_NODE = '__JAM_GRAND_NODE'
TAG_NODE_CLASS = '__JAM_TAG_NODE'
TEXT_NODE_CLASS = '__JAM_TEXT_NODE'
ESCAPE_HELLPER = '__JAM_TEXT_ESCAPE'


class Parser(object):

    def __init__(self, indent=2):
        self.indent = indent
        self.__id = 0
        self.ast = AstWrap(self)
        # parent nodes stack
        self.stack = []
        # current tree line number
        self.lineno = 1
        # final module, which stores all prepaired nodes
        self.module = self.ast.Module(body=[
            self.ast.Assign(targets=[self.ast._name(CTX, 'store')],
                            value=self.ast._call(self.ast._name(GRAND_NODE)))
        ])
        # current scope
        self.ctx = self.module.body
        # keeps track of all inline python expressions line numbers
        self._associative_lines = {}
        # indicates if we are in text block
        self.in_text_block = False
        self._text_block = []
        # if elif else
        self._if_blocks = []
        self.slots = {}

    def push_stack(self, ctx):
        '''
        ctx - scope (list actualy)
        '''
        self.stack.append(self.ctx)
        self.ctx = ctx

    def pop_stack(self):
        self.ctx = self.stack.pop()

    @property
    def level(self):
        return len(self.stack)

    def _id(self):
        self.__id += 1
        return self.__id

    @property
    def tree(self):
        if self.slots:
            for slot in self.slots.values():
                self.module.body.append(slot)
        return self.module

    def parse(self, input):
        '''
        input - file like object
        '''
        lines = input.readlines()
        total_lines = len(lines)
        i = 0
        while i < total_lines:
            line = lines[i]
            line = line.replace('\n', '')
            striped_line = line.strip()
            self.lineno += 1
            if striped_line and not striped_line.startswith(COMMENT):
                line_type = self.get_line_type(striped_line)
                # if we are in code block or in text block
                if self.need_next_line(line_type, line):
                    i += 1
                    continue

                # if line is upper level, we pop context
                level = self._get_level(line)
                if level < self.level:
                    for y in range(self.level - level):
                        self.pop_stack()

                # if-elif-else, slot are special cases
                if self.python_statement(line_type, line):
                    i += 1
                    continue
                # reset internal buffers
                self.reset()
                if hasattr(self, 'handle_'+line_type):
                    nodes = getattr(self, 'handle_'+line_type)(striped_line)
                    self._process_nodes(nodes)
                else:
                    print 'unknown type: %s' % line_type
            i += 1
        if self._text_block:
            self.handle_text(self._text_block)
        del lines

    def reset(self):
        self.in_text_block = False
        self._text_block = []

    def get_line_type(self, line):
        if line.startswith(STMT_FOR):
            return 'for'
        elif _attr_re.match(line):
            return 'attr'
        elif line.startswith(STMT_IF):
            return 'if'
        elif line.startswith(STMT_ELIF):
            return 'elif'
        elif line.startswith(STMT_ELSE):
            return 'else'
        elif _python_variable.match(line):
            return 'set'
        elif line.startswith(SLOT_DEF):
            return 'slot'
        elif line.startswith(PYTHON_VARIABLE_START):
            # I guess it is a slot call
            return 'slotcall'
        elif _tag_re.match(line):
            return 'tag'
        else:
            return 'text'

    def need_next_line(self, line_type, line):
        if line_type == 'text':
            self.in_text_block = True
            self._text_block.append(line)
            return True
        # we must process all text lines stored
        elif self._text_block:
            self.handle_text(self._text_block)
            self._text_block = []
        elif line_type in ('attr', 'set'):
            getattr(self, 'handle_'+line_type)(line.strip())
            return True
        return False

    def python_statement(self, line_type, line):
        if line_type in ('if', 'elif', 'else', 'slot', 'slotcall'):
            getattr(self, 'handle_'+line_type)(line.strip())
            return True
        return False

    def _process_nodes(self, nodes):
        # put all nodes to current scope
        for node in nodes:
            self.ctx.append(node)
        # first node (function) now is new scope
        self.push_stack(nodes[0].body)

    def _get_level(self, line):
        return (len(line) - len(line.lstrip()))/self.indent

    def handle_tag(self, line):
        tag_name = line[1:]
        # if we are in function, parent name is - 'node', else 'None'
        if self.level > 0:
            parent = 'node'
        else:
            parent = CTX

        # Parent value name node
        parent = self.ast.Name(id=parent, ctx=ast.Load())

        _func_name = '_tag_%d' % self._id()

        # def _tag_NUM(parent):
        #     node = Tag('....', parent)
        _function = self.ast.FunctionDef(
            name=_func_name,
            args=self.ast.arguments(
                args = [self.ast._name('parent', ctx='param')],
                defaults=[]),
            body=[
                self.ast.Assign(
                    targets=[self.ast._name('node', 'store')],
                    value=self.ast._call(
                        self.ast._name(TAG_NODE_CLASS),
                        args=[
                            self.ast.Str(tag_name),
                            self.ast._name('parent')]))],
            decorator_list=[])

        # _tag_NUMBER(parent)
        _function_call = self.ast.Expr(
            value=self.ast._call(
                self.ast.Name(id=_func_name, ctx=ast.Load()),
                args=[parent]))
        return _function, _function_call

    def handle_text(self, text_block):
        # if we are in function, parent name is - 'node', else '_ctx'
        if self.level > 0:
            parent = 'node'
        else:
            parent = CTX

        line = '\n'.join(text_block)

        # Parent value name node
        parent = self.ast.Name(id=parent, ctx=ast.Load())

        _text_node = self._get_textnode(line)

        text_node = self.ast.Assign(
            targets=[self.ast._name('textnode', 'store')],
            value=self.ast._call(
                self.ast._name(TEXT_NODE_CLASS),
                args=[_text_node, parent]))
        self.ctx.append(text_node)

    def handle_attr(self, line):
        line = line[1:]
        if self.level < 1:
            raise TemplateError('You can not set attributes at zero level: line %d' % self.lineno)

        name = line
        other_content = ''
        if ' ' in line:
            name, other_content = line.split(' ',1)
        _text_node = self._get_textnode(other_content)

        text_node = self.ast.Expr(
            value = self.ast._call(
                self.ast.Attribute(
                    value=self.ast._name('node'),
                    attr='set_attr',
                    ctx=ast.Load()),
                args=[self.ast.Str(name), _text_node]))
        self.ctx.append(text_node)

    def _get_textnode(self, line):
        '''
        Returns ast with expr, finds inline code blocks and
        replace them with result of code execution
        '''
        # list of parsed inline code blocks
        expr_list = []
        constructed_str = ''
        last_match_end = 0
        for match in _text_inline_python.finditer(line):
            value = match.groups()[0][2:-2].strip()
            constructed_str += line[last_match_end:match.start()].replace('%', '%%')
            constructed_str += '%s'
            last_match_end = match.end()
            expr = ast.parse(value).body[0].value
            expr_list.append(
                self.ast._call(self.ast._name(ESCAPE_HELLPER), args=[expr])
            )
        # append rest of line
        if last_match_end < len(line):
            constructed_str += line[last_match_end:]
        if expr_list:
            _operator = self.ast.BinOp(
                    left=self.ast.Str(constructed_str),
                    op=self.ast.Mod(),
                    right=self.ast.Tuple(elts=expr_list, ctx=ast.Load())
                )
            return _operator
        return self.ast.Str(line)

    def handle_set(self, line):
        line = line[1:]
        set = ast.parse(line).body[0]
        self.ctx.append(set)

    def handle_slot(self, line):
        m = _slot_def.match(line)
        if m:
            slot_name = m.groupdict()['name']
            if line[-1] == ':':
                line += ' pass'
            else:
                line += ': pass'
            slot_tree = ast.parse(line[1:]).body[0]
            slot_tree.body = []
            self.slots[slot_name] = slot_tree
            self.push_stack(slot_tree.body)
        else:
            raise TemplateError('Syntax error: %d: %s' % (self.lineno, line))

    def handle_slotcall(self, line):
        m = _slot_call.match(line)
        if m:
            slotname = m.groupdict()['name']
            # TODO: raise correct exception when slot is absent
            slotdef = self.slots[slotname]
            slotcall = ast.parse(line[1:]).body[0]
            # if we are in function, parent name is - 'node', else 'None'
            if self.level > 0:
                parent = 'node'
            else:
                parent = CTX

            # Parent value name node
            parent = self.ast.Name(id=parent, ctx=ast.Load())

            _func_name = '_slot_%d' % self._id()

            # def _slot_NUM(parent):
            #     def slotname(*slotargs, **slotkwargs):
            #         ...
            #     slotname(1,'two',a)
            _function = self.ast.FunctionDef(
                name=_func_name,
                args=self.ast.arguments(
                    args = [self.ast._name('parent', ctx='param')],
                    defaults=[]),
                body=[
                    self.ast.Assign(targets=[self.ast._name('node', 'store')],
                                    value=self.ast._name('parent')),
                    slotdef, slotcall],
                decorator_list=[])

            # _slot_NUM(node)
            _function_call = self.ast.Expr(
                value=self.ast._call(
                    self.ast.Name(id=_func_name, ctx=ast.Load()),
                    args=[parent]))
            self.ctx.append(_function)
            self.ctx.append(_function_call)
        else:
            raise TemplateError('Syntax error: %d: %s' % (self.lineno, line))


    def handle_for(self, line):
        line = line[1:]
        if line[-1] != ':':
            line += ': pass'
        else:
            line += ' pass'
        _tree = ast.parse(line)
        _tree.body[0].body = []
        return [_tree.body[0]]

    def handle_if(self, line):
        line = line[1:]
        if line[-1] == ':':
            line = line + ' pass'
        else:
            line = line + ': pass'
        if_node = ast.parse(line).body[0]
        if_node.body = []
        self._if_blocks.append(if_node)

        self.ctx.append(if_node)
        self.push_stack(if_node.body)

    def handle_elif(self, line):
        line = line[3:]
        if line[-1] == ':':
            line = line + ' pass'
        else:
            line = line + ': pass'
        if_node = ast.parse(line).body[0]
        if_node.body = []
        self._if_blocks[-1].orelse.append(if_node)
        self._if_blocks.append(if_node)
        self.push_stack(if_node.body)

    def handle_else(self, line):
        last_if = self._if_blocks.pop()
        self.push_stack(last_if.orelse)


if __name__ == '__main__':
    import sys
    import traceback
    from sys import argv, stdout
    input = open(argv[1], 'r')
    parser = Parser(indent=4)
    parser.parse(input)
    tree = parser.tree
    #print ast.dump(tree)
    data = {
        'a':'THIS IS A<`^$#&',
        'b':False,
        'c':'THIS IS C',
        'url_for_static':lambda s: s,
    }
    ns = {
        GRAND_NODE:GrandNode,
        TAG_NODE_CLASS:Tag,
        TEXT_NODE_CLASS:TextNode,
        ESCAPE_HELLPER:escape,
        '__builtins__':__builtins__,
    }
    ns.update(data)
    #TODO: divide compiling process exceptions from 
    #      exceptions of execution
    compiled_souces = compile(tree, argv[1], 'exec')
    exec compiled_souces in ns
    ns[CTX].render(stdout)
