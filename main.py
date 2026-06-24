from fastapi import FastAPI
from crdt.medication_order import MedicationOrder
from crdt.conflict_detector import ConflictDetector

app = FastAPI()

# The relay's single source of truth — starts as a fresh order.
# In a real system this would be created once per patient order.
server_order = MedicationOrder()
server_order.patient_id.set("patient-001", replica_id="system")
server_order.medication_name.set("Lisinopril", replica_id="system")
server_order.dosage.set("10mg", replica_id="system")
server_order.frequency.set("once daily", replica_id="system")
server_order.route.set("oral", replica_id="system")
server_order.status.set("active", replica_id="system")
server_order.prescriber.set("Dr. Smith", replica_id="system")
server_order.start_date.set("2026-06-01", replica_id="system")
server_order.end_date.set("2026-06-30", replica_id="system")

detector = ConflictDetector()


@app.get("/sync")
def get_state():
    """Client pulls the current merged state from the relay."""
    return server_order.to_dict()


@app.post("/sync")
def post_state(client_order: dict):
    """Client pushes their local state. Relay merges it in."""
    global server_order
    incoming = MedicationOrder.from_dict(client_order)
    server_order = server_order.merge(incoming)

    conflicts = detector.scan(server_order)
    return {
        "merged_state": server_order.to_dict(),
        "conflicts": [c.field_name for c in conflicts]
    }