@a.href(< > " ' &).id(&) link
@a.href( &lt; &gt; &quot; &#39; &amp; < > " ' &) link
@a.href(< > " ' {{ utils.markup('<tag id="3 &amp;" />') }})
    {{ utils.markup('<tag id="3 &amp;" />') }} <tag id='3' />

@ul
    #for i, loop in utils.loop(range(9)):
        @li.class({{ loop.odd and 'odd' or '' }} {{ loop.cycle('one', 'two', 'three') }}) 
            {{ i }} {{ loop.index }} {{ loop.first }} {{ loop.last }}

@a.href(http://docs/?a=1&b=2) docs
