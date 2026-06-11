import pytest
from crdt.lww_register import LWWRegister


def test_set_and_value():
    r = LWWRegister()
    r.set("Dr. Smith", replica_id="physician", timestamp=1000)
    assert r.value() == "Dr. Smith"


def test_merge_keeps_latest():
    a = LWWRegister()
    a.set("Dr. Smith", replica_id="physician", timestamp=1000)

    b = LWWRegister()
    b.set("Dr. Jones", replica_id="nurse", timestamp=1001)

    merged = a.merge(b)
    assert merged.value() == "Dr. Jones"


def test_merge_keeps_latest_reversed():
    a = LWWRegister()
    a.set("Dr. Smith", replica_id="physician", timestamp=1001)

    b = LWWRegister()
    b.set("Dr. Jones", replica_id="nurse", timestamp=1000)

    merged = a.merge(b)
    assert merged.value() == "Dr. Smith"


def test_merge_commutativity():
    a = LWWRegister()
    a.set("Dr. Smith", replica_id="physician", timestamp=1000)

    b = LWWRegister()
    b.set("Dr. Jones", replica_id="nurse", timestamp=1001)

    assert a.merge(b) == b.merge(a)


def test_merge_associativity():
    a = LWWRegister()
    a.set("Dr. Smith", replica_id="physician", timestamp=1000)

    b = LWWRegister()
    b.set("Dr. Jones", replica_id="nurse", timestamp=1001)

    c = LWWRegister()
    c.set("Dr. Patel", replica_id="pharmacist", timestamp=1002)

    assert a.merge(b).merge(c) == a.merge(b.merge(c))


def test_merge_idempotency():
    a = LWWRegister()
    a.set("Dr. Smith", replica_id="physician", timestamp=1000)
    assert a.merge(a) == a


def test_empty_merge():
    a = LWWRegister()
    a.set("Dr. Smith", replica_id="physician", timestamp=1000)

    b = LWWRegister()

    merged = a.merge(b)
    assert merged.value() == "Dr. Smith"