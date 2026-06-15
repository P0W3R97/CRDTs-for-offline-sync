import pytest
from crdt.mv_register import MVRegister


def test_set_and_value():
    r = MVRegister()
    r.set("15mg", replica_id="physician")
    assert "15mg" in r.value()


def test_no_conflict_single_replica():
    r = MVRegister()
    r.set("15mg", replica_id="physician")
    assert r.has_conflict() == False


def test_sequential_update_no_conflict():
    # Physician updates dosage twice — second write dominates first
    r = MVRegister()
    r.set("10mg", replica_id="system")
    clock_after_first = r.vector_clocks()[0]
    r.set("15mg", replica_id="physician", vector_clock=clock_after_first)
    assert r.has_conflict() == False
    assert r.value() == {"15mg"}


def test_concurrent_writes_conflict():
    # Physician and resident both write from the same base — real conflict
    base = MVRegister()
    base.set("10mg", replica_id="system")
    base_clock = base.vector_clocks()[0]

    physician = MVRegister()
    physician.set("10mg", replica_id="system")
    physician.set("15mg", replica_id="physician", vector_clock=base_clock)

    resident = MVRegister()
    resident.set("10mg", replica_id="system")
    resident.set("20mg", replica_id="resident", vector_clock=base_clock)

    merged = physician.merge(resident)
    assert merged.has_conflict() == True
    assert merged.value() == {"15mg", "20mg"}


def test_conflict_preserves_both_values():
    base_clock = {"system": 1}

    physician = MVRegister()
    physician.set("15mg", replica_id="physician", vector_clock=base_clock)

    resident = MVRegister()
    resident.set("20mg", replica_id="resident", vector_clock=base_clock)

    merged = physician.merge(resident)
    assert merged.value() == {"15mg", "20mg"}


def test_merge_commutativity():
    base_clock = {"system": 1}

    a = MVRegister()
    a.set("15mg", replica_id="physician", vector_clock=base_clock)

    b = MVRegister()
    b.set("20mg", replica_id="nurse", vector_clock=base_clock)

    assert a.merge(b) == b.merge(a)


def test_merge_associativity():
    base_clock = {"system": 1}

    a = MVRegister()
    a.set("15mg", replica_id="physician", vector_clock=base_clock)

    b = MVRegister()
    b.set("20mg", replica_id="nurse", vector_clock=base_clock)

    c = MVRegister()
    c.set("25mg", replica_id="pharmacist", vector_clock=base_clock)

    assert a.merge(b).merge(c) == a.merge(b.merge(c))


def test_merge_idempotency():
    a = MVRegister()
    a.set("15mg", replica_id="physician")
    assert a.merge(a) == a


def test_sequential_update_after_sync():
    # Nurse sees doctor's write, then updates — not a conflict
    doctor = MVRegister()
    doctor.set("10mg", replica_id="system")
    doctor.set("15mg", replica_id="doctor", vector_clock={"system": 1})

    # Nurse syncs and sees doctor's clock
    doctor_clock = doctor.vector_clocks()[0]

    nurse = MVRegister()
    nurse.set("10mg", replica_id="system")
    nurse.set("20mg", replica_id="nurse", vector_clock=doctor_clock)

    merged = doctor.merge(nurse)
    assert merged.has_conflict() == False
    assert merged.value() == {"20mg"}

def test_identical_concurrent_writes_no_conflict():
    # Both replicas write the same value concurrently — not a conflict
    base_clock = {"system": 1}

    a = MVRegister()
    a.set("15mg", replica_id="nurse", vector_clock=base_clock)

    b = MVRegister()
    b.set("15mg", replica_id="doctor", vector_clock=base_clock)

    merged = a.merge(b)
    assert merged.has_conflict() == False
    assert merged.value() == {"15mg"}