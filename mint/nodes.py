# -*- coding: utf-8 -*-

import htmlentitydefs


UNSAFE_CHARS = '&<>"'
CHARS_ENTITIES = dict([(v, '&%s;' % k) for k, v in htmlentitydefs.entitydefs.items()])
UNSAFE_CHARS_ENTITIES = [(k, CHARS_ENTITIES[k]) for k in UNSAFE_CHARS]
UNSAFE_CHARS_ENTITIES.append(("'",'&#39;'))


def escape(obj):
    if hasattr(obj, '__html__'):
        return obj.__html__()
    text = str(obj)
    for k, v in UNSAFE_CHARS_ENTITIES:
        text = text.replace(k, v)
    return text


class TextNode(object):

    def __init__(self, value, escaping=True):
        if escaping:
            self.value = escape(value)
        else:
            self.value = value

    def to_ast(self):
        pass

    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self.value)
        #return 'write("%s")' % self.value


class ExprNode(object):

    def __init__(self, value):
        self.value = value

    def to_ast(self):
        pass

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.value)
        #return 'write(%s)' % self.value


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

    _selfclosed = ['link', 'input', 'br', 'hr', 'img', 'meta']

    def __init__(self, name):
        self.name = name
        self.nodes = []
        self._attrs = []
        self._attrs_if = {}

    def set_attr(self, node):
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
        return '%s("%s", nodes=%r, attrs=%r)' % (self.__class__.__name__, self.name,
                                                 self.nodes, self._attrs)


def merge(a, b):
    if isinstance(a, TextNode):
        if isinstance(b, TextNode):
            a.value += b.value
            return None
    return b


def make_list(nodes_list):
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
    yield last
