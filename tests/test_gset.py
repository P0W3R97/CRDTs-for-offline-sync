import pytest
from crdt.gset import GSet


def test_add():
    g = GSet()
    g.add("note_1")
    assert "note_1" in g.value()


def test_merge_commutativity():
    # a.merge(b) == b.merge(a)
    a = GSet(["note_1", "note_2"])
    b = GSet(["note_2", "note_3"])
    assert a.merge(b) == b.merge(a)


def test_merge_associativity():
    # (a.merge(b)).merge(c) == a.merge(b.merge(c))
    a = GSet(["note_1"])
    b = GSet(["note_2"])
    c = GSet(["note_3"])
    assert a.merge(b).merge(c) == a.merge(b.merge(c))


def test_merge_idempotency():
    # a.merge(a) == a
    a = GSet(["note_1", "note_2"])
    assert a.merge(a) == a


def test_merge_preserves_all_elements():
    a = GSet(["note_1", "note_2"])
    b = GSet(["note_3"])
    merged = a.merge(b)
    assert merged.value() == frozenset(["note_1", "note_2", "note_3"])


def test_no_duplicates():
    a = GSet(["note_1"])
    b = GSet(["note_1"])
    merged = a.merge(b)
    assert len(merged.value()) == 1