# -*- coding: utf-8 -*-

from .escape import Markup, CHARS_ENTITIES


class doctype:
    html_strict = Markup('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">')
    html_transitional = Markup('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 '
                               'Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">')
    xhtml_strict = Markup('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
                          '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')
    xhtml_transitional = Markup('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 '
                                'Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">')
    html5 = Markup('<!DOCTYPE html>')


markup = Markup


def loop(iterable):
    return Looper(iterable)


def entity(char):
    return Markup(CHARS_ENTITIES.get(char, char))


def script(src=None, data=None, type='text/javascript'):
    if src:
        return Markup('<script type="%s" src="%s"></script>' % (type, src))
    elif data:
        return Markup('<script type="%s">%s</script>' % (type, data))
    return ''


def scripts(*args, **kwargs):
    result = []
    for name in args:
        result.append(script(name, **kwargs))
    return ''.join(result)


def link(href, rel='stylesheet', type='text/css'):
    return Markup('<link rel="%s" type="%s" href="%s" />' % (rel, type, href))


class Looper:
    'Cool class taken from PPA project'
    class _Item:
        def __init__(self, index, has_next):
            self.index = index
            self.has_next = has_next
            self.last = not has_next
            self.first = not index
        @property
        def odd(self):
            return self.index % 2
        @property
        def even(self):
            return not self.index % 2
        def cycle(self, *args):
            'Magic method (adopted ;)'
            return args[self.index % len(args)]

    def __init__(self, iterable):
        self._iterator = iter(iterable)

    def _shift(self):
        try:
            self._next = self._iterator.next()
        except StopIteration:
            self._has_next = False
        else:
            self._has_next = True

    def __iter__(self):
        self._shift()
        index = 0
        while self._has_next:
            value = self._next
            self._shift()
            yield value, self._Item(index, self._has_next)
            index += 1
