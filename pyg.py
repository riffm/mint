from pygments import highlight
from pygments.lexer import RegexLexer, bygroups, using, include
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from pygments.token import *

class MintLexer(RegexLexer):
    name = 'mint'
    aliases = ['mint']
    filenames = ['*.mint']
    tokens = {
        'root': [
            (r'(\s*@[a-zA-Z_:]+)(\.)', bygroups(Name.Tag, Text), 'attribute'),
            (r'\s*@[a-zA-Z_:]+', Name.Tag),
            (r'\s*#', Text, 'python-expression'),
            (r'\s*\\.*$', Text, 'text'),
            (r'\s*\{\{', String.Symbol, 'python-expression'),
            (r'[^@]', Text, 'text'),
        ],
        'attribute':[
            (r'[a-zA-Z_:]+\(', Name.Attribute),
            (r'(\))(\.)', bygroups(Name.Attribute, Text)),
            include('text'),
            (r'\)', Name.Attribute, 'root'),
        ],
        'text':[
            (r'\s*--.*$', Comment.Single),
            (r'\s*[a-zA-Z<>_:1-9]+\s*', Text),
            (r'(.*)(\{\{)', bygroups(Text, String.Symbol), 'python-expression'),
            (r'\s*#', Text, 'python-expression'),
        ],
        'python-expression': [
            (r'(.*?)(\}\})', bygroups(using(PythonLexer), String.Symbol), '#pop'),
            (r'.+:', using(PythonLexer), '#pop'),
            (r'.+\)', using(PythonLexer), '#pop'),
        ],
    }


code = '''
@html
    @head
        @title {{ title }}
    @body

        @ul
            #for img in images:
                @li @img.alt().src({{ img }})

        @table
            @tr.class(2 attr value ).id( 43)
                @td {{ item }}
                -- comment string
                @td -- comment
                    text text {{ range(2) }}
                    text text

        #def content(arg, arg1='value'):
            @p {{ arg }} text {{ arg1 }}
            @p
                {{ arg }} text {{ arg1 }}
            @div.id(1) @div.id(2) @div.id(3)
            \@div.id(1) @div.id(2) @div.id(3)

        #content(1)
'''

template = '''
<html>
    <head>
        <style>
            %s
        </style>
    </head>
    <body>
        %s
    </body>
</html>
'''

print template % (HtmlFormatter().get_style_defs('.highlight'), 
                  highlight(code, MintLexer(), HtmlFormatter()) )
