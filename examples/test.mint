@html
    @head
        @title {{ a }}
    @body
        // first div 
        @div.id(content)
            Text text text,
            text before {{ c }} and after
            {{ d }}
            \{{ obj_list[3:7].find() }}
            some more text
        @p.class({{ c }} title)
            @ul
                #for i in range(5):
                    #for y in range(i):
                        @li {{ i }} {{ y }} привет
