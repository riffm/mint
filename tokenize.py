# -*- coding: utf-8 -*-

from mint import tokenizer

if __name__ == '__main__':
    import sys
    for t in tokenizer(open(sys.argv[1], 'r')):
        print t
