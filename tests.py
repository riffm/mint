# -*- coding: utf-8 -*-

import os
import glob
import unittest
from hampy import Template, Loader

loader = Loader('.')

class Examples(unittest.TestCase):

    def test_examples(self):
        htmls = glob.glob('examples/*.html')
        results = [r[:-len('.result')]for r in glob.glob('examples/*.result')]
        for html in htmls:
            if html in results:
                print html
                t = loader.get_template(html)
                self.assertEqual(t.render(), open(html + '.result', 'r').read(), html)


if __name__ == '__main__':
    unittest.main()
