import requests
from crdt.medication_order import MedicationOrder

RELAY_URL = "http://54.196.235.160:8000/sync"

# Reset note: re-run main.py on EC2 first if you want a clean "10mg" base again

# Step 1: Nurse pulls current state
nurse_state = requests.get(RELAY_URL).json()
nurse_order = MedicationOrder.from_dict(nurse_state)
base_clock = nurse_order.dosage.vector_clocks()[0]

# Step 2: Doctor ALSO pulls the same base state (simulating concurrent offline edit)
doctor_state = requests.get(RELAY_URL).json()
doctor_order = MedicationOrder.from_dict(doctor_state)

# Step 3: Nurse edits offline
nurse_order.dosage.set("15mg", replica_id="nurse", vector_clock=base_clock)

# Step 4: Doctor edits offline, from the SAME base clock — concurrent, unaware of nurse
doctor_order.dosage.set("20mg", replica_id="doctor", vector_clock=base_clock)

# Step 5: Nurse syncs first
nurse_push = requests.post(RELAY_URL, json=nurse_order.to_dict())
print("After nurse syncs:")
print("Conflicts:", nurse_push.json()["conflicts"])
print("Dosage:", nurse_push.json()["merged_state"]["dosage"])

# Step 6: Doctor syncs second — this should now conflict with nurse's already-merged value
doctor_push = requests.post(RELAY_URL, json=doctor_order.to_dict())
print("\nAfter doctor syncs:")
print("Conflicts:", doctor_push.json()["conflicts"])
print("Dosage:", doctor_push.json()["merged_state"]["dosage"])