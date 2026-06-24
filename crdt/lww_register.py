import uuid
import time


class LWWRegister:
    def __init__(self):
        self._value = None
        self._timestamp = -1
        self._replica_id = None

    def set(self, value, replica_id=None, timestamp=None):
        self._value = value
        self._timestamp = timestamp or time.time()
        self._replica_id = replica_id or str(uuid.uuid4())

    def merge(self, other):
        merged = LWWRegister()
        if other._timestamp > self._timestamp:
            merged._value = other._value
            merged._timestamp = other._timestamp
            merged._replica_id = other._replica_id
        else:
            merged._value = self._value
            merged._timestamp = self._timestamp
            merged._replica_id = self._replica_id
        return merged

    def value(self):
        return self._value

    def __eq__(self, other):
        return (
            self._value == other._value and
            self._timestamp == other._timestamp and
            self._replica_id == other._replica_id
        )

    def __repr__(self):
        return f"LWWRegister(value={self._value}, ts={self._timestamp}, replica={self._replica_id})"
    
    def to_dict(self):
        return {
            "type": "LWWRegister",
            "value": self._value,
            "timestamp": self._timestamp,
            "replica_id": self._replica_id
        }
    
    @staticmethod
    def from_dict(data):
        reg = LWWRegister()
        reg._value = data["value"]
        reg._timestamp = data["timestamp"]
        reg._replica_id = data["replica_id"]
        return reg