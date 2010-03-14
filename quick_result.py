# -*- coding: utf-8 -*-

from hampy import Loader
from tests import Examples

if __name__ == '__main__':
    from sys import argv
    l = Loader('.')
    t = l.get_template(argv[1])
    print t.render(**Examples.vars)
