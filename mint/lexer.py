# -*- coding: utf-8 -*-


class _TokensCollection(object):

    _tokens = (
        'indent',
        'unindent',
        'tag_block',
        'inline_tag',
    )

    def __getattr__(self, name):
        if name in self._tokens:
            value = intern(name)
            setattr(self, name, value)
            return value
        raise AttributeError(name)

    def __getitem__(self, name):
        try:
            value = getattr(self, name)
        except AttributeError:
            raise KeyError(name)
        else:
            return value


token = _TokensCollection()
