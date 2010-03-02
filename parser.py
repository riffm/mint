# -*- coding: utf-8 -*-

#from ast import *
import re
import ast
import functools
import weakref
import htmlentitydefs


#TODO
# - Text escaping
# - "IF-ELSE" statement
# - "FOR" statement
# - blocks (inheritance)
# - python code blocks

class TemplateError(Exception):
    pass


class Context(object):

    def __init__(self):
        self.nodes = []

    def render(self, out):
        for node in self.nodes:
            node.render(out)


class Node(object):

    def escape(self, text):
        for k, v in htmlentitydefs.entitydefs.items():
            text = text.replace(v, '&%s;' % k)
        return text


class Tag(Node):

    _selfclosed = ['br', 'hr', 'img', 'meta']

    def __init__(self, tag_name, parent):
        parent.nodes.append(self)
        self.tag_name = tag_name
        self.nodes = []
        self.attrs = []
        self.closed = tag_name in self._selfclosed
        self.text_attr = ''

    def set_attr(self, name, value):
        self.attrs.append((name, value))

    def add_text_attr(self, text):
        self.text_attr += ' %s' % text

    def add_text(self, text):
        TextNode(text, self)

    def render(self, out, indent=0):
        out.write('  '*indent)
        out.write('<%s' % self.tag_name)
        for attr in self.attrs:
            out.write(' %s="%s" ' % attr)
        if self.text_attr:
            out.write(self.text_attr)
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
        out.write('  '*indent)
        out.write('%s\n' % self.escape(self.text))


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
CODE_BLOCK_START = '<%'
CODE_BLOCK_END = '%>'
HTML_TAG_START = '%'
PYTHON_STATEMENT = '@'
COMMENT = '/'


class Parser(object):

    def __init__(self, indent=2):
        self.indent = indent
        self.level = 0
        self.__id = 0
        self.ast = AstWrap(self)
        # keeps all parents nodes
        self.stack = []
        self.lineno = 0
        # ast tree
        self.ctx = self.ast.Module(body=[
            self.ast.Assign(targets=[self.ast._name('_ctx', 'store')],
                            value=self.ast._call(self.ast._name('Context')))
        ])

    def push_context(self, ctx):
        self.level += 1
        self.stack.append(self.ctx)
        self.ctx = ctx

    def pop_context(self):
        self.level -= 1
        self.ctx = self.stack.pop()

    def _push(self, node):
        'Appending ast.Node to current ctx'
        self.ctx.body.append(node)

    def _id(self):
        self.__id += 1
        return self.__id

    @property
    def tree(self):
        return self.stack[0]

    def parse(self, input):
        for i, line in enumerate(input.readlines()):
            line = line.replace('\n', '')
            striped_line = line.strip()
            if striped_line and len(striped_line) > 1 \
            and not striped_line.startswith(COMMENT):
                self.lineno +=1
                self._process_line(line, i)

    def _process_line(self, line, line_number):
        level = self._get_level(line)

        # if line is upper level, we pop context
        if level < self.level:
            for i in range(self.level - level):
                self.pop_context()

        line = line.strip()
        nodes = []
        if line.startswith('%block'):
            return
        if line.startswith('%endblock'):
            return
        elif line.startswith('@for'):
            nodes = self.handle_for(line[1:])
        elif line.startswith('@if'):
            return
        elif line.startswith('@else'):
            return
        elif line.startswith(CODE_BLOCK_START):
            return
        elif line.startswith(CODE_BLOCK_END):
            return
        elif line.startswith(HTML_TAG_START) or line.startswith('.') or line.startswith('#'):
            nodes = self.handle_tag(line)
        else:
            nodes = self.handle_text(line)

        if not nodes:
            raise TemplateError('line %d: %s' % (self.lineno, line))

        # put all nodes to current scope
        for node in nodes:
            self._push(node)
        # first node (function) now is new scope
        self.push_context(nodes[0])

    def _get_level(self, line):
        return (len(line) - len(line.lstrip()))/self.indent

    _tag_re = re.compile(r'''
                          ^%s(?P<name>[a-zA-Z-#._]+)   # tag name
                          ''' % (re.escape(HTML_TAG_START),), re.VERBOSE)
    _tag_attrs_re = re.compile(r'''
                          (%s.*?%s)   # tag attrs (title="some title" href="http://host")
                          ''' % (re.escape('('), re.escape(')')), re.VERBOSE)
    _div_re = re.compile(r'''
                          ^(?P<name>(\.|\#)[a-zA-Z-#.]+)   # div attrs
                          ''', re.VERBOSE)

    def _get_tag_attrs(self, data):
        '''
        parse string representing classes and id
        .class.other-class#id -> ['class', 'other-class'], id
        '''
        classes = []
        tag_id = None
        _classes = ''
        if '#' in data:
            _classes, tag_id = data.split('#')
        else:
            _classes = data
        if _classes:
            classes = _classes.split('.')[1:]
        return classes, tag_id

    def _parse_attrs(self, line):
        '''
        get attrs from string '(attr="value" attr1="value1") some text'
        returns two strings 'attr="value" attr1="value1"' and 'some text'
        '''
        match = self._tag_attrs_re.search(line)
        rest_line = ''
        if match:
            rest_line = line[match.end():].strip()
            return match.groups()[0][1:-1].strip(), rest_line
        return '', line.strip()

    def handle_tag(self, line):
        rest_line = line
        tag_name = 'div'
        tag_attrs = ''
        if self._tag_re.match(line):
            data = self._tag_re.match(line).groupdict('name')
            name = data['name']
            if '.' in name:
                tag_name = name.split('.')[0]
                tag_attrs = name[len(tag_name):]
            elif '#' in name:
                tag_name = name.split('#')[0]
                tag_attrs = name[len(tag_name):]
            else:
                tag_name = name
            rest_line = line[len(tag_name)+len(tag_attrs)+1:]
        elif self._div_re.match(line):
            data = self._div_re.match(line).groupdict('name')
            tag_attrs = data['name']
            rest_line = line[len(tag_attrs):]
        else:
            raise TemplateError('line %d: %s' % (self.lineno, line))
        # get classes list and id
        classes, tag_id = self._get_tag_attrs(tag_attrs)

        # Here we got tag name and optional classes of tag and id.
        # Now we look at other attrs of tag
        other_attrs, rest_line = self._parse_attrs(rest_line)
        #print other_attrs, rest_line

        # if we are in function, parent name is - 'node', else 'None'
        if filter(lambda p: type(p) is ast.FunctionDef, self.stack + [self.ctx]):
            parent = 'node'
        else:
            parent = '_ctx'

        # Parent value name node
        parent = self.ast.Name(id=parent, ctx=ast.Load())

        _func_name = '_tag_%d' % self._id()

        # def _tag_NUM(parent):
        #     node = Tag('....', parent)
        _function = self.ast.FunctionDef(
            name=_func_name,
            args=self.ast.arguments(
                args = [self.ast._name('parent', ctx='param')],
                defaults=[]
            ),
            body=[
                self.ast.Assign(
                    targets=[self.ast._name('node', 'store')],
                    value=self.ast._call(
                        self.ast._name('Tag'),
                        args=[
                            self.ast.Str(tag_name),
                            self.ast._name('parent')
                        ]
                    )
                )
            ],
            decorator_list=[]
        )
        # node.set_attr('class', '.....')
        if classes:
            _function.body.append(
                self.ast.Expr(
                    value = self.ast._call(
                        self.ast.Attribute(
                            value=self.ast._name('node'),
                            attr='set_attr',
                            ctx=ast.Load()
                        ),
                        args=[self.ast.Str('class'), self.ast.Str(' '.join(classes))]
                    )
                )
            )
        # node.set_attr('id', '....')
        if tag_id:
            _function.body.append(
                self.ast.Expr(
                    value = self.ast._call(
                        self.ast.Attribute(
                            value=self.ast._name('node'),
                            attr='set_attr',
                            ctx=ast.Load()
                        ),
                        args=[self.ast.Str('id'), self.ast.Str(tag_id)]
                    )
                )
            )
        # node.add_text_attr('....')
        if other_attrs:
            _node = self._get_textnode(other_attrs)
            _function.body.append(
                self.ast.Expr(
                    value = self.ast._call(
                        self.ast.Attribute(
                            value=self.ast._name('node'),
                            attr='add_text_attr',
                            ctx=ast.Load()
                        ),
                        args=[_node]
                    )
                )
            )
        # node.add_text('...')
        if rest_line:
            _node = self._get_textnode(rest_line)
            _function.body.append(
                self.ast.Expr(
                    value = self.ast._call(
                        self.ast.Attribute(
                            value=self.ast._name('node'),
                            attr='add_text',
                            ctx=ast.Load()
                        ),
                        args=[_node]
                    )
                )
            )

        # _tag_NUMBER(parent)
        _function_call = self.ast.Expr(
            value=self.ast._call(
                self.ast.Name(id=_func_name, ctx=ast.Load()),
                args=[parent]
            )
        )
        return _function, _function_call

    def handle_text(self, line):
        # if we are in function, parent name is - 'node', else '_ctx'
        if filter(lambda p: type(p) is ast.FunctionDef, self.stack + [self.ctx]):
            parent = 'node'
        else:
            parent = '_ctx'

        # Parent value name node
        parent = self.ast.Name(id=parent, ctx=ast.Load())

        _func_name = '_text_%d' % self._id()

        _text_node = self._get_textnode(line)

        _function = self.ast.FunctionDef(
            name=_func_name,
            args=self.ast.arguments(
                args = [self.ast._name('parent', ctx='param')],
                defaults=[]
            ),
            body=[
                self.ast.Assign(
                    targets=[self.ast._name('node', 'store')],
                    value=self.ast._call(
                        self.ast._name('TextNode'),
                        args=[
                            _text_node,
                            self.ast._name('parent')
                        ]
                    )
                )
            ],
            decorator_list=[]
        )
        _function_call = self.ast.Expr(
            value=self.ast._call(
                self.ast.Name(id=_func_name, ctx=ast.Load()),
                args=[parent]
            )
        )
        return _function, _function_call

    _text_inline_python = re.compile(r'''
                          (%s.*?%s)   # inline python expressions, i.e. {{ expr }}
                          ''' % (re.escape(EXPR_TAG_START), re.escape(EXPR_TAG_END)), re.VERBOSE)

    def _get_textnode(self, line):
        '''
        Returns ast with expr, finds inline code blocks and
        replace them with result of code execution
        '''
        # list of parsed inline code blocks
        expr_list = []
        for match in self._text_inline_python.finditer(line):
            value = match.groups()[0][2:-2].strip()
            length = match.end() - match.start()
            line = line.replace(match.groups()[0], '%s', 1)
            expr = ast.parse(value).body[0].value
            expr_list.append(expr)
        if expr_list:
            return self.ast.BinOp(
                    left=self.ast.Str(line),
                    op=self.ast.Mod(),
                    right=self.ast.Tuple(elts=expr_list, ctx=ast.Load())
                )
        return self.ast.Str(line)

    def handle_for(self, line):
        if line[-1] != ':':
            line += ': pass'
        else:
            line += ' pass'
        _tree = ast.parse(line)
        _tree.body[0].body = []
        return [_tree.body[0]]


if __name__ == '__main__':
    from sys import argv, stdout
    input = open(argv[1], 'r')
    parser = Parser()
    parser.parse(input)
    tree = parser.tree
    data = {
        'a':'THIS IS A<`^$#&',
        'b':False,
        'c':'THIS IS C',
    }
    ns = {
        'Context':Context,
        'Tag':Tag,
        'TextNode':TextNode,
        '__builtins__':__builtins__,
    }
    ns.update(data)
    exec compile(tree, '<string>', 'exec') in ns
    ns['_ctx'].render(stdout)
