# -*- coding: utf-8 -*-

import os
import glob
import unittest
import mint


class TagsAndText(unittest.TestCase):

    def test_empty(self):
        'Empty template'
        self.assertRaises(AssertionError, lambda: mint.Template(''))

    def test_empty2(self):
        'Not so empty template'
        self.assertEqual(mint.Template('\n').render(), '')

    def test_tag(self):
        'One tag'
        self.assertEqual(mint.Template('@tag').render(), '<tag></tag>')

    def test_tags(self):
        'Two tags'
        self.assertEqual(mint.Template('@tag\n'
                                       '@tag2').render(), '<tag></tag><tag2></tag2>')

    def test_nested_tags(self):
        'Nested tags'
        self.assertEqual(mint.Template('@tag\n'
                                       '    @tag2').render(), '<tag><tag2></tag2></tag>')

    def test_nested_tags2(self):
        'Nested tags more levels'
        self.assertEqual(mint.Template('@tag\n'
                                       '    @tag2\n'
                                       '        @tag3').render(), 
                         '<tag><tag2><tag3></tag3></tag2></tag>')

    def test_nested_tags3(self):
        'Nested tags shortcuts'
        self.assertEqual(mint.Template('@tag @tag2 @tag3').render(), 
                         '<tag><tag2><tag3></tag3></tag2></tag>')

    def test_text_content(self):
        'Tag with text content'
        self.assertEqual(mint.Template('@tag\n'
                                       '    text content').render(), 
                         '<tag>text content\n</tag>')

    def test_text_content2(self):
        'Tag with text content shortcut'
        self.assertEqual(mint.Template('@tag text content').render(), 
                         '<tag>text content\n</tag>')

    def test_text_content3(self):
        'Tag with multiline text content'
        self.assertEqual(mint.Template('@tag\n'
                                       '    text content\n'
                                       '    more text content here.').render(),
                         '<tag>text content\nmore text content here.\n</tag>')

    def test_mixed(self):
        'Mixed text and tags'
        self.assertEqual(mint.Template('text content\n'
                                       '@tag\n'
                                       'more text content here.').render(),
                         'text content\n<tag></tag>more text content here.\n')

    def test_mixed2(self):
        'Mixed text and tags with tags shortcuts'
        self.assertEqual(mint.Template('text content\n'
                                       '@tag inside tag\n'
                                       'more text content here.').render(),
                         'text content\n<tag>inside tag\n</tag>more text content here.\n')

    def test_mixed3(self):
        'Mixed text and tags with indention'
        self.assertEqual(mint.Template('text content\n'
                                       '@tag\n'
                                       '    inside tag\n'
                                       'more text content here.').render(),
                         'text content\n<tag>inside tag\n</tag>more text content here.\n')

    def test_tag_attr(self):
        'Tags attributes'
        self.assertEqual(mint.Template('@tag.attr(value)').render(),
                         '<tag attr="value"></tag>')

    def test_tag_attr2(self):
        'Tags attributes: values with spaces'
        self.assertEqual(mint.Template('@tag.attr( value )').render(),
                         '<tag attr=" value "></tag>')

    def test_tag_attr3(self):
        'Tags attributes: multiple attrs'
        self.assertEqual(mint.Template('@tag.attr(value).attr1(value1)').render(),
                         '<tag attr="value" attr1="value1"></tag>')

    def test_tag_attr4(self):
        'Tags attributes: more complex attribute names'
        self.assertEqual(mint.Template('@tag.ns:attr-name(value)').render(),
                                       '<tag ns:attr-name="value"></tag>')

    def test_tag_attr5(self):
        'Tags attributes: tags with content'
        self.assertEqual(mint.Template('@tag.ns:attr-name(value)\n'
                                       '    text content').render(),
                                       '<tag ns:attr-name="value">text content\n</tag>')

    def test_attr_assignment(self):
        'New attribute assignment'
        self.assertEqual(mint.Template('@tag\n'
                                       '    @.attr(value)').render(),
                                       '<tag attr="value"></tag>')

    def test_attr_assignment2(self):
        'New attribute assignment with default attribute value'
        self.assertEqual(mint.Template('@tag.attr(text)\n'
                                       '    @.attr(new value)').render(),
                                       '<tag attr="new value"></tag>')

    def test_attr_setting(self):
        'Attribute setter'
        self.assertEqual(mint.Template('@tag\n'
                                       '    @+attr(value)').render(),
                                       '<tag attr="value"></tag>')

    def test_attr_setting2(self):
        'Attribute setter with default attribute value'
        self.assertEqual(mint.Template('@tag.attr(value)\n'
                                       '    @+attr( value1)').render(),
                                       '<tag attr="value value1"></tag>')


class PythonPart(unittest.TestCase):

    def test_expression(self):
        'Python expression'
        self.assertEqual(mint.Template('{{ "Hello, mint!" }}').render(), 'Hello, mint!\n')

    def test_expression1(self):
        'Wrong Python expression'
        self.assertRaises(SyntaxError, lambda: mint.Template('{{ "Hello, mint! }}').render())

    def test_expressoin_and_text(self):
        'Python expression and text after'
        self.assertEqual(mint.Template('{{ "Hello," }} mint!').render(), 'Hello, mint!\n')

    def test_expressoin_and_text2(self):
        'Python expression and text before'
        self.assertEqual(mint.Template('Hello, {{ "mint!" }}').render(), 'Hello, mint!\n')

    def test_expressoin_and_text3(self):
        'Python expression and text at new line'
        self.assertEqual(mint.Template('{{ "Hello," }}\n'
                                       'mint!').render(), 'Hello,\nmint!\n')

    def test_if(self):
        'if statement (true)'
        self.assertEqual(mint.Template('#if True:\n'
                                       '    true').render(), 'true\n')

    def test_if1(self):
        'if statement (false)'
        self.assertEqual(mint.Template('#if False:\n'
                                       '    true\n'
                                       'false').render(), 'false\n')

    def test_if2(self):
        'if-else statements'
        self.assertEqual(mint.Template('#if False:\n'
                                       '    true\n'
                                       '#else:\n'
                                       '    false').render(), 'false\n')

    def test_if3(self):
        'if-elif-else statements'
        self.assertEqual(mint.Template('#if False:\n'
                                       '    if\n'
                                       '#elif True:\n'
                                       '    elif\n'
                                       '#else:\n'
                                       '    else').render(), 'elif\n')

    def test_if4(self):
        'if-elif-else statements and nested statements'
        self.assertEqual(mint.Template('#if False:\n'
                                       '    if\n'
                                       '#elif True:\n'
                                       '    elif\n'
                                       '    #if False:\n'
                                       '        nested if\n'
                                       '    #else:\n'
                                       '        nested else\n'
                                       '#else:\n'
                                       '    else').render(), 'elif\nnested else\n')

    def test_for(self):
        'for statement'
        self.assertEqual(mint.Template('#for v in values:\n'
                                       '    {{ v }}').render(values=[1,2,3]), '1\n2\n3\n')

                                       '    {{ v }}').render(values=[1,2,3]), '1\n2\n3\n')


if __name__ == '__main__':
    unittest.main()
