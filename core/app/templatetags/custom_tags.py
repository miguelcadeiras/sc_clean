from django import template

register = template.Library()

@register.filter
def get_key(value, arg):
    if arg in value:
        return value[arg]
    else:
        return ''

@register.filter
def getList_value(list,value):
    # print(len(list),list)
    if len(list) > int(value):
        # print(value)
        return list[value]
    else:
        return ''