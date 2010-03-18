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


class Mistakes(unittest.TestCase):

    def test_tag_attr_at_same_level(self):
        t = Template('''
        <p
        :class some-value
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_attr_level(self):
        t = Template('''
            <p
        :class some-value
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_attr_place(self):
        t = Template('''
        <p
            text node
            :class some-value
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_empty_if(self):
        t = Template('''
        !if True
        text node
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_empty_if1(self):
        t = Template('''
        !if True
        <p
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_empty_elif(self):
        t = Template('''
        !elif True
        text node
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_empty_else(self):
        t = Template('''
        !else
        text node
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_empty_for(self):
        t = Template('''
        !for i in range(10)
        text node
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_wrong_base(self):
        t = Template('''

@base template.html
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_nested_slot(self):
        t = Template('''
        !def slot1()
            <p
                :attr val
            !def slot2()
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_nodes_after_attr(self):
        t = Template('''
        <p
            :attr value
                text node
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_nodes_after_attr1(self):
        t = Template('''
        <p
            :attr value
                <p
        ''')
        self.assertRaises(TemplateError, t.render)

    def test_nodes_after_text(self):
        t = Template('''
        <p
            text node
                <p
        ''')
        self.assertRaises(TemplateError, t.render)


if __name__ == '__main__':
    unittest.main()
