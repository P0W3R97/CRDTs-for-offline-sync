from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class ConflictRecord:
    field_name: str
    competing_values: set
    replica_ids: list
    timestamp: float = field(default_factory=time.time)

    def __repr__(self):
        return (
            f"ConflictRecord(\n"
            f"  field={self.field_name},\n"
            f"  values={self.competing_values},\n"
            f"  replicas={self.replica_ids},\n"
            f"  timestamp={self.timestamp}\n"
            f")"
        )


class ConflictDetector:
    MV_FIELDS = [
        "medication_name", "dosage", "frequency",
        "route", "status", "start_date", "end_date"
    ]

    def scan(self, order):
        """Scan a merged MedicationOrder and return a list of ConflictRecords."""
        records = []
        for field_name in self.MV_FIELDS:
            mv = getattr(order, field_name)
            if mv.has_conflict():
                records.append(ConflictRecord(
                    field_name=field_name,
                    competing_values=mv.value(),
                    replica_ids=self._get_replica_ids(mv)
                ))
        return records

    def resolve(self, order, field_name, chosen_value, resolver_id="reviewer"):
        """
        Resolve a conflict on a given field by writing a new value
        with a clock that dominates all conflicting clocks.
        """
        mv = getattr(order, field_name)

        # merge all conflicting clocks together
        merged_clock = {}
        for vc in mv.vector_clocks():
            for replica, counter in vc.items():
                merged_clock[replica] = max(merged_clock.get(replica, 0), counter)

        # increment the resolver's counter so the new clock dominates all
        merged_clock[resolver_id] = merged_clock.get(resolver_id, 0) + 1

        # write the chosen value with the dominating clock
        mv._values = []
        mv.set(chosen_value, replica_id=resolver_id, vector_clock=merged_clock)

        return merged_clock

    def _get_replica_ids(self, mv):
        """Extract replica IDs from all concurrent vector clocks."""
        replica_ids = []
        for vc in mv.vector_clocks():
            for replica_id in vc:
                if replica_id not in replica_ids:
                    replica_ids.append(replica_id)
        return replica_ids