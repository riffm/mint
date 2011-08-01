from pygments.lexer import RegexLexer, bygroups, using, include
from pygments.lexers import PythonLexer
from pygments.token import *

class MintLexer(RegexLexer):
    name = 'mint'
    aliases = ['mint']
    filenames = ['*.mint']
    tokens = {
        'root': [
            (r'(\s*@[a-zA-Z_:-]+)(\.)', bygroups(Name.Tag, Text), 'attribute'),
            (r'\s*@[a-zA-Z_:-]+', Name.Tag),
            (r'\s*@\+', Name.Tag, 'attribute'),
            (r'\s*@.', Name.Tag, 'attribute'),
            (r'\s*#', Text, 'python-expression'),
            (r'\s*\\.*$', Text, 'text'),
            (r'\s*\{\{', String.Symbol, 'python-expression'),
            (r'[^@]', Text, 'text'),
        ],
        'attribute':[
            (r'[a-zA-Z_:-]+\(', Name.Attribute),
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
