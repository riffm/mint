# -*- coding: utf-8 -*-

import unittest
from hampy import Template, Loader

loader = Loader('examples')

class TagsAndText(unittest.TestCase):

    def test_tags(self):
        t = loader.get_template('tags.html')
        self.assertEqual(t.render(), open('examples/tags.html.result', 'r').read())


if __name__ == '__main__':
    unittest.main()
