class MVRegister:
    def __init__(self):
        # list of (value, vector_clock) pairs
        # each entry represents a concurrent write
        self._values = []

    def set(self, value, replica_id, vector_clock=None):
        if vector_clock is None:
            # start from an empty clock and increment this replica
            vector_clock = {}
        
        # increment this replica's counter in the clock
        new_clock = dict(vector_clock)
        new_clock[replica_id] = new_clock.get(replica_id, 0) + 1

        # remove any existing values whose clocks are dominated by the new clock
        self._values = [
            (v, vc) for v, vc in self._values
            if not self._dominates(new_clock, vc)
        ]

        # add the new value
        self._values.append((value, new_clock))

    def merge(self, other):
        merged = MVRegister()
        combined = self._values + other._values

        # keep only values whose clocks are not dominated by any other clock
        merged._values = [
            (v, vc) for v, vc in combined
            if not any(
                self._dominates(other_vc, vc) and (other_v, other_vc) != (v, vc)
                for other_v, other_vc in combined
            )
        ]
        return merged

    def value(self):
        return set(v for v, _ in self._values)

    def has_conflict(self):
        if len(self._values) <= 1:
            return False
        return len(set(v for v, _ in self._values)) > 1

    def vector_clocks(self):
        return [vc for _, vc in self._values]

    @staticmethod
    def _dominates(vc_a, vc_b):
        # vc_a dominates vc_b if every key in vc_b has a counter <= vc_a
        all_keys = set(vc_a) | set(vc_b)
        return all(vc_a.get(k, 0) >= vc_b.get(k, 0) for k in all_keys)

    def __eq__(self, other):
        # order doesn't matter, compare as sets of (value, frozenset) pairs
        def normalize(values):
            return set((v, frozenset(vc.items())) for v, vc in values)
        return normalize(self._values) == normalize(other._values)

    def __repr__(self):
        return f"MVRegister({self._values})"