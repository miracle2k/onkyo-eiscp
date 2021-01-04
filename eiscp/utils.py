class ValueRange(object):
    """Some command values are defined as a range of possible
    values, such as from 1 to 100. We use a custom type to represen
    this.

    We used to use range() or xrange(), but a list is not hashable,
    and a generator can be exhausted after use.
    """
    def __init__(self, start, end):
        self.start = start
        self.end = end

        self._range = tuple(range(start, end + 1))

    def __contains__(self, value):
        return value in self._range


def format_nri_list(data):
    """Return NRI lists as dict with names or ids as the key."""
    if not data:
        return None
    info = {}
    for item in data:
        if item.get("name") is not None:
            key = item.pop("name")
        elif item.get("id") is not None:
            key = item.pop("id")
        else:
            return None
        info[key] = item
    return info
