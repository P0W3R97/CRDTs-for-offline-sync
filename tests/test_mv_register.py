import pytest
from crdt.mv_register import MVRegister


def test_set_and_value():
    r = MVRegister()
    r.set("15mg", replica_id="physician", timestamp=1000)
    assert "15mg" in r.value()


def test_no_conflict_single_replica():
    r = MVRegister()
    r.set("15mg", replica_id="physician", timestamp=1000)
    assert r.has_conflict() == False


def test_conflict_detected():
    a = MVRegister()
    a.set("15mg", replica_id="physician", timestamp=1000)

    b = MVRegister()
    b.set("20mg", replica_id="nurse", timestamp=1001)

    merged = a.merge(b)
    assert merged.has_conflict() == True


def test_conflict_preserves_both_values():
    a = MVRegister()
    a.set("15mg", replica_id="physician", timestamp=1000)

    b = MVRegister()
    b.set("20mg", replica_id="nurse", timestamp=1001)

    merged = a.merge(b)
    assert merged.value() == {"15mg", "20mg"}


def test_merge_commutativity():
    a = MVRegister()
    a.set("15mg", replica_id="physician", timestamp=1000)

    b = MVRegister()
    b.set("20mg", replica_id="nurse", timestamp=1001)

    assert a.merge(b) == b.merge(a)


def test_merge_associativity():
    a = MVRegister()
    a.set("15mg", replica_id="physician", timestamp=1000)

    b = MVRegister()
    b.set("20mg", replica_id="nurse", timestamp=1001)

    c = MVRegister()
    c.set("25mg", replica_id="pharmacist", timestamp=1002)

    assert a.merge(b).merge(c) == a.merge(b.merge(c))


def test_merge_idempotency():
    a = MVRegister()
    a.set("15mg", replica_id="physician", timestamp=1000)
    assert a.merge(a) == a


def test_same_replica_keeps_latest():
    a = MVRegister()
    a.set("15mg", replica_id="physician", timestamp=1000)

    b = MVRegister()
    b.set("20mg", replica_id="physician", timestamp=1001)

    merged = a.merge(b)
    assert merged.value() == {"20mg"}
    assert merged.has_conflict() == False