# CRDTs-for-offline-sync
Local-first medication order sync using Conflict-Free Replicated Data Types. Automatic merging where safe, human review where it matters.

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
