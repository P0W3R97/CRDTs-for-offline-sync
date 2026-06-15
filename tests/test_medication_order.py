import pytest
from crdt.medication_order import MedicationOrder


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
    """Helper to extract the current vector clock from an MVRegister field."""
    return getattr(order, field).vector_clocks()[0]


def test_safe_merge_no_conflict():
    # Nurse edits dosage, doctor adds a note — different fields, no conflict
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.clinical_notes.add("Patient showing signs of improvement")

    merged = nurse.merge(doctor)
    assert "15mg" in merged.dosage.value()
    assert "Patient showing signs of improvement" in merged.clinical_notes.value()
    assert merged.has_conflicts() == False


def test_concurrent_dosage_conflict():
    # Nurse and doctor both edit dosage offline from same base
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    assert merged.has_conflicts() == True
    assert "dosage" in merged.conflicts()
    assert merged.dosage.value() == {"15mg", "20mg"}


def test_sequential_update_no_conflict():
    # Doctor edits dosage, nurse sees doctor's edit and updates on top
    base_clock = get_clock(setup_order(), "dosage")

    doctor = setup_order()
    doctor.dosage.set("15mg", replica_id="doctor", vector_clock=base_clock)

    # Nurse syncs and sees doctor's clock
    doctor_clock = doctor.dosage.vector_clocks()[0]

    nurse = setup_order()
    nurse.dosage.set("20mg", replica_id="nurse", vector_clock=doctor_clock)

    merged = doctor.merge(nurse)
    assert merged.has_conflicts() == False
    assert merged.dosage.value() == {"20mg"}


def test_gset_fields_never_conflict():
    # Two nurses add different notes offline
    nurse_a = setup_order()
    nurse_a.clinical_notes.add("Note from nurse A")

    nurse_b = setup_order()
    nurse_b.clinical_notes.add("Note from nurse B")

    merged = nurse_a.merge(nurse_b)
    assert "Note from nurse A" in merged.clinical_notes.value()
    assert "Note from nurse B" in merged.clinical_notes.value()
    assert merged.has_conflicts() == False


def test_identical_concurrent_writes_no_conflict():
    # Nurse and doctor both write the same dosage concurrently
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("15mg", replica_id="doctor", vector_clock=base_clock)

    merged = nurse.merge(doctor)
    assert merged.has_conflicts() == False
    assert merged.dosage.value() == {"15mg"}


def test_multiple_field_conflicts():
    # Nurse and doctor both edit dosage and frequency offline
    base_dosage_clock = get_clock(setup_order(), "dosage")
    base_frequency_clock = get_clock(setup_order(), "frequency")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_dosage_clock)
    nurse.frequency.set("twice daily", replica_id="nurse", vector_clock=base_frequency_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_dosage_clock)
    doctor.frequency.set("three times daily", replica_id="doctor", vector_clock=base_frequency_clock)

    merged = nurse.merge(doctor)
    assert "dosage" in merged.conflicts()
    assert "frequency" in merged.conflicts()
    assert len(merged.conflicts()) == 2


def test_mixed_conflict_and_safe_merge():
    # Nurse edits dosage, doctor edits frequency and adds a note
    base_dosage_clock = get_clock(setup_order(), "dosage")
    base_frequency_clock = get_clock(setup_order(), "frequency")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_dosage_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_dosage_clock)
    doctor.frequency.set("twice daily", replica_id="doctor", vector_clock=base_frequency_clock)
    doctor.clinical_notes.add("Patient tolerating medication well")

    merged = nurse.merge(doctor)
    assert "dosage" in merged.conflicts()
    assert "frequency" not in merged.conflicts()
    assert "Patient tolerating medication well" in merged.clinical_notes.value()
    assert len(merged.conflicts()) == 1


def test_merge_commutativity():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    doctor = setup_order()
    doctor.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

    assert nurse.merge(doctor) == doctor.merge(nurse)


def test_merge_associativity():
    base_dosage_clock = get_clock(setup_order(), "dosage")
    base_frequency_clock = get_clock(setup_order(), "frequency")
    base_route_clock = get_clock(setup_order(), "route")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_dosage_clock)

    doctor = setup_order()
    doctor.frequency.set("twice daily", replica_id="doctor", vector_clock=base_frequency_clock)

    pharmacist = setup_order()
    pharmacist.route.set("IV", replica_id="pharmacist", vector_clock=base_route_clock)

    assert nurse.merge(doctor).merge(pharmacist) == nurse.merge(doctor.merge(pharmacist))


def test_merge_idempotency():
    base_clock = get_clock(setup_order(), "dosage")

    nurse = setup_order()
    nurse.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

    assert nurse.merge(nurse) == nurse


def test_prescriber_lww_no_conflict():
    # Prescriber uses LWW — latest timestamp wins
    nurse = setup_order()
    nurse.prescriber.set("Dr. Smith", replica_id="nurse", timestamp=1001)

    doctor = setup_order()
    doctor.prescriber.set("Dr. Jones", replica_id="doctor", timestamp=1002)

    merged = nurse.merge(doctor)
    assert merged.prescriber.value() == "Dr. Jones"
    assert merged.has_conflicts() == False