"""
client_demo.py

Runs six test scenarios against the CRDT medication-order sync relay.
Each scenario resets the relay to its baseline state first, so scenarios
are fully independent and can be run in any order or individually.

Usage:
    python client_demo.py
"""

import requests
from crdt.medication_order import MedicationOrder

RELAY_HOST = "http://34.228.17.130:8000"   # <-- update this everytime you want to run with a new EC2 instance
SYNC_URL = f"{RELAY_HOST}/sync"
RESET_URL = f"{RELAY_HOST}/reset"


def reset_relay():
    """Resets the relay to its baseline state before a scenario runs."""
    resp = requests.post(RESET_URL)
    resp.raise_for_status()


def pull_state():
    """Pulls the current relay state as a MedicationOrder."""
    resp = requests.get(SYNC_URL)
    resp.raise_for_status()
    return MedicationOrder.from_dict(resp.json())


def push_state(order):
    """Pushes a MedicationOrder to the relay and returns the JSON response."""
    resp = requests.post(SYNC_URL, json=order.to_dict())
    resp.raise_for_status()
    return resp.json()


def base_clock_for(order, field_name):
    """Returns the first vector clock currently attached to a field.
    Used so a simulated edit starts from the same causal point as the
    server's current value (i.e. 'I saw this version before editing')."""
    field = getattr(order, field_name)
    clocks = field.vector_clocks()
    return clocks[0] if clocks else None


def print_result(label, result):
    print(f"\n{label}")
    print(f"  Conflicts: {result['conflicts']}")
    for field in result["conflicts"]:
        print(f"  {field}: {result['merged_state'][field]}")


# ---------------------------------------------------------------------------
# Scenario 1: Three-way concurrency
# Nurse, doctor, and pharmacist all edit dosage offline from the same base
# clock, then sync one at a time. Checks whether MV-Register correctly
# surfaces all three concurrent values, not just two.
# ---------------------------------------------------------------------------
def scenario_1_three_way_concurrency():
    print("\n" + "=" * 70)
    print("SCENARIO 1: Three-way concurrent dosage edit (nurse/doctor/pharmacist)")
    print("=" * 70)
    reset_relay()

    server_state = pull_state()
    base_clock = base_clock_for(server_state, "dosage")

    nurse_order = pull_state()
    nurse_order.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)
    result = push_state(nurse_order)
    print_result("After nurse syncs:", result)

    doctor_order = pull_state()
    # doctor still edits from the ORIGINAL base clock, not the nurse's,
    # to keep this a genuine 3-way concurrent edit rather than sequential
    doctor_order.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)
    result = push_state(doctor_order)
    print_result("After doctor syncs:", result)

    pharmacist_order = pull_state()
    pharmacist_order.dosage.set("12mg", replica_id="pharmacist", vector_clock=base_clock)
    result = push_state(pharmacist_order)
    print_result("After pharmacist syncs:", result)

    print("\nExpectation: all three values (15mg, 20mg, 12mg) should be present")
    print("in the merged dosage field, and 'dosage' should be listed as a conflict.")


# ---------------------------------------------------------------------------
# Scenario 2: Sequential (non-concurrent) edits
# Doctor edits dosage and syncs. Nurse then pulls the NEW state and edits
# from there. Since the nurse's edit causally descends from the doctor's,
# this should auto-merge with NO conflict.
# ---------------------------------------------------------------------------
def scenario_2_sequential_edits():
    print("\n" + "=" * 70)
    print("SCENARIO 2: Sequential edits (doctor syncs, then nurse edits the result)")
    print("=" * 70)
    reset_relay()

    doctor_order = pull_state()
    base_clock = base_clock_for(doctor_order, "dosage")
    doctor_order.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)
    result = push_state(doctor_order)
    print_result("After doctor syncs:", result)

    # Nurse pulls the NEW state (which includes the doctor's clock),
    # so her edit causally descends from his.
    nurse_order = pull_state()
    nurse_base_clock = base_clock_for(nurse_order, "dosage")
    nurse_order.dosage.set("22mg", replica_id="nurse", vector_clock=nurse_base_clock)
    result = push_state(nurse_order)
    print_result("After nurse syncs (based on doctor's update):", result)

    print("\nExpectation: NO conflict. Final dosage should be a single value, 22mg,")
    print("since the nurse's edit happened-after the doctor's in causal order.")


# ---------------------------------------------------------------------------
# Scenario 3: G-Set field test (clinical_notes)
# Nurse and doctor concurrently add DIFFERENT notes offline. Since G-Set
# merge is just set union, this should merge cleanly with no conflict
# concept at all (ConflictDetector only scans MV_FIELDS).
# ---------------------------------------------------------------------------
def scenario_3_gset_notes():
    print("\n" + "=" * 70)
    print("SCENARIO 3: Concurrent G-Set edits (clinical_notes)")
    print("=" * 70)
    reset_relay()

    nurse_order = pull_state()
    nurse_order.clinical_notes.add("Patient reports mild nausea after dose.")
    result = push_state(nurse_order)
    print(f"\nAfter nurse syncs: clinical_notes = {result['merged_state']['clinical_notes']}")

    doctor_order = pull_state()
    doctor_order.clinical_notes.add("Reviewed chart, no contraindications noted.")
    result = push_state(doctor_order)
    print(f"\nAfter doctor syncs: clinical_notes = {result['merged_state']['clinical_notes']}")

    print("\nExpectation: both notes present in clinical_notes (set union),")
    print("'clinical_notes' never appears in the conflicts list (G-Set is not")
    print("scanned for conflicts — only MV_FIELDS are).")


# ---------------------------------------------------------------------------
# Scenario 4: Status field conflict
# Pharmacist approves offline, doctor rejects offline, from the same base
# clock. Mirrors the dosage test structurally, but on a different field,
# to confirm the conflict-detection behavior generalizes across fields.
# ---------------------------------------------------------------------------
def scenario_4_status_conflict():
    print("\n" + "=" * 70)
    print("SCENARIO 4: Status conflict (pharmacist approves vs. doctor rejects)")
    print("=" * 70)
    reset_relay()

    server_state = pull_state()
    base_clock = base_clock_for(server_state, "status")

    pharmacist_order = pull_state()
    pharmacist_order.status.set("approved", replica_id="pharmacist", vector_clock=base_clock)
    result = push_state(pharmacist_order)
    print_result("After pharmacist syncs:", result)

    doctor_order = pull_state()
    doctor_order.status.set("rejected", replica_id="doctor", vector_clock=base_clock)
    result = push_state(doctor_order)
    print_result("After doctor syncs:", result)

    print("\nExpectation: 'status' listed as a conflict, with both 'approved'")
    print("and 'rejected' surfaced in the merged state.")


# ---------------------------------------------------------------------------
# Scenario 5: Same-value concurrent edit
# Nurse and doctor independently set dosage to the SAME value (15mg) from
# the same base clock. Tests whether has_conflict() correctly recognizes
# this as non-conflicting, since it checks distinct *values*, not the
# number of concurrent writes.
# ---------------------------------------------------------------------------
def scenario_5_same_value_concurrent():
    print("\n" + "=" * 70)
    print("SCENARIO 5: Same-value concurrent edit (nurse and doctor both set 15mg)")
    print("=" * 70)
    reset_relay()

    server_state = pull_state()
    base_clock = base_clock_for(server_state, "dosage")

    nurse_order = pull_state()
    nurse_order.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)
    result = push_state(nurse_order)
    print_result("After nurse syncs:", result)

    doctor_order = pull_state()
    doctor_order.dosage.set("15mg", replica_id="doctor", vector_clock=base_clock)
    result = push_state(doctor_order)
    print(f"\nAfter doctor syncs:")
    print(f"  Conflicts: {result['conflicts']}")
    print(f"  dosage: {result['merged_state']['dosage']}")

    print("\nNote: both writes are genuinely concurrent (neither clock dominates")
    print("the other), so internally there are two distinct (value, clock) entries.")
    print("But has_conflict() checks DISTINCT VALUES, not entry count, so since")
    print("both entries equal '15mg', this should NOT appear in the conflicts list")
    print("— even though two independent concurrent writes did occur. This is a")
    print("deliberate design choice: no clinical ambiguity, so no review needed.")


# ---------------------------------------------------------------------------
# Scenario 6: Convergence / order-independence check
# Push the same two concurrent edits in reverse order (doctor first, then
# nurse) and confirm the final merged state matches Scenario 1's dosage
# test regardless of arrival order — the core convergence guarantee.
# ---------------------------------------------------------------------------
def scenario_6_convergence_check():
    print("\n" + "=" * 70)
    print("SCENARIO 6: Convergence check (same edits, reversed sync order)")
    print("=" * 70)
    reset_relay()

    server_state = pull_state()
    base_clock = base_clock_for(server_state, "dosage")

    # Doctor syncs FIRST this time (reverse of the original dosage test)
    doctor_order = pull_state()
    doctor_order.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)
    result = push_state(doctor_order)
    print_result("After doctor syncs (first):", result)

    nurse_order = pull_state()
    nurse_order.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)
    result = push_state(nurse_order)
    print_result("After nurse syncs (second):", result)

    final_values = set(result["merged_state"]["dosage"]["values"][i]["value"]
                        for i in range(len(result["merged_state"]["dosage"]["values"])))

    print(f"\nFinal merged dosage values: {final_values}")
    print("Expectation: {'15mg', '20mg'} regardless of sync order —")
    print("this matches the original test's result with order reversed,")
    print("demonstrating order-independent convergence.")


if __name__ == "__main__":
    scenario_1_three_way_concurrency()
    scenario_2_sequential_edits()
    scenario_3_gset_notes()
    scenario_4_status_conflict()
    scenario_5_same_value_concurrent()
    scenario_6_convergence_check()