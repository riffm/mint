====
mint
====

- about_
- usage_
- syntax_
  - tags_
  - attributes_
  - escaping_
  - python expressions_
  - loops_
  - conditions_
  - comments_
- inheritance_
- utils_


.. _about:

-----
about
-----

**mint** - is small, fast and easy to use (x)html templates engine.
Implemented with python language. Goodies of **mint**:

single python module
    You can copy ``mint.py`` to your project package and use it.

minimalistic syntax
    Your templates will become smaller and more readable due to
    indent based syntax.

works fast
    **mint** uses ``ast`` python module from standard library 
    (since 2.6, thank you Armin and co). So all templates compiles to optimized
    python byte code (during first call) which works fast.

smart
    **mint** knows about (x)html tags and attributes,
    so you get smart escaping. (There is a plan to implement html 
    validation during rendering)

not standing on your way
    **mint** does't hide exceptions like some other template engines, and shows line
    your template where exception was raised

Template engine was inspired by haml (a template engine written in ruby),
but some concepts were redisigned due to simplification and adoptation to python world.


.. _usage:

-----
usage
-----

API is simple::

    import mint
    loader = mint.Loader('./templates', cache=True)
    namespace = dict(a='a', b='b')
    result = loder.get_template('index.mint').render(**namespace)

.. _syntax:

------
syntax
------

**mint** syntax is based on indention, so you see document structure and 
update document fast. Because you can move blocks of code and do not search for
begining of parent tag and where it ends.


.. _tags:

tags
----

To define a tag just use ``@`` char before tag name::

    @tagname

Why **mint** does't use ``%`` char, like haml do?
I think that ``@`` char is more readable and it is just third button on the keyboard,
so you type it by one hand (without finger gymnastics).
Next example shows tags structure::

    @html
        @head
        @body

Indented tags head and body are children for tag html (parent tag).
Text is interpreted as text::

    @div
        @p
            Text of paragraph

So last example will be rendered as::

    <div>
        <p>
            Text of paragraph
        </p>
    </div>

By the way you can use short variant::

    @div
        @p Text of paragraph


.. _attributes:

attributes
----------

To define attribute **mint** uses concept similar to method calls::

    @div.id(content)

Previouse example will be rendered as::

    <div id="content"></div>

Note that there is no difference between whitespace in attribute value::

    @div.id(content)
    @div.id( content)
    @div.id( content )
    @div.id(content )

All this examples will provide the same result.

To define multiple attributes **mint** uses (so called) chaining::

    @img.alt().src(/img/my_picture.png)

Previouse example will be rendered as::

    <img alt="" src="/img/my_picture.png" />

Note that **mint** knows about selfclosed html tags.

Why do not use python dictionary declaration syntax instead?
Something like ``{alt:"", src:"/img/my_picture.png"}``

Because it is overloaded for html templating. "Chained-methods-call" like 
syntax uses less chars to type.


.. _escaping:

escaping
--------

As you know there are some chars we need to escape in xml.
And **mint** do this automaticly for you. It escapes all text inside tags and attributes.
For now moment autoescaping can not be switched off. 
But there is solution to this problem. So: ::

    @a.href(/docs?type=1&published=true) docs
    @p.class( ' " < > & )
        <div class="inside" />

Previouse example will be rendered as::

    <a href="/docs?type=1&amp;published=true">docs</a>
    <p class="&#39; &quot; &lt; &gt; &amp;">
        &lt;div class=&quot;inside&quot; /&gt;
    </p>


.. _expressions:

python expressions
------------------

Of course, template engine with out possibility to insert python expressions is unusable.
So in **mint** you can do this with syntax similar to ``jinja2`` or ``django``::

    @html
        @head
            @title {{ doc.title }}
        @body
            @div.id(content)
                Here we have content {{ doc.content }}

Under the hood **mint** calls ``unicode`` on inserted python expressions 
and escapes result.

Note that you can provide any valid python expression inside tokens ``{{`` ``}}``.
Also note that you can use limited subset of python ``__builtins__``.

In **mint** templates expressions can be used inside text elements and inside attributes.::

    @p.class(title {{ doc.main_doc_class }}).id({{ doc.id }}) {{ doc.body }}

As you remember all content inserted in tag (as text) and in attribute escapes by **mint**.
And that is good, but sometimes wee need to insert html and do not escape it.
For this purpose mint uses special class ``mint.Markup``, which implements interface of
``__html__`` method (this is something like convention). To insert html inside templates you need to mark you python variables with ``mint.Markup`` inside your python code.

In previouse example if ``doc.body`` has html we need attribute ``body`` to return 
``mint.Markup(html_string)``. And that ``html_string`` will be inserted in template
with out escaping. That is the prefered way to insert markup inside html template.

Also note that there are two context to insert markup - tag and attribute.
In case of tag ``mint.Markup`` instances will be inserted without modifications.
But if you attemed to insert markup in attribute it will be additional escaped.

For example we have such python code::

    class Doc(object):
        def __init__(self, title, body):
            self.title = mint.Markup(title)
            self.body = mint.Markup(body)

    doc = Doc('<b>title</b>', '<p>content of document</p>')

And such template::

    @div.class(doc)
        @p.class(title).title({{ doc.title }}) doc.title
        {{ doc.body }}

The result will be::

    <div class="doc">
        <p class="title" title="&gt;b&lt;title&gt;/b&lt;">
            <b>title</b>
        </p>
        <p>content of document</p>
    </div>

This feature of **mint** is very handy.

.. _loops:

loops
-----

In **mint** you can use python statement ``for``.::

    @ul
        #for img in images:
            @li @img.src({{ img.file }})

Note that::

    @li @img.src({{ img.file }})

is similar to::

    @li
        @img.src({{ img.file }})


.. _conditions:

conditions
----------

Conditions are easy to write too::

    #for doc in docs:
        #if doc.id != current_id:
            @a.href({{ url_for('doc', id=doc.id) }}) {{ doc.title }}
        #elif doc.title == 'I need paragraph':
            @p {{ doc.title }}
        #else:
            {{ doc.title }}


.. _comments:

comments
--------

To comment a line use token ``--``::

    -- In this div we provide content, yours K.O.
    @div.id(content)

Sometimes you need to use special tokens in text, so if a line starts with 
token ``\`` line is not interpreted by **mint**.

    @p.class(title) Here we have title
    \@p.class(title) Here we have title

Will provide

    <p class="title">Here we have title</p>
    @p.class(title) Here we have title



.. _inheritance:

-----------
inheritance
-----------

**mint** uses slots to implement template inheritance. Slot is nothing more but
python functions. Slot can be defined and called anywhere in template.::

    -- layout.mint
    @html
        @head
            @title {{ title }}
        @body
            @div.id(content)

                #def content():
                    @p.class(title) {{ title }}
                    {{ content }}

                #content()

            @div.id(footer)

As you can see in previouse example we define slot ``content`` and call it after that.
During call of slot it's content will be inserted in template. And if we need to insert
different content in that place we should inherit ``layout.mint`` and override ``content``
slot implementation::

    -- news.mint
    #base: layout.mint

    #def content():
        #for item in news:
            @a.href({[ url_for('news-item', id=item.id) }}) {{ news.title }}

It is simple and powerful concept.

Slots are python functions, so they see all global variables passed to template and have 
own scope. This is very handy, because sometimes people have problems with such things 
in other templates engines.

For example we need to block inside ``for`` loop::

    -- layout.mint
    @div.id(content)
        #for item in items:
            #loop_slot()

    -- photos.mint
    #base: layout.mint

    #def loop_slot():
        @p.class(title) {{ item.title }}
        @img.alt().src({{ item.image.path }})

For **mint** it is natural behavior. And ``item`` is just global variable for 
slot ``loop_slot``. But in this case better to provide ``item`` to slot obviosly.::

    -- layout.mint
    @div.id(content)
        #for item in items:
            #loop_slot(item)

    -- photos.mint
    #base: layout.mint

    #def loop_slot(item):
        @p.class(title) {{ item.title }}
        @img.alt().src({{ item.image.path }})



.. _utils:

-----
utils
-----

**mint** provides global variable ``utils`` which contains useful constants and helper 
functions.

Doctype declarations

- ``utils.DT_HTML_STRICT``
- ``utils.DT_HTML_TRANSITIONAL``
- ``utils.DT_XHTML_STRICT``
- ``utils.DT_XHTML_TRANSITIONAL``

Class ``mint.Markup`` is ``utils.markup`` (this is replacement for hack ``{{ var|safe }}``)

``utils.loop`` is helper function to use with ``for`` statement. It takes iterable 
object and returns tuple of item and special object that consist of useful info for each
iteration.::

    #for item, l in utils.loop(items):
        @a.href({{ item.url }})
            {{ item. title }} {{ (l.first, l.last, l.odd) }} {{ l.cycle('one', 'two', 'three') }}

In previouse example ``l.cycle('one', 'two', 'three')`` will return one of values provided
in sequence. It is handy to colorize tables.

That's all folks!
