# -*- coding: utf-8 -*-

from mint import Loader
from tests import Examples

if __name__ == '__main__':
    from sys import argv
    import ast
    l = Loader('.')
    t = l.get_template(argv[1])
    #print ast.dump(t.parse(), include_attributes=False)
    print t.render(**Examples.vars).encode('utf-8')
