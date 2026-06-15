from crdt.gset import GSet
from crdt.mv_register import MVRegister
from crdt.lww_register import LWWRegister


class MedicationOrder:
    def __init__(self):
        self.patient_id      = LWWRegister()
        self.medication_name = MVRegister()
        self.dosage          = MVRegister()
        self.frequency       = MVRegister()
        self.route           = MVRegister()
        self.status          = MVRegister()
        self.prescriber      = LWWRegister()
        self.start_date      = MVRegister()
        self.end_date        = MVRegister()
        self.clinical_notes  = GSet()
        self.bp_checks       = GSet()

    def merge(self, other):
        merged = MedicationOrder()
        merged.patient_id      = self.patient_id.merge(other.patient_id)
        merged.medication_name = self.medication_name.merge(other.medication_name)
        merged.dosage          = self.dosage.merge(other.dosage)
        merged.frequency       = self.frequency.merge(other.frequency)
        merged.route           = self.route.merge(other.route)
        merged.status          = self.status.merge(other.status)
        merged.prescriber      = self.prescriber.merge(other.prescriber)
        merged.start_date      = self.start_date.merge(other.start_date)
        merged.end_date        = self.end_date.merge(other.end_date)
        merged.clinical_notes  = self.clinical_notes.merge(other.clinical_notes)
        merged.bp_checks       = self.bp_checks.merge(other.bp_checks)
        return merged

    def conflicts(self):
        conflict_fields = []
        mv_fields = [
            "medication_name", "dosage", "frequency",
            "route", "status", "start_date", "end_date"
        ]
        for field in mv_fields:
            if getattr(self, field).has_conflict():
                conflict_fields.append(field)
        return conflict_fields

    def has_conflicts(self):
        return len(self.conflicts()) > 0

    def __eq__(self, other):
        return (
            self.patient_id      == other.patient_id      and
            self.medication_name == other.medication_name and
            self.dosage          == other.dosage          and
            self.frequency       == other.frequency       and
            self.route           == other.route           and
            self.status          == other.status          and
            self.prescriber      == other.prescriber      and
            self.start_date      == other.start_date      and
            self.end_date        == other.end_date        and
            self.clinical_notes  == other.clinical_notes  and
            self.bp_checks       == other.bp_checks
        )

    def __repr__(self):
        return (
            f"MedicationOrder(\n"
            f"  patient_id={self.patient_id.value()},\n"
            f"  medication_name={self.medication_name.value()},\n"
            f"  dosage={self.dosage.value()},\n"
            f"  frequency={self.frequency.value()},\n"
            f"  route={self.route.value()},\n"
            f"  status={self.status.value()},\n"
            f"  prescriber={self.prescriber.value()},\n"
            f"  start_date={self.start_date.value()},\n"
            f"  end_date={self.end_date.value()},\n"
            f"  clinical_notes={self.clinical_notes.value()},\n"
            f"  bp_checks={self.bp_checks.value()}\n"
            f")"
        )