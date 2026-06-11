import uuid


class MVRegister:
    def __init__(self):
        # stores {replica_id: (value, timestamp)}
        self._data = {}

    def set(self, value, replica_id=None, timestamp=None):
        rid = replica_id or str(uuid.uuid4())
        ts = timestamp or __import__("time").time()
        self._data[rid] = (value, ts)

    def merge(self, other):
        merged = MVRegister()
        all_replicas = set(self._data) | set(other._data)
        for rid in all_replicas:
            if rid in self._data and rid in other._data:
                # keep the one with the higher timestamp
                merged._data[rid] = max(
                    self._data[rid],
                    other._data[rid],
                    key=lambda x: x[1]
                )
            elif rid in self._data:
                merged._data[rid] = self._data[rid]
            else:
                merged._data[rid] = other._data[rid]
        return merged

    def value(self):
        return set(v for v, _ in self._data.values())

    def has_conflict(self):
        return len(self._data) > 1

    def __eq__(self, other):
        return self._data == other._data

    def __repr__(self):
        return f"MVRegister({self._data})"