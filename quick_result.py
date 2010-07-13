# -*- coding: utf-8 -*-

from mint import Loader
from tests import Examples

import datetime

if __name__ == '__main__':
    from sys import argv
    import ast
    l = Loader('.', cache=True)
    t = l.get_template(argv[1])
    #print ast.dump(t.parse(), include_attributes=False)
    tries = []
    for i in range(100):
        start = datetime.datetime.now()
        print t.render(**Examples.vars).encode('utf-8')
        end = datetime.datetime.now()
        tries.append(end - start)
    for t in tries:
        print str(t)
