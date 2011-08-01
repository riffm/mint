=====================
Mint - Pygments lexer
=====================

Mint ships with a Pygments_ lexer available in **ext/pygments**.

We haven't included it in the package to avoid requiring Pygments_.

In order to use it you will have to make sure that **pygmint.py**
is in your `sys.path`.

Instantiate the MintLexer when calling highlight as you would with other
schemes::

    from pygmint import MintLexer
    from pygments import highlight
    from pygments.formatters import HtmlFormatter

    code = """
        {{ utils.doctype.html5 }}
        @html
            @head
            @body
              @div.class(content)"""

    print highlight(code, MintLexer(), HtmlFormatter())

.. _pygments: http://www.pygments.org
