class GSet:
    def __init__(self, items=None):
        if items:
            self._data = set(items)
        else:
            self._data = set()

    def add(self, item):
        self._data.add(item)

    def merge(self, other):
        merged = GSet()
        merged._data = self._data | other._data
        return merged

    def value(self):
        return frozenset(self._data)

    def __eq__(self, other):
        return self._data == other._data

    def __repr__(self):
        return f"GSet({self._data})"
    
    def to_dict(self):
        return {"type": "GSet", "items": list(self._data)}

    @staticmethod
    def from_dict(data):
        return GSet(items=data["items"])