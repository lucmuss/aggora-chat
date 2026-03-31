from django import template


register = template.Library()


@register.filter
def get_item(mapping, key):
    if not mapping:
        return 0
    return mapping.get(key, 0)


@register.filter
def split(value, separator):
    return value.split(separator)


@register.filter
def contains(items, key):
    if not items:
        return False
    return key in items


@register.filter
def pairs(data):
    """
    Groups a list into pairs.
    Example: ['a', 'b', 'c', 'd'] -> [('a', 'b'), ('c', 'd')]
    """
    it = iter(data)
    return zip(it, it)
