# -*- coding: utf-8 -*-

import os
from ast import Store
from StringIO import StringIO
from . import utils
from .trees import (
        correct_inheritance, AstWrapper, new_tree,
        ESCAPE_HELLPER, TREE_FACTORY, MAIN_FUNCTION, MintToPythonTransformer,
        SlotsGetter
        )
from .lexer import tokenizer
from .parser import get_mint_tree
from .escape import escape


class TemplateNotFound(Exception):
    pass


class Template(object):

    def __init__(self, source, filename=None, loader=None, globals=None,
                 pprint=False):
        assert source or filename, 'Please provide source code or filename'
        self.source = source
        self.filename = filename if filename else '<string>'
        self._loader = loader
        self.compiled_code = compile(self.tree(), self.filename, 'exec')
        self.globals = globals or {}
        self.pprint = pprint

    def tree(self, slots=None):
        slots = slots or {}
        source = StringIO(self.source) if self.source else open(self.filename, 'r')
        mint_tree = get_mint_tree(tokenizer(source))
        tree = MintToPythonTransformer().visit(mint_tree)
        slots_getter = SlotsGetter()
        slots_getter.visit(tree.body[0])
        _slots, base_template_name = slots_getter.slots, slots_getter.base
        # we do not want to override slot's names,
        # so prefixing existing slots with underscore
        slots = correct_inheritance(slots, _slots)
        if base_template_name:
            base_template = self._loader.get_template(base_template_name)
            tree = base_template.tree(slots=slots)
        elif slots is not None:
            # insert implementation of slots
            # def slot_bb13e100d5(): ...
            # and insert assings of slots
            # real_slot_name = slot_bb13e100d5
            for k,v in slots.items():
                if not k.endswith('__overrided'):
                    ast_ = AstWrapper(v.lineno, v.col_offset)
                    tree.body.insert(0, ast_.Assign(targets=[
                        ast_.Name(id=k, ctx=Store())],
                        value=ast_.Name(id=v.name)))
                tree.body.insert(0, v)
        # tree already has slots definitions and ready to be compiled
        return tree

    def render(self, **kwargs):
        ns = {
            'utils':utils,
            ESCAPE_HELLPER:escape,
            TREE_FACTORY:new_tree(self.pprint),
        }
        ns.update(self.globals)
        ns.update(kwargs)
        exec self.compiled_code in ns
        # execute template main function
        return ns[MAIN_FUNCTION]()

    def slot(self, name, **kwargs):
        ns = {
            'utils':utils,
            ESCAPE_HELLPER:escape,
            TREE_FACTORY:new_tree(self.pprint),
        }
        ns.update(self.globals)
        ns.update(kwargs)
        exec self.compiled_code in ns
        return ns[name]


class Loader(object):

    def __init__(self, *dirs, **kwargs):
        self.dirs = []
        # dirs - list of directories. Order matters
        for d in dirs:
            self.dirs.append(os.path.abspath(d))
        self.cache = kwargs.get('cache', False)
        self._templates_cache = {}
        self.globals = kwargs.get('globals', {})
        self.pprint = kwargs.get('pprint', 0)

    def get_template(self, template):
        if template in self._templates_cache:
            return self._templates_cache[template]
        for dir in self.dirs:
            location = os.path.join(dir, template)
            if os.path.exists(location) and os.path.isfile(location):
                with open(location, 'r') as f:
                    tmpl = Template(source=f.read(), filename=f.name,
                                    loader=self, globals=self.globals, pprint=self.pprint)
                    if self.cache:
                        self._templates_cache[template] = tmpl
                    return tmpl
        raise TemplateNotFound(template)

    def __add__(self, other):
        dirs = self.dirs + other.dirs
        return self.__class__(cache=self.cache, globals=self.globals,*dirs)
