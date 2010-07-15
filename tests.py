# -*- coding: utf-8 -*-

import os
import glob
import unittest
from mint import Template, Loader, TemplateError

loader = Loader('.')

class Examples(unittest.TestCase):

    vars = dict([(l,l) for l in ['a','b','c','d','e']])

    def test_examples(self):
        htmls = glob.glob('examples/*.html')
        results = [r[:-len('.result')]for r in glob.glob('examples/*.result')]
        for html in htmls:
            if html in results:
                print html
                t = loader.get_template(html)
                self.assertEqual(t.render(**self.vars), open(html + '.result', 'r').read())


if __name__ == '__main__':
    unittest.main()
