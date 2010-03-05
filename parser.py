# -*- coding: utf-8 -*-

import re
import ast
import functools
import weakref
import htmlentitydefs


#TODO
# + Text escaping
# - filters
# + "IF-ELIF-ELSE" statement
# - "IF-ELIF-ELSE" templates error handling
# + "FOR" statement
# - blocks (inheritance)
# - python code blocks

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

    _selfclosed = ['br', 'hr', 'img', 'meta']

    def __init__(self, tag_name, parent):
        parent.nodes.append(self)
        self.tag_name = tag_name
        self.nodes = []
        self.attrs = {}
        self.classes = []
        self.id = None
        self.closed = tag_name in self._selfclosed

    def set_attr(self, name, value):
        if name == 'id':
            self.id = value
        elif name == 'class':
            self.classes.append(value.strip())
        else:
            self.attrs[name] = value

    def add_text(self, text):
        TextNode(text, self)

    def render(self, out, indent=0):
        out.write('  '*indent)
        out.write('<%s' % self.tag_name)
        if self.id is not None:
            out.write(' id="%s"' % self.id)
        if self.classes:
            out.write(' class="%s" ' % ' '.join(self.classes))
        for item in self.attrs.items():
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
        out.write('  '*indent)
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
CODE_BLOCK_START = '<%'
CODE_BLOCK_END = '%>'
STMT_IF = '@if'
STMT_ELIF = '@elif'
STMT_ELSE = '@else'
HTML_TAG_START = '%'
PYTHON_STATEMENT = '@'
COMMENT = '/'

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
        # current line number in template
        self._current_line_number = 0
        # final module, which stores all prepaired nodes
        self.module = self.ast.Module(body=[
            self.ast.Assign(targets=[self.ast._name(CTX, 'store')],
                            value=self.ast._call(self.ast._name(GRAND_NODE)))
        ])
        # current scope
        self.ctx = self.module.body
        # keeps track of all inline python expressions line numbers
        self._associative_lines = {}
        # indicates if we are in code or text block
        self.in_code_block = False
        self._code_block = []
        self.in_text_block = False
        self._text_block = []
        # if elif else
        self._if_blocks = []

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
            self._current_line_number += 1
            if striped_line and len(striped_line) > 1 \
            and not striped_line.startswith(COMMENT):
                line_type = self.get_line_type(striped_line)
                # if we are in code block or in text block
                if self.need_next_line(line_type, line):
                    i += 1
                    continue
                if self.if_node(line_type, line):
                    i += 1
                    continue
                # reset internal buffers
                self.reset()
                if hasattr(self, 'handle_'+line_type):
                    nodes = getattr(self, 'handle_'+line_type)(striped_line)
                    level = self._get_level(line)
                    self._process_nodes(nodes, level)
                else:
                    print 'unknown type: %s' % line_type
            i += 1
        del lines

    def reset(self):
        self.in_code_block = False
        self.in_text_block = False
        self._code_block = []
        self._text_block = []

    def get_line_type(self, line):
        if line.startswith('%block'):
            return 'block'
        if line.startswith('%endblock'):
            return 'endblock'
        elif line.startswith('@for'):
            return 'for'
        elif line.startswith(STMT_IF):
            return 'if'
        elif line.startswith(STMT_ELIF):
            return 'elif'
        elif line.startswith(STMT_ELSE):
            return 'else'
        elif line.startswith(CODE_BLOCK_START):
            return 'codeblock'
        elif line.startswith(CODE_BLOCK_END):
            return 'endcodeblock'
        elif line.startswith(HTML_TAG_START) or line.startswith('.') or line.startswith('#'):
            return 'tag'
        else:
            return 'text'

    def need_next_line(self, line_type, line):
        if line_type == 'codeblock':
            self.in_code_block = True
            return True
        if line_type == 'endcodeblock':
            # if line is upper level, we pop context
            level = self._get_level(line)
            if level < self.level:
                for i in range(self.level - level):
                    self.pop_stack()
            assert self.in_code_block, 'line %d: %s' % (self._current_line_number,
                                                        line)
            # process code stored block
            self.handle_codeblock(self._code_block)
            return True
        if line_type == 'text':
            self.in_text_block = True
            if self.in_code_block:
                self._code_block.append(line)
            else:
                self._text_block.append(line)
            return True
        # this line is not code block or text
        # we must process all text lines stored
        if self._text_block:
            self.handle_text(self._text_block)
            self._text_block = []
        # Python comment comes here (i.e. # comment text)
        #if self.in_code_block:
            #self._code_block.append(line)
            #return True
        return False

    def if_node(self, line_type, line):
        if line_type in ('if', 'elif', 'else'):
            level = self._get_level(line)
            # if line is upper level, we pop context
            if level < self.level:
                for i in range(self.level - level):
                    self.pop_stack()
            getattr(self, 'handle_'+line_type)(line.strip())
            return True
        return False

    def _process_nodes(self, nodes, level):
        # if line is upper level, we pop context
        if level < self.level:
            for i in range(self.level - level):
                self.pop_stack()

        # put all nodes to current scope
        for node in nodes:
            self.ctx.append(node)
        # first node (function) now is new scope
        self.push_stack(nodes[0].body)

    def _get_level(self, line):
        return (len(line) - len(line.lstrip()))/self.indent

    _tag_re = re.compile(r'''
                          ^%s(?P<name>[a-zA-Z-#._]+)   # tag name
                          ''' % (re.escape(HTML_TAG_START),), re.VERBOSE)
    _tag_attrs_re = re.compile(r'''
                          ^(%s.*?%s)   # tag attrs (title="some title" href="http://host")
                          ''' % (re.escape('('), re.escape(')')), re.VERBOSE)
    _div_re = re.compile(r'''
                          ^(?P<name>(\.|\#)[a-zA-Z-#.]+)   # div attrs
                          ''', re.VERBOSE)
    _attrs_list_re = re.compile(r'''
                          (\w+=".*?")
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

    def _split_attrs(self, line):
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

    def _parse_attrs(self, line):
        '''
        Get attrs and values from string 'attr="value" attr1="value1"'.
        Returns dict
        '''
        result = {}
        for m in self._attrs_list_re.finditer(line):
            key, value = m.groups()[0].split('=', 1)
            result[key] = value[1:-1]
        return result

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
        other_attrs, rest_line = self._split_attrs(rest_line)
        attrs_dict = self._parse_attrs(other_attrs)
        #print other_attrs, rest_line

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
                defaults=[]
            ),
            body=[
                self.ast.Assign(
                    targets=[self.ast._name('node', 'store')],
                    value=self.ast._call(
                        self.ast._name(TAG_NODE_CLASS),
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
            for cl in classes:
                _function.body.append(
                    self.ast.Expr(
                        value = self.ast._call(
                            self.ast.Attribute(
                                value=self.ast._name('node'),
                                attr='set_attr',
                                ctx=ast.Load()
                            ),
                            args=[self.ast.Str('class'), self.ast.Str(cl)]
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
                        args=[self.ast.Str('id'), self.ast.Str(tag_id)]))
            )
        # node.add_text_attr('....')
        if attrs_dict:
            for k, v in attrs_dict.items():
                _node = self._get_textnode(v)
                _function.body.append(
                    self.ast.Expr(
                        value = self.ast._call(
                            self.ast.Attribute(
                                value=self.ast._name('node'),
                                attr='set_attr',
                                ctx=ast.Load()),
                            args=[self.ast.Str(k), _node]))
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
                            ctx=ast.Load()),
                        args=[_node]))
            )

        # _tag_NUMBER(parent)
        _function_call = self.ast.Expr(
            value=self.ast._call(
                self.ast.Name(id=_func_name, ctx=ast.Load()),
                args=[parent]
            )
        )
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
                args=[
                    _text_node,
                    parent
                ]
            )
        )
        self.ctx.append(text_node)

    _text_inline_python = re.compile(r'''
                          (%s.*?%s)   # inline python expressions, i.e. {{ expr }}
                          ''' % (re.escape(EXPR_TAG_START), re.escape(EXPR_TAG_END)), re.VERBOSE)

    def _get_textnode(self, line):
        '''
        Returns ast with expr, finds inline code blocks and
        replace them with result of code execution
        '''
        # list of parsed inline code blocks
        old_line = line
        expr_list = []
        for match in self._text_inline_python.finditer(line):
            value = match.groups()[0][2:-2].strip()
            length = match.end() - match.start()
            line = line.replace(match.groups()[0], '%s', 1)
            expr = ast.parse(value).body[0].value
            expr_list.append(
                self.ast._call(self.ast._name(ESCAPE_HELLPER), args=[expr])
            )
        if expr_list:
            _operator = self.ast.BinOp(
                    left=self.ast.Str(line),
                    op=self.ast.Mod(),
                    right=self.ast.Tuple(elts=expr_list, ctx=ast.Load())
                )
            self._associative_lines[_operator.lineno] = (self._current_line_number, old_line)
            return _operator
        return self.ast.Str(line)

    def handle_codeblock(self, codeblock):
        level = self._get_level(codeblock[0])
        cutoff = level*self.indent
        code = '\n'.join([line[cutoff:] for line in codeblock])
        _tree = ast.parse(code)
        #print ast.dump(_tree)
        #self._associative_lines[self.lineno] = (self._current_line_number, ' in codeblock')
        for node in _tree.body:
            self.ctx.append(node)

    def handle_for(self, line):
        old_line = line
        line = line[1:]
        if line[-1] != ':':
            line += ': pass'
        else:
            line += ' pass'
        _tree = ast.parse(line)
        _tree.body[0].body = []
        self._associative_lines[self.lineno] = (self._current_line_number, old_line)
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
    parser = Parser()
    parser.parse(input)
    tree = parser.tree
    data = {
        'a':'THIS IS A<`^$#&',
        'b':False,
        'c':'THIS IS C',
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
    try:
        compiled_souces = compile(tree, '<string>', 'exec')
        exec compiled_souces in ns
    except Exception, e:
        tb = traceback.extract_tb(sys.exc_traceback)
        line_number = tb[-1][1]
        raise
        template_line_number, line_text = parser._associative_lines[line_number]
        raise TemplateError('Template line %d: %s:\n %s: %s' % (template_line_number,
                                                 line_text,
                                                 e.__class__.__name__,
                                                 str(e)))
    ns[CTX].render(stdout)
