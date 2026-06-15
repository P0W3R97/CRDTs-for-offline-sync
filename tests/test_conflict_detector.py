import pytest
from crdt.medication_order import MedicationOrder
from crdt.conflict_detector import ConflictDetector


def setup_order():
    """Simulates the server writing the initial order."""
    order = MedicationOrder()
    order.patient_id.set("patient-001", replica_id="system")
    order.medication_name.set("Lisinopril", replica_id="system")
    order.dosage.set("10mg", replica_id="system")
    order.frequency.set("once daily", replica_id="system")
    order.route.set("oral", replica_id="system")
    order.status.set("active", replica_id="system")
    order.prescriber.set("Dr. Smith", replica_id="system")
    order.start_date.set("2026-06-01", replica_id="system")
    order.end_date.set("2026-06-30", replica_id="system")
    return order


def get_clock(order, field):
    return getattr(order, field).vector_clocks()[0]


def test_scan_no_conflicts():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.clinical_notes.add("Patient doing well")

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    records = detector.scan(merged)

    assert len(records) == 0


def test_scan_detects_single_conflict():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    records = detector.scan(merged)

    assert len(records) == 1
    assert records[0].field_name == "dosage"
    assert records[0].competing_values == {"15mg", "20mg"}


def test_scan_detects_multiple_conflicts():
    base_dosage_clock = get_clock(setup_order(), "dosage")
    base_frequency_clock = get_clock(setup_order(), "frequency")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_dosage_clock)
    nurse.frequency.set("twice daily", replica_id="nurse", vector_clock=base_frequency_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_dosage_clock)
    doctor.frequency.set("three times daily", replica_id="doctor", vector_clock=base_frequency_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    records = detector.scan(merged)

    assert len(records) == 2
    field_names = [r.field_name for r in records]
    assert "dosage" in field_names
    assert "frequency" in field_names


def test_scan_identical_concurrent_writes_no_conflict():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("15mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    records = detector.scan(merged)

    assert len(records) == 0


def test_scan_conflict_record_contains_replica_ids():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    records = detector.scan(merged)

    assert "nurse" in records[0].replica_ids
    assert "doctor" in records[0].replica_ids


def test_resolve_eliminates_conflict():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()

    assert merged.has_conflicts() == True

    detector.resolve(merged, "dosage", "15mg", resolver_id="reviewer")

    assert merged.has_conflicts() == False
    assert merged.dosage.value() == {"15mg"}


def test_resolve_clock_dominates_all_conflicting_clocks():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    resolution_clock = detector.resolve(merged, "dosage", "15mg", resolver_id="reviewer")

    # resolution clock must dominate both nurse and doctor clocks
    assert resolution_clock.get("nurse", 0) >= base_clock.get("nurse", 0)
    assert resolution_clock.get("doctor", 0) >= base_clock.get("doctor", 0)
    assert resolution_clock.get("reviewer", 0) >= 1


def test_resolve_stale_write_discarded():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    detector.resolve(merged, "dosage", "15mg", resolver_id="reviewer")

    # doctor tries to push stale value after resolution
    stale_doctor = setup_order()
    stale_doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    re_merged = merged.merge(stale_doctor)
    assert re_merged.has_conflicts() == False
    assert re_merged.dosage.value() == {"15mg"}


def test_gset_fields_not_scanned_for_conflicts():
    nurse = setup_order()
    nurse.clinical_notes.add("Note A")

    doctor = setup_order()
    doctor.clinical_notes.add("Note B")

    merged = nurse.merge(doctor)
    detector = ConflictDetector()
    records = detector.scan(merged)

    assert len(records) == 0