# -*- coding: utf-8 -*-

import unittest
import types
from StringIO import StringIO

from mint import lexer
from mint.lexer import token


class TokensTest(unittest.TestCase):

    def test_valid_token(self):
        lexer.token.indent
        lexer.token['indent']

    def test_invalid_token(self):
        with self.assertRaises(AttributeError):
            lexer.token.wat
        with self.assertRaises(KeyError):
            lexer.token['wat']

    def test_equality(self):
        self.assertTrue(lexer.token.indent is lexer.token.indent)

    def test_value(self):
        value = lexer.TokenValue(lexer.token.indent, ' ', 1, 0)
        self.assertEqual(value.token, lexer.token.indent)
        self.assertEqual(value[0], lexer.token.indent)
        self.assertEqual(value.value, ' ')
        self.assertEqual(value[1], ' ')
        self.assertEqual(value.line, 1)
        self.assertEqual(value[2], 1)
        self.assertEqual(value.pos, 0)
        self.assertEqual(value[3], 0)


class LexerTest(unittest.TestCase):

    src = u'съешь же ещё этих мягких \n'+\
          u'французских булок, \n'+\
          u'да выпей чаю\n'

    def test_next(self):
        lex = lexer.Lexer(self.src)
        self.assertEqual([lex.next() for i in range(len(self.src)+1)],
                         list(self.src)+[''])
        self.assertEqual(lex.line_no, 1)
        self.assertEqual(lex.line_pos, 0)
        self.assertEqual(lex.lines, [('', 0),
                                     (u'съешь же ещё этих мягких \n', 26),
                                     (u'французских булок, \n', 46),
                                     (u'да выпей чаю\n', 59)])

    def test_backup(self):
        lex = lexer.Lexer(self.src)
        lex.next()
        lex.backup()
        self.assertEqual(lex.pos, 0)
        self.assertEqual(lex.last_char, '')

    def test_backup_at_line_beginging(self):
        lex = lexer.Lexer(u'\n\nb')
        lex.next()
        lex.next()
        lex.next()
        lex.backup()
        self.assertEqual(lex.pos, 2)
        self.assertEqual(lex.lines, [('', 0), ('\n', 1)])
        self.assertEqual(lex.last_char, '\n')
        lex.backup()
        self.assertEqual(lex.pos, 1)
        self.assertEqual(lex.lines, [('', 0) ])
        self.assertEqual(lex.last_char, '\n')
        lex.backup()
        self.assertEqual(lex.pos, 0)
        self.assertEqual(lex.lines, [('', 0)])
        self.assertEqual(lex.last_char, '')

    def test_ignore(self):
        lex = lexer.Lexer(u'\n\nb')
        lex.next()
        lex.ignore()
        self.assertEqual(lex.start, 1)
        self.assertEqual(lex.pos, 1)
        self.assertEqual(lex.line_no, 2)
        self.assertEqual(lex.line_pos, 0)
        self.assertEqual(lex.lines, [('', 0)])
        lex.next()
        lex.ignore()
        self.assertEqual(lex.start, 2)
        self.assertEqual(lex.pos, 2)
        self.assertEqual(lex.line_no, 3)
        self.assertEqual(lex.line_pos, 0)
        self.assertEqual(lex.lines, [('', 0), ('\n', 1)])

    def test_peek(self):
        lex = lexer.Lexer(u'ab')
        self.assertEqual(lex.peek(), 'a')
        lex.next()
        self.assertEqual(lex.peek(), 'b')

    def test_accept(self):
        lex = lexer.Lexer(u'ab')
        self.assertTrue(lex.accept('a'))
        self.assertEqual(lex.pos, 1)
        self.assertEqual(lex.start, 0)
        self.assertTrue(lex.accept('b'))
        self.assertEqual(lex.pos, 2)
        self.assertEqual(lex.start, 0)

    def test_accept_run_of_one_char(self):
        lex = lexer.Lexer(u'ab')
        lex.accept_run('a')
        self.assertEqual(lex.pos, 1)
        self.assertEqual(lex.start, 0)

    def test_accept_run_of_multiple_chars(self):
        lex = lexer.Lexer(u'ab')
        lex.accept_run('abc')
        self.assertEqual(lex.pos, 2)
        self.assertEqual(lex.start, 0)

    def test_indention(self):
        lex = lexer.Lexer(u' \n')
        self.assertEqual(list(lex), [(token.indent, 1, 1, 0),
                                     (token.text, '\n', 1, 1),
                                     (token.unindent, 1, 2, 0),
                                     (token.eof, '', 2, 0)])
        self.assertEqual(lex.indent, ' ')
        self.assertEqual(lex.indent_level, 0)

    def test_same_level_indention(self):
        lex = lexer.Lexer(u' \n \n')
        self.assertEqual(list(lex), [(token.indent, 1, 1, 0),
                                     (token.text, '\n', 1, 1),
                                     (token.text, '\n', 2, 1),
                                     (token.unindent, 1, 3, 0),
                                     (token.eof, '', 3, 0)])

    def test_indent_unindent(self):
        lex = lexer.Lexer(u' \n\n')
        self.assertEqual(list(lex), [(token.indent, 1, 1, 0),
                                     (token.text, '\n', 1, 1),
                                     (token.unindent, 1, 2, 0),
                                     (token.text, '\n', 2, 0),
                                     (token.eof, '', 3, 0)])


@unittest.skip('Broken lexer')
class TagsAndText(unittest.TestCase):

    def test_empty(self):
        'Empty template'
        self.assertRaises(AssertionError, lambda: Template(''))

    def test_empty2(self):
        'Not so empty template'
        self.assertEqual(Template('\n').render(), '')

    def test_returns_markup(self):
        'Template.render() renturns Markup'
        self.assert_(isinstance(Template('\n').render(), Markup))

    def test_tag(self):
        'One tag'
        self.assertEqual(Template('@tag').render(), '<tag></tag>')

    def test_tags(self):
        'Two tags'
        self.assertEqual(Template('@tag\n'
                                       '@tag2').render(), '<tag></tag><tag2></tag2>')

    def test_nested_tags(self):
        'Nested tags'
        self.assertEqual(Template('@tag\n'
                                       '    @tag2').render(), '<tag><tag2></tag2></tag>')

    def test_nested_tags2(self):
        'Nested tags more levels'
        self.assertEqual(Template('@tag\n'
                                       '    @tag2\n'
                                       '        @tag3').render(),
                         '<tag><tag2><tag3></tag3></tag2></tag>')

    def test_nested_tags3(self):
        'Nested tags shortcuts'
        self.assertEqual(Template('@tag @tag2 @tag3').render(),
                         '<tag><tag2><tag3></tag3></tag2></tag>')

    def test_nested_tags4(self):
        'Big question'
        #XXX: Throw SyntaxError wrong indent level
        self.assertEqual(Template('@li @a.href(url) text\n'
                                       '    @p other text').render(),
                         '<li><a href="url">text\n</a><p>other text\n</p></li>')

    def test_text_content(self):
        'Tag with text content'
        self.assertEqual(Template('@tag\n'
                                       '    text content').render(),
                         '<tag>text content\n</tag>')

    def test_text_content2(self):
        'Tag with text content shortcut'
        self.assertEqual(Template('@tag text content').render(),
                         '<tag>text content\n</tag>')

    def test_text_content3(self):
        'Tag with multiline text content'
        self.assertEqual(Template('@tag\n'
                                       '    text content\n'
                                       '    more text content here.').render(),
                         '<tag>text content\nmore text content here.\n</tag>')

    def test_mixed(self):
        'Mixed text and tags'
        self.assertEqual(Template('text content\n'
                                       '@tag\n'
                                       'more text content here.').render(),
                         'text content\n<tag></tag>more text content here.\n')

    def test_mixed2(self):
        'Mixed text and tags with tags shortcuts'
        self.assertEqual(Template('text content\n'
                                       '@tag inside tag\n'
                                       'more text content here.').render(),
                         'text content\n<tag>inside tag\n</tag>more text content here.\n')

    def test_mixed3(self):
        'Mixed text and tags with indention'
        self.assertEqual(Template('text content\n'
                                       '@tag\n'
                                       '    inside tag\n'
                                       'more text content here.').render(),
                         'text content\n<tag>inside tag\n</tag>more text content here.\n')

    def test_tag_attr(self):
        'Tags attributes'
        self.assertEqual(Template('@tag.attr(value)').render(),
                         '<tag attr="value"></tag>')

    def test_tag_attr2(self):
        'Tags attributes: values with spaces'
        self.assertEqual(Template('@tag.attr( value )').render(),
                         '<tag attr=" value "></tag>')

    def test_tag_attr3(self):
        'Tags attributes: multiple attrs'
        self.assertEqual(Template('@tag.attr(value).attr1(value1)').render(),
                         '<tag attr="value" attr1="value1"></tag>')

    def test_tag_attr4(self):
        'Tags attributes: more complex attribute names'
        self.assertEqual(Template('@tag.ns:attr-name(value)').render(),
                                       '<tag ns:attr-name="value"></tag>')

    def test_tag_attr5(self):
        'Tags attributes: tags with content'
        self.assertEqual(Template('@tag.ns:attr-name(value)\n'
                                       '    text content').render(),
                                       '<tag ns:attr-name="value">text content\n</tag>')

    def test_attr_assignment(self):
        'New attribute assignment'
        self.assertEqual(Template('@tag\n'
                                       '    @.attr(value)').render(),
                                       '<tag attr="value"></tag>')

    def test_attr_assignment2(self):
        'New attribute assignment with default attribute value'
        self.assertEqual(Template('@tag.attr(text)\n'
                                       '    @.attr(new value)').render(),
                                       '<tag attr="new value"></tag>')

    def test_attr_setting(self):
        'Attribute setter'
        self.assertEqual(Template('@tag\n'
                                       '    @+attr(value)').render(),
                                       '<tag attr="value"></tag>')

    def test_attr_setting2(self):
        'Attribute setter with default attribute value'
        self.assertEqual(Template('@tag.attr(value)\n'
                                       '    @+attr( value1)').render(),
                                       '<tag attr="value value1"></tag>')

    def test_mint_comment(self):
        'mint comments'
        self.assertEqual(Template('// comment message').render(), '')

    def test_html_comment(self):
        'html comments'
        self.assertEqual(Template('-- comment message').render(), '<!-- comment message -->')

    def test_html_comment2(self):
        'html comments with trail whitespaces'
        self.assertEqual(Template('--  comment message  ').render(), '<!-- comment message -->')

    def test_backspace_escaping(self):
        'Backsapce escaping'
        self.assertEqual(Template('\@tag.attr(value)').render(), '@tag.attr(value)\n')

    def test_escaping(self):
        'Text value escaping'
        self.assertEqual(Template('text < > \' " &').render(),
                         'text &lt; &gt; &#39; &quot; &amp;\n')

    def test_escaping2(self):
        'Tag attr value escaping'
        self.assertEqual(Template('@tag.attr(text < > \' " &)').render(),
                         '<tag attr="text &lt; &gt; &#39; &quot; &amp;"></tag>')

    def test_escaping3(self):
        'Markup object value'
        self.assertEqual(Template('@tag\n'
                                       '    text <tag attr="&" />\n'
                                       '    {{ value }}').render(value=Markup('<tag attr="&amp;" />')),
                         '<tag>text &lt;tag attr=&quot;&amp;&quot; /&gt;\n<tag attr="&amp;" />\n</tag>')

    def test_escaping4(self):
        'Markup object value in tag attr'
        self.assertEqual(Template('@tag.attr({{ value }})').render(
                                value=Markup('<tag attr="&amp;" />')),
                         '<tag attr="&lt;tag attr=&quot;&amp;&quot; /&gt;"></tag>')

    def test_spaces(self):
        'Whitespaces'
        self.assertRaises(SyntaxError, lambda: Template('    \n'))

    def test_syntaxerror(self):
        'indented tag'
        self.assertRaises(SyntaxError, lambda: Template('    \n'
                                                             '    @tag'))

    def test_syntaxerror2(self):
        'Nestead tags with no whitespace'
        self.assertRaises(parser.WrongToken, lambda: Template('@tag@tag'))

    def test_syntaxerror3(self):
        'Nestead tag with text'
        self.assertEqual(Template('@tag text @tag').render(), '<tag>text @tag\n</tag>')


@unittest.skip('Broken lexer')
class Tokenizer(unittest.TestCase):

    def test_tokens(self):
        'Empty string'
        self.assertEqual(list(lexer.tokenizer(StringIO())),
                         [(lexer.TOKEN_EOF, 'EOF', 1, 0)])

    def test_tokens2(self):
        'Simple tokens'
        self.assertEqual(list(lexer.tokenizer(StringIO('@@.@+()[]:;.,-+{{}}'))),
                         [(lexer.TOKEN_TAG_START, '@', 1, 1),
                          (lexer.TOKEN_TAG_ATTR_SET, '@.', 1, 2),
                          (lexer.TOKEN_TAG_ATTR_APPEND, '@+', 1, 4),
                          (lexer.TOKEN_PARENTHESES_OPEN, '(', 1, 6),
                          (lexer.TOKEN_PARENTHESES_CLOSE, ')', 1, 7),
                          (lexer.TOKEN_TEXT, '[]', 1, 8),
                          (lexer.TOKEN_COLON, ':', 1, 10),
                          (lexer.TOKEN_TEXT, ';', 1, 11),
                          (lexer.TOKEN_DOT, '.', 1, 12),
                          (lexer.TOKEN_TEXT, ',', 1, 13),
                          (lexer.TOKEN_MINUS, '-', 1, 14),
                          (lexer.TOKEN_PLUS, '+', 1, 15),
                          (lexer.TOKEN_EXPRESSION_START, '{{', 1, 16),
                          (lexer.TOKEN_EXPRESSION_END, '}}', 1, 18),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 20),
                          (lexer.TOKEN_EOF, 'EOF', 2, 0)])

    def test_tokens3(self):
        'Special tokens'
        self.assertEqual(list(lexer.tokenizer(StringIO('#base: #if #elif #else:#def #for #'))),
                         [(lexer.TOKEN_BASE_TEMPLATE, '#base: ', 1, 1),
                          (lexer.TOKEN_STATEMENT_IF, '#if ', 1, 8),
                          (lexer.TOKEN_STATEMENT_ELIF, '#elif ', 1, 12),
                          (lexer.TOKEN_STATEMENT_ELSE, '#else:', 1, 18),
                          (lexer.TOKEN_SLOT_DEF, '#def ', 1, 24),
                          (lexer.TOKEN_STATEMENT_FOR, '#for ', 1, 29),
                          (lexer.TOKEN_STMT_CHAR, '#', 1, 34),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 35),
                          (lexer.TOKEN_EOF, 'EOF', 2, 0)])

    def test_tokens4(self):
        'Two tokens in a row'
        self.assertEqual(list(lexer.tokenizer(StringIO('{{{{#if #if '))),
                         [(lexer.TOKEN_EXPRESSION_START, '{{', 1, 1),
                          (lexer.TOKEN_EXPRESSION_START, '{{', 1, 3),
                          (lexer.TOKEN_STATEMENT_IF, '#if ', 1, 5),
                          (lexer.TOKEN_STATEMENT_IF, '#if ', 1, 9),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 13),
                          (lexer.TOKEN_EOF, 'EOF', 2, 0)])

    def test_tokens5(self):
        'Special tokens (js)'
        self.assertEqual(list(lexer.tokenizer(StringIO('#function #else if '))),
                         [(lexer.TOKEN_SLOT_DEF, '#function ', 1, 1),
                          (lexer.TOKEN_STATEMENT_ELIF, '#else if ', 1, 11),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 20),
                          (lexer.TOKEN_EOF, 'EOF', 2, 0)])

    def test_indent(self):
        'One indent'
        self.assertEqual(list(lexer.tokenizer(StringIO('    '))),
                         [(lexer.TOKEN_INDENT, '    ', 1, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 1, 5),
                          (lexer.TOKEN_EOF, 'EOF', 2, 0)])

    def test_indent2(self):
        'One indent and new line'
        self.assertEqual(list(lexer.tokenizer(StringIO('    \n'))),
                         [(lexer.TOKEN_INDENT, '    ', 1, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 1, 5),
                          (lexer.TOKEN_EOF, 'EOF', 2, 0)])

    def test_indent2_1(self):
        'Line and indent'
        self.assertEqual(list(lexer.tokenizer(StringIO('\n'
                                                      '    '))),
                         [(lexer.TOKEN_NEWLINE, '\n', 1, 1),
                          (lexer.TOKEN_INDENT, '    ', 2, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 2, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 2, 5),
                          (lexer.TOKEN_EOF, 'EOF', 3, 0)])

    def test_indent3(self):
        'Indent tokens'
        self.assertEqual(list(lexer.tokenizer(StringIO('    \n'
                                                      '        \n'
                                                      '    '))),
                         [(lexer.TOKEN_INDENT, '    ', 1, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 5),
                          (lexer.TOKEN_INDENT, '    ', 2, 5),
                          (lexer.TOKEN_NEWLINE, '\n', 2, 9),
                          (lexer.TOKEN_UNINDENT, '    ', 3, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 3, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 3, 5),
                          (lexer.TOKEN_EOF, 'EOF', 4, 0)])

    def test_indent4(self):
        'Mixed indent'
        self.assertEqual(list(lexer.tokenizer(StringIO('   \n'
                                                      '       '))),
                         [(lexer.TOKEN_INDENT, '   ', 1, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 4),
                          (lexer.TOKEN_INDENT, '   ', 2, 4),
                          (lexer.TOKEN_WHITESPACE, ' ', 2, 7),
                          (lexer.TOKEN_NEWLINE, '\n', 2, 8),
                          (lexer.TOKEN_UNINDENT, '   ', 2, 8),
                          (lexer.TOKEN_UNINDENT, '   ', 2, 8),
                          (lexer.TOKEN_EOF, 'EOF', 3, 0)])

    def test_indent5(self):
        'More mixed indent'
        self.assertEqual(list(lexer.tokenizer(StringIO('    \n'
                                                      '   '))),
                         [(lexer.TOKEN_INDENT, '    ', 1, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 1, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 1, 5),
                          (lexer.TOKEN_WHITESPACE, '   ', 2, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 2, 4),
                          (lexer.TOKEN_EOF, 'EOF', 3, 0)])

    def test_indent6(self):
        'Pyramid'
        self.assertEqual(list(lexer.tokenizer(StringIO('\n'
                                                      '    \n'
                                                      '        \n'
                                                      '    '))),
                         [(lexer.TOKEN_NEWLINE, '\n', 1, 1),
                          (lexer.TOKEN_INDENT, '    ', 2, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 2, 5),
                          (lexer.TOKEN_INDENT, '    ', 3, 5),
                          (lexer.TOKEN_NEWLINE, '\n', 3, 9),
                          (lexer.TOKEN_UNINDENT, '    ', 4, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 4, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 4, 5),
                          (lexer.TOKEN_EOF, 'EOF', 5, 0)])

    def test_indent7(self):
        'Pyramid with double indent'
        self.assertEqual(list(lexer.tokenizer(StringIO('\n'
                                                      '    \n'
                                                      '            \n'
                                                      '    '))),
                         [(lexer.TOKEN_NEWLINE, '\n', 1, 1),
                          (lexer.TOKEN_INDENT, '    ', 2, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 2, 5),
                          (lexer.TOKEN_INDENT, '    ', 3, 5),
                          (lexer.TOKEN_INDENT, '    ', 3, 9),
                          (lexer.TOKEN_NEWLINE, '\n', 3, 13),
                          (lexer.TOKEN_UNINDENT, '    ', 4, 1),
                          (lexer.TOKEN_UNINDENT, '    ', 4, 1),
                          (lexer.TOKEN_NEWLINE, '\n', 4, 5),
                          (lexer.TOKEN_UNINDENT, '    ', 4, 5),
                          (lexer.TOKEN_EOF, 'EOF', 5, 0)])


@unittest.skip('Broken lexer')
class Parser(unittest.TestCase):

    def get_mint_tree(self, source):
        return parser.get_mint_tree(lexer.tokenizer(StringIO(source)))

    def test_text_node(self):
        'Text node'
        tree = self.get_mint_tree('text content')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TextNode('text content\n', lineno=1, col_offset=1)]))

    def test_expression_node(self):
        'Expression node'
        tree = self.get_mint_tree('{{ expression }}')
        #XXX: Do we really need TextNode with "\n" at the end?
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.ExpressionNode('expression', lineno=1, col_offset=1),
                             nodes.TextNode('\n', lineno=1, col_offset=17)]))

    def test_expression_node2(self):
        'Expression node with text before'
        tree = self.get_mint_tree('text value {{ expression }}')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TextNode('text value ', lineno=1, col_offset=1),
                             nodes.ExpressionNode('expression', lineno=1, col_offset=12),
                             nodes.TextNode('\n', lineno=1, col_offset=28)]))

    def test_expression_node3(self):
        'Expression node with text after'
        tree = self.get_mint_tree('{{ expression }} text value')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.ExpressionNode('expression', lineno=1, col_offset=1),
                             nodes.TextNode(' text value\n', lineno=1, col_offset=17)]))

    def test_tag_node(self):
        'Tag node'
        tree = self.get_mint_tree('@tag')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                            nodes.TagNode('tag', lineno=1, col_offset=1)]))

    def test_tag_node2(self):
        'Tag node with attrs'
        tree = self.get_mint_tree('@tag.attr(value)')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TagNode('tag',
                                           attrs=[nodes.TagAttrNode('attr',
                                                                   value=[nodes.TextNode('value',
                                                                                        lineno=1,
                                                                                        col_offset=11)],
                                                                    lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node3(self):
        'Tag node with attrs and body text'
        tree = self.get_mint_tree('@tag.attr(value)\n'
                                  '    text value')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TagNode('tag',
                                           attrs=[nodes.TagAttrNode('attr',
                                                                   value=[nodes.TextNode('value',
                                                                                        lineno=1,
                                                                                        col_offset=11)],
                                                                    lineno=1, col_offset=6)],
                                           body=[nodes.TextNode('text value\n', lineno=2, col_offset=5)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node4(self):
        'Tag node with child tag'
        tree = self.get_mint_tree('@tag\n'
                                  '    @tag2')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TagNode('tag', attrs=[],
                                           body=[nodes.TagNode('tag2', attrs=[], body=[],
                                                              lineno=2, col_offset=5)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node5(self):
        'Nodes for short tags record'
        tree = self.get_mint_tree('@tag @tag2')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TagNode('tag', attrs=[],
                                           body=[nodes.TagNode('tag2', attrs=[], body=[],
                                                              lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_tag_node6(self):
        'Nodes for short tags record with text'
        tree = self.get_mint_tree('@tag @tag2 text value')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TagNode('tag', attrs=[],
                                           body=[nodes.TagNode('tag2', attrs=[],
                                                              body=[nodes.TextNode('text value\n',
                                                                                  lineno=1, col_offset=12)],
                                                              lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_tag_attr(self):
        'Tag attribute node with expression'
        tree = self.get_mint_tree('@tag.attr({{ expression }})')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.TagNode('tag',
                                           attrs=[nodes.TagAttrNode('attr',
                                                                   value=[nodes.ExpressionNode('expression',
                                                                                              lineno=1,
                                                                                              col_offset=11)],
                                                                   lineno=1, col_offset=6)],
                                           lineno=1, col_offset=1)]))

    def test_if_node(self):
        'If statement'
        tree = self.get_mint_tree('#if statement')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.IfStmtNode('#if statement', body=[], lineno=1, col_offset=1)]))

    def test_if_node2(self):
        'If statement with body'
        tree = self.get_mint_tree('#if statement\n'
                                  '    text value')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.IfStmtNode('#if statement',
                                             body=[nodes.TextNode('text value\n', lineno=2, col_offset=5)],
                                             lineno=1, col_offset=1)]))

    def test_if_node3(self):
        'If statement with else'
        tree = self.get_mint_tree('#if statement\n'
                                  '    text value\n'
                                  '#else:\n'
                                  '    another text value')
        self.assertEqual(tree,
                         nodes.MintTemplate(body=[
                             nodes.IfStmtNode('#if statement',
                                             body=[nodes.TextNode('text value\n', lineno=2, col_offset=5)],
                                             orelse=[nodes.ElseStmtNode(body=[
                                                 nodes.TextNode('another text value\n',
                                                               lineno=4, col_offset=5)],
                                                                       lineno=3, col_offset=1)],
                                             lineno=1, col_offset=1)]))


class DummyLoader(object):
    def __init__(self, templates):
        self.templates = templates
    def get_template(self, template_name):
        return self.templates[template_name]


@unittest.skip('Broken lexer')
class PythonPart(unittest.TestCase):

    def test_expression(self):
        'Python expression'
        self.assertEqual(Template('{{ "Hello, mint!" }}').render(), 'Hello, mint!\n')

    def test_expression1(self):
        'Wrong Python expression'
        self.assertRaises(SyntaxError, lambda: Template('{{ "Hello, mint! }}').render())

    def test_expressoin_and_text(self):
        'Python expression and text after'
        self.assertEqual(Template('{{ "Hello," }} mint!').render(), 'Hello, mint!\n')

    def test_expressoin_and_text2(self):
        'Python expression and text before'
        self.assertEqual(Template('Hello, {{ "mint!" }}').render(), 'Hello, mint!\n')

    def test_expressoin_and_text3(self):
        'Python expression and text at new line'
        self.assertEqual(Template('{{ "Hello," }}\n'
                                       'mint!').render(), 'Hello,\nmint!\n')

    def test_if(self):
        'if statement (true)'
        self.assertEqual(Template('#if True:\n'
                                       '    true').render(), 'true\n')

    def test_if1(self):
        'if statement (false)'
        self.assertEqual(Template('#if False:\n'
                                       '    true\n'
                                       'false').render(), 'false\n')

    def test_if2(self):
        'if-else statements'
        self.assertEqual(Template('#if False:\n'
                                       '    true\n'
                                       '#else:\n'
                                       '    false').render(), 'false\n')

    def test_if3(self):
        'if-elif-else statements'
        self.assertEqual(Template('#if False:\n'
                                       '    if\n'
                                       '#elif True:\n'
                                       '    elif\n'
                                       '#else:\n'
                                       '    else').render(), 'elif\n')

    def test_if4(self):
        'if-elif-else statements and nested statements'
        self.assertEqual(Template('#if False:\n'
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
        self.assertEqual(Template('#for v in values:\n'
                                       '    {{ v }}').render(values=[1,2,3]), '1\n2\n3\n')

    def test_slotdef(self):
        'Slot definition'
        self.assertEqual(Template('#def count():\n'
                                       '    {{ value }}').render(value=1), '')

    def test_slotcall(self):
        'Slot call'
        self.assertEqual(Template('#def count():\n'
                                       '    {{ value }}\n'
                                       '#count()').render(value=1), '1\n')

    def test_slotcall_from_python(self):
        'Slot call from python code'
        t = Template('#def count(value):\n'
                          '    {{ value }}\n'
                          '#count()')
        slot = t.slot('count')
        self.assert_(isinstance(slot, types.FunctionType))
        self.assertEqual(slot(1), '1\n')

    def test_inheritance(self):
        'One level inheritance'
        loader = DummyLoader({
            'base.mint':Template('#def slot():\n'
                                      '    base slot\n'
                                      '#slot()'),
        })
        self.assertEqual(Template('#base: base.mint\n'
                                       '#def slot():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'overrided slot\n')

    def test_inheritance2(self):
        'One level inheritance with different slots'
        loader = DummyLoader({
            'base.mint':Template('#def slot1():\n'
                                      '    base slot\n'
                                      '#slot1()\n'
                                      '#slot2()'),
        })
        self.assertEqual(Template('#base: base.mint\n'
                                       '#def slot2():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\noverrided slot\n')

    def test_inheritance3(self):
        'Two level inheritance'
        loader = DummyLoader({
            'base.mint':Template('#def slot():\n'
                                      '    base slot\n'
                                      '#slot()'),
        })
        loader.templates.update({
            'base2.mint':Template('#base: base.mint\n'
                                       '#def slot():\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(Template('#base: base2.mint\n'
                                       '#def slot():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'overrided slot\n')

    def test_inheritance4(self):
        'Two level inheritance and slots on differrent levels'
        loader = DummyLoader({
            'base.mint':Template('#def slot1():\n'
                                      '    base slot\n'
                                      '#slot1()\n'
                                      '#slot2()\n'
                                      '#slot3()\n'),
        })
        loader.templates.update({
            'base2.mint':Template('#base: base.mint\n'
                                       '#def slot2():\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(Template('#base: base2.mint\n'
                                       '#def slot3():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\nbase2 slot\noverrided slot\n')

    def test_inheritance5(self):
        'Two level inheritance and slots on differrent levels 2'
        loader = DummyLoader({
            'base.mint':Template('#def slot1():\n'
                                      '    base slot\n'
                                      '#slot1()\n'
                                      '#slot2()\n'
                                      '#slot3()\n'),
        })
        loader.templates.update({
            'base2.mint':Template('#base: base.mint\n'
                                       '#def slot2():\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(Template('#base: base2.mint\n'
                                       '#def slot2():\n'
                                       '    overrided base2 slot\n'
                                       '#def slot3():\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\noverrided base2 slot\noverrided slot\n')

    def test_inheritance6(self):
        'Two level inheritance and __base__'
        loader = DummyLoader({
            'base.mint':Template('#def slot():\n'
                                      '    base slot\n'
                                      '#slot()'),
        })
        loader.templates.update({
            'base2.mint':Template('#base: base.mint\n'
                                       '#def slot():\n'
                                       '    {{ __base__() }}\n'
                                       '    base2 slot\n', loader=loader),
        })
        self.assertEqual(Template('#base: base2.mint\n'
                                       '#def slot():\n'
                                       '    {{ __base__() }}\n'
                                       '    overrided slot\n', loader=loader).render(),
                        'base slot\n\nbase2 slot\n\noverrided slot\n')


@unittest.skip('Broken lexer')
class PprintTests(unittest.TestCase):

    def test_empty(self):
        'Pprint not so empty template'
        self.assertEqual(Template('\n', pprint=True).render(), '')

    def test_tag(self):
        'Pprint tag'
        self.assertEqual(Template('@tag', pprint=True).render(), '<tag></tag>\n')

    def test_tags(self):
        'Pprint tags'
        self.assertEqual(Template('@tag @tag', pprint=True).render(),
                         '<tag>\n'
                         '  <tag></tag>\n'
                         '</tag>\n')

    def test_tags2(self):
        'Pprint tags in a row'
        self.assertEqual(Template('@tag\n'
                                       '@tag', pprint=True).render(),
                         '<tag></tag>\n'
                         '<tag></tag>\n')

    def test_tag_attrs(self):
        'Pprint tag with attrs'
        self.assertEqual(Template('@tag.attr(value)', pprint=True).render(), '<tag attr="value"></tag>\n')

    def test_tags_attrs(self):
        'Pprint tags with attrs'
        self.assertEqual(Template('@tag.attr(value) @tag.attr(value)', pprint=True).render(),
                         '<tag attr="value">\n'
                         '  <tag attr="value"></tag>\n'
                         '</tag>\n')

    def test_tag_text(self):
        'Pprint tag with text content'
        self.assertEqual(Template('@tag text text', pprint=True).render(),
                         '<tag>\n'
                         '  text text\n'
                         '</tag>\n')

    def test_tag_big_text(self):
        'Pprint tag with big text content'
        self.assertEqual(Template('@tag Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat volutpat. Ut wisi enim ad minim veniam, quis nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat.', pprint=True).render(), 
                        '<tag>\n'
                        '  Lorem ipsum dolor sit amet, consectetuer adipiscing elit, sed diam nonummy nibh euismod tincidunt ut laoreet dolore magna aliquam erat volutpat. Ut wisi enim ad minim veniam, quis nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat.\n'
                        '</tag>\n')

    def test_slot(self):
        'Pprint tag with slot'
        self.assertEqual(Template('#def slot():\n'
                                       '  @tag.attr(value)\n'
                                       '@tag\n'
                                       '  #slot()', pprint=True).render(),
                         '<tag>\n'
                         '  <tag attr="value"></tag>\n'
                         '</tag>\n')

    def test_slot_tags(self):
        'Pprint tag with slot with tags'
        self.assertEqual(Template('#def slot():\n'
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
