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
