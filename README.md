# CRDTs-for-offline-sync
A Python implementation of Conflict-Free Replicated Data Types (CRDTs) for safe offline synchronization of medication orders. The system automatically merges concurrent edits where safe, and flags clinically significant conflicts for human review.

CRDTs-for-offline-sync/
  crdt/
    __init__.py
    gset.py
    mv_register.py
    lww_register.py
  tests/
    __init__.py
    test_gset.py
    test_mv_register.py
    test_lww_register.py
