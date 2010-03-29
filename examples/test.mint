@html
    @head
        @title {{ title }}
    @body
        // first div 
        @div.class( content {{ expr }} )
            Text text text,
            text before {{ content['first'] }} and after
            {{ obj_list[3:7].find() }}
            \{{ obj_list[3:7].find() }}
            some more text
