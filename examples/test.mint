{{ utils.DT_HTML5 }}
@html
    @head
        @title {{ a }}
    @body
        -- first div
        @div.id(content)
            #def content(arg, arg1='arg1'):
                {{ arg1 }}
                @p.class(slot)
                    Slot text {{ arg }}
                @b
            #content(a)
            Text text text, <b>text</b>
            text before {{ c }} and after
            {{ d }}
            \{{ obj_list[3:7].find() }}
            some more text
        @p.class({{ c }} title)
            @ul
                #for i in range(1, 5):
                    #for y in range(i):
                       @li {{ i }} {{ y }} привет
        #if a == 'd':
            @p {{ a }}
        #elif c == 'c':
            @p {{ c }}
            #if a == 'a':
                @p {{ a }}
            #elif a == 'b':
                @p {{ b }}
            #else:
                @p nothing
        #else:
            @p {{ b }}
        @div.class(after).id(sdf)
