# -*- coding: utf-8 -*-

import os
import glob
import unittest
import types
from StringIO import StringIO

import mint

class TagsAndText(unittest.TestCase):

    def test_empty(self):
        'Empty template'
        self.assertRaises(AssertionError, lambda: mint.Template(''))

    def test_empty2(self):
        'Not so empty template'
        self.assertEqual(mint.Template('\n').render(), '')

    def test_returns_markup(self):
        'Template.render() renturns Markup'
        self.assert_(isinstance(mint.Template('\n').render(), mint.Markup))

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

    def test_nested_tags4(self):
        'Big question'
        #XXX: Throw SyntaxError wrong indent level
        self.assertEqual(mint.Template('@li @a.href(url) text\n'
                                       '    @p other text').render(),
                         '<li><a href="url">text\n</a><p>other text\n</p></li>')

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

    def test_mint_comment(self):
        'mint comments'
        self.assertEqual(mint.Template('// comment message').render(), '')

    def test_html_comment(self):
        'html comments'
        self.assertEqual(mint.Template('-- comment message').render(), '<!-- comment message -->')

    def test_html_comment2(self):
        'html comments with trail whitespaces'
        self.assertEqual(mint.Template('--  comment message  ').render(), '<!-- comment message -->')

    def test_backspace_escaping(self):
        'Backsapce escaping'
        self.assertEqual(mint.Template('\@tag.attr(value)').render(), '@tag.attr(value)\n')

    def test_escaping(self):
        'Text value escaping'
        self.assertEqual(mint.Template('text < > \' " &').render(),
                         'text &lt; &gt; &#39; &quot; &amp;\n')

    def test_escaping2(self):
        'Tag attr value escaping'
        self.assertEqual(mint.Template('@tag.attr(text < > \' " &)').render(),
                         '<tag attr="text &lt; &gt; &#39; &quot; &amp;"></tag>')

    def test_escaping3(self):
        'Markup object value'
        self.assertEqual(mint.Template('@tag\n'
                                       '    text <tag attr="&" />\n'
                                       '    {{ value }}').render(value=mint.Markup('<tag attr="&amp;" />')),
                         '<tag>text &lt;tag attr=&quot;&amp;&quot; /&gt;\n<tag attr="&amp;" />\n</tag>')

    def test_escaping4(self):
        'Markup object value in tag attr'
        self.assertEqual(mint.Template('@tag.attr({{ value }})').render(
                                value=mint.Markup('<tag attr="&amp;" />')),
                         '<tag attr="&lt;tag attr=&quot;&amp;&quot; /&gt;"></tag>')

    def test_spaces(self):
        'Whitespaces'
        self.assertRaises(SyntaxError, lambda: mint.Template('    \n'))

    def test_syntaxerror(self):
        'indented tag'
        self.assertRaises(SyntaxError, lambda: mint.Template('    \n'
                                                             '    @tag'))

    def test_syntaxerror2(self):
        'Nestead tags with no whitespace'
        self.assertRaises(mint.WrongToken, lambda: mint.Template('@tag@tag'))

    def test_syntaxerror3(self):
        'Nestead tag with text'
        self.assertEqual(mint.Template('@tag text @tag').render(), '<tag>text @tag\n</tag>')


class Tokenizer(unittest.TestCase):

    def test_tokens(self):
        'Empty string'
        self.assertEqual(list(mint.tokenizer(StringIO())),
                         [(mint.TOKEN_EOF, 'EOF', 1, 0)])

    def test_tokens2(self):
        'Simple tokens'
        self.assertEqual(list(mint.tokenizer(StringIO('@@.@+()[]:;.,-+{{}}'))),
                         [(mint.TOKEN_TAG_START, '@', 1, 1),
                          (mint.TOKEN_TAG_ATTR_SET, '@.', 1, 2),
                          (mint.TOKEN_TAG_ATTR_APPEND, '@+', 1, 4),
                          (mint.TOKEN_PARENTHESES_OPEN, '(', 1, 6),
                          (mint.TOKEN_PARENTHESES_CLOSE, ')', 1, 7),
                          (mint.TOKEN_TEXT, '[]', 1, 8),
                          (mint.TOKEN_COLON, ':', 1, 10),
                          (mint.TOKEN_TEXT, ';', 1, 11),
                          (mint.TOKEN_DOT, '.', 1, 12),
                          (mint.TOKEN_TEXT, ',', 1, 13),
                          (mint.TOKEN_MINUS, '-', 1, 14),
                          (mint.TOKEN_PLUS, '+', 1, 15),
                          (mint.TOKEN_EXPRESSION_START, '{{', 1, 16),
                          (mint.TOKEN_EXPRESSION_END, '}}', 1, 18),
                          (mint.TOKEN_NEWLINE, '\n', 1, 20),
                          (mint.TOKEN_EOF, 'EOF', 2, 0)])

    def test_tokens3(self):
        'Special tokens'
        self.assertEqual(list(mint.tokenizer(StringIO('#base: #if #elif #else:#def #for #'))),
                         [(mint.TOKEN_BASE_TEMPLATE, '#base: ', 1, 1),
                          (mint.TOKEN_STATEMENT_IF, '#if ', 1, 8),
                          (mint.TOKEN_STATEMENT_ELIF, '#elif ', 1, 12),
                          (mint.TOKEN_STATEMENT_ELSE, '#else:', 1, 18),
                          (mint.TOKEN_SLOT_DEF, '#def ', 1, 24),
                          (mint.TOKEN_STATEMENT_FOR, '#for ', 1, 29),
                          (mint.TOKEN_STMT_CHAR, '#', 1, 34),
                          (mint.TOKEN_NEWLINE, '\n', 1, 35),
                          (mint.TOKEN_EOF, 'EOF', 2, 0)])

    def test_tokens4(self):
        'Two tokens in a row'
        self.assertEqual(list(mint.tokenizer(StringIO('{{{{#if #if '))),
                         [(mint.TOKEN_EXPRESSION_START, '{{', 1, 1),
                          (mint.TOKEN_EXPRESSION_START, '{{', 1, 3),
                          (mint.TOKEN_STATEMENT_IF, '#if ', 1, 5),
                          (mint.TOKEN_STATEMENT_IF, '#if ', 1, 9),
                          (mint.TOKEN_NEWLINE, '\n', 1, 13),
                          (mint.TOKEN_EOF, 'EOF', 2, 0)])

    def test_tokens5(self):
        'Special tokens (js)'
        self.assertEqual(list(mint.tokenizer(StringIO('#function #else if '))),
                         [(mint.TOKEN_SLOT_DEF, '#function ', 1, 1),
                          (mint.TOKEN_STATEMENT_ELIF, '#else if ', 1, 11),
                          (mint.TOKEN_NEWLINE, '\n', 1, 20),
                          (mint.TOKEN_EOF, 'EOF', 2, 0)])

    def test_indent(self):
        'One indent'
        self.assertEqual(list(mint.tokenizer(StringIO('    '))),
                         [(mint.TOKEN_INDENT, '    ', 1, 1),
                          (mint.TOKEN_NEWLINE, '\n', 1, 5),
                          (mint.TOKEN_UNINDENT, '    ', 1, 5),
                          (mint.TOKEN_EOF, 'EOF', 2, 0)])

    def test_indent2(self):
        'One indent and new line'
        self.assertEqual(list(mint.tokenizer(StringIO('    \n'))),
                         [(mint.TOKEN_INDENT, '    ', 1, 1),
                          (mint.TOKEN_NEWLINE, '\n', 1, 5),
                          (mint.TOKEN_UNINDENT, '    ', 1, 5),
                          (mint.TOKEN_EOF, 'EOF', 2, 0)])

    def test_indent2_1(self):
        'Line and indent'
        self.assertEqual(list(mint.tokenizer(StringIO('\n'
                                                      '    '))),
                         [(mint.TOKEN_NEWLINE, '\n', 1, 1),
                          (mint.TOKEN_INDENT, '    ', 2, 1),
                          (mint.TOKEN_NEWLINE, '\n', 2, 5),
                          (mint.TOKEN_UNINDENT, '    ', 2, 5),
                          (mint.TOKEN_EOF, 'EOF', 3, 0)])

    def test_indent3(self):
        'Indent tokens'
        self.assertEqual(list(mint.tokenizer(StringIO('    \n'
                                                      '        \n'
                                                      '    '))),
                         [(mint.TOKEN_INDENT, '    ', 1, 1),
                          (mint.TOKEN_NEWLINE, '\n', 1, 5),
                          (mint.TOKEN_INDENT, '    ', 2, 5),
                          (mint.TOKEN_NEWLINE, '\n', 2, 9),
                          (mint.TOKEN_UNINDENT, '    ', 3, 1),
                          (mint.TOKEN_NEWLINE, '\n', 3, 5),
                          (mint.TOKEN_UNINDENT, '    ', 3, 5),
                          (mint.TOKEN_EOF, 'EOF', 4, 0)])

    def test_indent4(self):
        'Mixed indent'
        self.assertEqual(list(mint.tokenizer(StringIO('   \n'
                                                      '       '))),
                         [(mint.TOKEN_INDENT, '   ', 1, 1),
                          (mint.TOKEN_NEWLINE, '\n', 1, 4),
                          (mint.TOKEN_INDENT, '   ', 2, 4),
                          (mint.TOKEN_WHITESPACE, ' ', 2, 7),
                          (mint.TOKEN_NEWLINE, '\n', 2, 8),
                          (mint.TOKEN_UNINDENT, '   ', 2, 8),
                          (mint.TOKEN_UNINDENT, '   ', 2, 8),
                          (mint.TOKEN_EOF, 'EOF', 3, 0)])

    def test_indent5(self):
        'More mixed indent'
        self.assertEqual(list(mint.tokenizer(StringIO('    \n'
                                                      '   '))),
                         [(mint.TOKEN_INDENT, '    ', 1, 1),
                          (mint.TOKEN_NEWLINE, '\n', 1, 5),
                          (mint.TOKEN_UNINDENT, '    ', 1, 5),
                          (mint.TOKEN_WHITESPACE, '   ', 2, 1),
                          (mint.TOKEN_NEWLINE, '\n', 2, 4),
                          (mint.TOKEN_EOF, 'EOF', 3, 0)])

    def test_indent6(self):
        'Pyramid'
        self.assertEqual(list(mint.tokenizer(StringIO('\n'
                                                      '    \n'
                                                      '        \n'
                                                      '    '))),
                         [(mint.TOKEN_NEWLINE, '\n', 1, 1),
                          (mint.TOKEN_INDENT, '    ', 2, 1),
                          (mint.TOKEN_NEWLINE, '\n', 2, 5),
                          (mint.TOKEN_INDENT, '    ', 3, 5),
                          (mint.TOKEN_NEWLINE, '\n', 3, 9),
                          (mint.TOKEN_UNINDENT, '    ', 4, 1),
                          (mint.TOKEN_NEWLINE, '\n', 4, 5),
                          (mint.TOKEN_UNINDENT, '    ', 4, 5),
                          (mint.TOKEN_EOF, 'EOF', 5, 0)])

    def test_indent7(self):
        'Pyramid with double indent'
        self.assertEqual(list(mint.tokenizer(StringIO('\n'
                                                      '    \n'
                                                      '            \n'
                                                      '    '))),
                         [(mint.TOKEN_NEWLINE, '\n', 1, 1),
                          (mint.TOKEN_INDENT, '    ', 2, 1),
                          (mint.TOKEN_NEWLINE, '\n', 2, 5),
                          (mint.TOKEN_INDENT, '    ', 3, 5),
                          (mint.TOKEN_INDENT, '    ', 3, 9),
                          (mint.TOKEN_NEWLINE, '\n', 3, 13),
                          (mint.TOKEN_UNINDENT, '    ', 4, 1),
                          (mint.TOKEN_UNINDENT, '    ', 4, 1),
                          (mint.TOKEN_NEWLINE, '\n', 4, 5),
                          (mint.TOKEN_UNINDENT, '    ', 4, 5),
                          (mint.TOKEN_EOF, 'EOF', 5, 0)])


class Parser(unittest.TestCase):

    def get_mint_tree(self, source):
        return mint.get_mint_tree(mint.tokenizer(StringIO(source)))

    def test_text_node(self):
        'Text node'
        tree = self.get_mint_tree('text content')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TextNode('text content\n', lineno=1, col_offset=1)]))

    def test_expression_node(self):
        'Expression node'
        tree = self.get_mint_tree('{{ expression }}')
        #XXX: Do we really need TextNode with "\n" at the end?
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.ExpressionNode('expression', lineno=1, col_offset=1),
                             mint.TextNode('\n', lineno=1, col_offset=17)]))

    def test_expression_node2(self):
        'Expression node with text before'
        tree = self.get_mint_tree('text value {{ expression }}')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TextNode('text value ', lineno=1, col_offset=1),
                             mint.ExpressionNode('expression', lineno=1, col_offset=12),
                             mint.TextNode('\n', lineno=1, col_offset=28)]))

    def test_expression_node3(self):
        'Expression node with text after'
        tree = self.get_mint_tree('{{ expression }} text value')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.ExpressionNode('expression', lineno=1, col_offset=1),
                             mint.TextNode(' text value\n', lineno=1, col_offset=17)]))

    def test_tag_node(self):
        'Tag node'
        tree = self.get_mint_tree('@tag')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                            mint.TagNode('tag', lineno=1, col_offset=1)]))

    def test_tag_node2(self):
        'Tag node with attrs'
        tree = self.get_mint_tree('@tag.attr(value)')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TagNode('tag',
                                           attrs=[mint.TagAttrNode('attr',
                                                                   value=[mint.TextNode('value',
                                                                                        lineno=1,
                                                                                        col_offset=11)],
                                                                    lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node3(self):
        'Tag node with attrs and body text'
        tree = self.get_mint_tree('@tag.attr(value)\n'
                                  '    text value')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TagNode('tag',
                                           attrs=[mint.TagAttrNode('attr',
                                                                   value=[mint.TextNode('value',
                                                                                        lineno=1,
                                                                                        col_offset=11)],
                                                                    lineno=1, col_offset=6)],
                                           body=[mint.TextNode('text value\n', lineno=2, col_offset=5)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node4(self):
        'Tag node with child tag'
        tree = self.get_mint_tree('@tag\n'
                                  '    @tag2')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TagNode('tag', attrs=[],
                                           body=[mint.TagNode('tag2', attrs=[], body=[],
                                                              lineno=2, col_offset=5)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node5(self):
        'Nodes for short tags record'
        tree = self.get_mint_tree('@tag @tag2')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TagNode('tag', attrs=[],
                                           body=[mint.TagNode('tag2', attrs=[], body=[],
                                                              lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node6(self):
        'Nodes for short tags record with text'
        tree = self.get_mint_tree('@tag @tag2 text value')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TagNode('tag', attrs=[],
                                           body=[mint.TagNode('tag2', attrs=[],
                                                              body=[mint.TextNode('text value\n',
                                                                                  lineno=1, col_offset=12)],
                                                              lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_tag_attr(self):
        'Tag attribute node with expression'
        tree = self.get_mint_tree('@tag.attr({{ expression }})')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.TagNode('tag',
                                           attrs=[mint.TagAttrNode('attr',
                                                                   value=[mint.ExpressionNode('expression',
                                                                                              lineno=1,
                                                                                              col_offset=11)],
                                                                   lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_if_node(self):
        'If statement'
        tree = self.get_mint_tree('#if statement')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.IfStmtNode('#if statement', body=[], lineno=1, col_offset=1)]))

    def test_if_node2(self):
        'If statement with body'
        tree = self.get_mint_tree('#if statement\n'
                                  '    text value')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.IfStmtNode('#if statement',
                                             body=[mint.TextNode('text value\n', lineno=2, col_offset=5)],
                                             lineno=1, col_offset=1)]))

    def test_if_node3(self):
        'If statement with else'
        tree = self.get_mint_tree('#if statement\n'
                                  '    text value\n'
                                  '#else:\n'
                                  '    another text value')
        self.assertEqual(tree,
                         mint.MintTemplate(body=[
                             mint.IfStmtNode('#if statement',
                                             body=[mint.TextNode('text value\n', lineno=2, col_offset=5)],
                                             orelse=[mint.ElseStmtNode(body=[
                                                 mint.TextNode('another text value\n',
                                                               lineno=4, col_offset=5)],
                                                                       lineno=3, col_offset=1)],
                                             lineno=1, col_offset=1)]))


class DummyLoader(object):
    def __init__(self, templates):
        self.templates = templates
    def get_template(self, template_name):
        return self.templates[template_name]


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

    def test_slotdef(self):
        'Slot definition'
        self.assertEqual(mint.Template('#def count():\n'
                                       '    {{ value }}').render(value=1), '')

    def test_slotcall(self):
        'Slot call'
        self.assertEqual(mint.Template('#def count():\n'
                                       '    {{ value }}\n'
                                       '#count()').render(value=1), '1\n')

    def test_slotcall_from_python(self):
        'Slot call from python code'
        t = mint.Template('#def count(value):\n'
                          '    {{ value }}\n'
                          '#count()')
        slot = t.slot('count')
        self.assert_(isinstance(slot, types.FunctionType))
        self.assertEqual(slot(1), '1\n')

    def test_inheritance(self):
        'One level inheritance'
        loader = DummyLoader({
            'base.mint':mint.Template('#def slot():\n'
                                      '    base slot\n'
                                      '#slot()'),
        })
        self.assertEqual(mint.Template('#base: base.mint\n'
                                       '#def slot():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'overrided slot\n')

    def test_inheritance2(self):
        'One level inheritance with different slots'
        loader = DummyLoader({
            'base.mint':mint.Template('#def slot1():\n'
                                      '    base slot\n'
                                      '#slot1()\n'
                                      '#slot2()'),
        })
        self.assertEqual(mint.Template('#base: base.mint\n'
                                       '#def slot2():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\noverrided slot\n')

    def test_inheritance3(self):
        'Two level inheritance'
        loader = DummyLoader({
            'base.mint':mint.Template('#def slot():\n'
                                      '    base slot\n'
                                      '#slot()'),
        })
        loader.templates.update({
            'base2.mint':mint.Template('#base: base.mint\n'
                                       '#def slot():\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(mint.Template('#base: base2.mint\n'
                                       '#def slot():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'overrided slot\n')

    def test_inheritance4(self):
        'Two level inheritance and slots on differrent levels'
        loader = DummyLoader({
            'base.mint':mint.Template('#def slot1():\n'
                                      '    base slot\n'
                                      '#slot1()\n'
                                      '#slot2()\n'
                                      '#slot3()\n'),
        })
        loader.templates.update({
            'base2.mint':mint.Template('#base: base.mint\n'
                                       '#def slot2():\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(mint.Template('#base: base2.mint\n'
                                       '#def slot3():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\nbase2 slot\noverrided slot\n')

    def test_inheritance5(self):
        'Two level inheritance and slots on differrent levels 2'
        loader = DummyLoader({
            'base.mint':mint.Template('#def slot1():\n'
                                      '    base slot\n'
                                      '#slot1()\n'
                                      '#slot2()\n'
                                      '#slot3()\n'),
        })
        loader.templates.update({
            'base2.mint':mint.Template('#base: base.mint\n'
                                       '#def slot2():\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(mint.Template('#base: base2.mint\n'
                                       '#def slot2():\n'
                                       '    overrided base2 slot\n'
                                       '#def slot3():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\noverrided base2 slot\noverrided slot\n')

    def test_inheritance6(self):
        'Two level inheritance and __base__'
        loader = DummyLoader({
            'base.mint':mint.Template('#def slot():\n'
                                      '    base slot\n'
                                      '#slot()'),
        })
        loader.templates.update({
            'base2.mint':mint.Template('#base: base.mint\n'
                                       '#def slot():\n'
                                       '    {{ __base__() }}\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(mint.Template('#base: base2.mint\n'
                                       '#def slot():\n'
                                       '    {{ __base__() }}\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\n\nbase2 slot\n\noverrided slot\n')


class PprintTests(unittest.TestCase):

    def test_empty(self):
        'Pprint not so empty template'
        self.assertEqual(mint.Template('\n', pprint=True).render(), '')

    def test_tag(self):
        'Pprint tag'
        self.assertEqual(mint.Template('@tag', pprint=True).render(), '<tag></tag>\n')

    def test_tags(self):
        'Pprint tags'
        self.assertEqual(mint.Template('@tag @tag', pprint=True).render(),
                         '<tag>\n'
                         '  <tag></tag>\n'
                         '</tag>\n')

    def test_tags2(self):
        'Pprint tags in a row'
        self.assertEqual(mint.Template('@tag\n'
                                       '@tag', pprint=True).render(),
                         '<tag></tag>\n'
                         '<tag></tag>\n')

    def test_tag_attrs(self):
        'Pprint tag with attrs'
        self.assertEqual(mint.Template('@tag.attr(value)', pprint=True).render(), '<tag attr="value"></tag>\n')

    def test_tags_attrs(self):
        'Pprint tags with attrs'
        self.assertEqual(mint.Template('@tag.attr(value) @tag.attr(value)', pprint=True).render(),
                         '<tag attr="value">\n'
                         '  <tag attr="value"></tag>\n'
                         '</tag>\n')

    def test_tag_text(self):
        'Pprint tag with text content'
        self.assertEqual(mint.Template('@tag text text', pprint=True).render(),
                         '<tag>\n'
                         '  text text\n'
                         '</tag>\n')

    def test_tag_big_text(self):
        'Pprint tag with big text content'
        self.assertEqual(mint.Template('@tag Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat volutpat. Ut wisi enim ad minim veniam, quis nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat.', pprint=True).render(), 
                        '<tag>\n'
                        '  Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat volutpat. Ut wisi enim ad minim veniam, quis nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat.\n'
                        '</tag>\n')

    def test_slot(self):
        'Pprint tag with slot'
        self.assertEqual(mint.Template('#def slot():\n'
                                       '  @tag.attr(value)\n'
                                       '@tag\n'
                                       '  #slot()', pprint=True).render(),
                         '<tag>\n'
                         '  <tag attr="value"></tag>\n'
                         '</tag>\n')

    def test_slot_tags(self):
        'Pprint tag with slot with tags'
        self.assertEqual(mint.Template('#def slot():\n'
                                       '  @tag\n'
                                       '    @tag.attr(value) text\n'
                                       '@tag\n'
                                       '  #slot()', pprint=True).render(),
                         '<tag>\n'
                         '  <tag>\n'
                         '    <tag attr="value">\n'
                         '      text\n'
                         '    </tag>\n'
                         '  </tag>\n'
                         '</tag>\n')



if __name__ == '__main__':
    unittest.main()
