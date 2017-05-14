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

        self._range = tuple(range(start, end))

    def __contains__(self, value):
        return value in self._range