html:
    head:
        title: {{ title }}
    body:
        div:
            Text text text,
            text before {{ content['first'] }} and after
            {{ obj_list[3:7].find() }}
