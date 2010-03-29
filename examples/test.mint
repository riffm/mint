@html
    @head
        @title {{ title }}
    @body
        @div.id()
            Text text text,
            text before {{ content['first'] }} and after
            {{ obj_list[3:7].find() }}
            \{{ obj_list[3:7].find() }}
            some more text
