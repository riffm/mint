# -*- coding: utf-8 -*-

'''
Template Engine based on indention and python syntax.
teboi
'''

import weakref


class Template(object):

    def __init__(self, file=None, source=None, cache=True, loader=None):
        assert file or source, 'Please provide file or source'
        self._file = file
        self._source = source
        self.need_caching = cache
        # ast
        self.tree = None
        self.parsed = False
        self.compiled_code = None
        self._loader = weakref.proxy(loader)

    def render(self, **kwargs):
        pass


class BaseLoader(object):

    def get_source(self, template):
        raise NotImplementedError


class Loader(object):

    def __init__(self, *dirs, cache=True):
        self.dirs = dirs
        self.need_caching = cache

    def get_source(self, template):
        pass
