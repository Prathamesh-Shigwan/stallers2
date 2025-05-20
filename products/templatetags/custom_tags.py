from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def floatval(value):
    try:
        return float(value)
    except:
        return 0

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except:
        return 0

@register.filter
def discount_percent(old_price, new_price):
    try:
        old = float(old_price)
        new = float(new_price)
        if old > new:
            return round((old - new) / old * 100)
    except:
        return 0
    return 0



