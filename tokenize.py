# -*- coding: utf-8 -*-

from mint import TokensStream

if __name__ == '__main__':
    import sys
    stream = TokensStream(open(sys.argv[1], 'r'))
    for t in stream.tokenize():
        print t
