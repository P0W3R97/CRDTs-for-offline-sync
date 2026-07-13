import { useState, useEffect, useCallback } from "react";

// ─── Config ───────────────────────────────────────────────────────────────────
const RELAY_URL = "http://54.196.217.13:8000"; // <-- update this

// ─── CRDT helpers (mirrors Python MVRegister / GSet logic in JS) ──────────────

/**
 * Given an MVRegister's values array (from server JSON), return the first
 * vector clock. Used as the base clock when a replica edits a field.
 */
function getBaseClock(mvRegisterValues) {
  if (!mvRegisterValues || mvRegisterValues.length === 0) return {};
  return mvRegisterValues[0].clock;
}

/**
 * Increment a replica's counter in a vector clock, returning a new clock.
 * This mirrors MVRegister.set()'s new_clock logic in Python.
 */
function incrementClock(baseClock, replicaId) {
  const newClock = { ...baseClock };
  newClock[replicaId] = (newClock[replicaId] || 0) + 1;
  return newClock;
}

function mergeAllClocks(mvRegisterValues) {
  const merged = {};
  for (const { clock } of mvRegisterValues) {
    for (const [replica, count] of Object.entries(clock)) {
      merged[replica] = Math.max(merged[replica] || 0, count);
    }
  }
  return merged;
}

/**
 * Build a local MedicationOrder dict in the relay's JSON format,
 * applying the replica's edits on top of the last known server state.
 *
 * For each MV-Register field: if the user edited it, produce a single
 * (value, clock) entry using the base clock from the server state with
 * the replica's counter incremented. If untouched, carry the server's
 * existing values through unchanged so the relay can merge correctly.
 *
 * For G-Set fields (clinical_notes, bp_checks): produce the full
 * accumulated set including any new items the user added locally.
 *
 * For LWW fields (patient_id, prescriber): produce a single value with
 * the current wall-clock timestamp.
 */
function buildLocalOrder(serverOrder, edits, replicaId, gsetAdditions, isResolution = false) {
  const now = Date.now();

  // Helper: build an MVRegister dict for one field
  function mvField(fieldName) {
    const serverValues = serverOrder?.[fieldName]?.values ?? [];
    if (edits[fieldName] !== undefined && edits[fieldName] !== "") {
      const baseClock = isResolution
        ? mergeAllClocks(serverValues)
        : getBaseClock(serverValues);
      const newClock = incrementClock(baseClock, replicaId);
      return { type: "MVRegister", values: [{ value: edits[fieldName], clock: newClock }] };
    }
    // Untouched — carry server values through
    return { type: "MVRegister", values: serverValues };
  }

  // Helper: build a GSet dict for one field
  function gsetField(fieldName) {
    const serverItems = serverOrder?.[fieldName]?.items ?? [];
    const additions = gsetAdditions[fieldName] ?? [];
    const merged = Array.from(new Set([...serverItems, ...additions]));
    return { type: "GSet", items: merged };
  }

  // Helper: build an LWW dict for one field
  function lwwField(fieldName) {
    if (edits[fieldName] !== undefined && edits[fieldName] !== "") {
      return { type: "LWWRegister", value: edits[fieldName], timestamp: now };
    }
    return serverOrder?.[fieldName] ?? { type: "LWWRegister", value: "", timestamp: 0 };
  }

  return {
    patient_id:      lwwField("patient_id"),
    medication_name: mvField("medication_name"),
    dosage:          mvField("dosage"),
    frequency:       mvField("frequency"),
    route:           mvField("route"),
    status:          mvField("status"),
    prescriber:      lwwField("prescriber"),
    start_date:      mvField("start_date"),
    end_date:        mvField("end_date"),
    clinical_notes:  gsetField("clinical_notes"),
    bp_checks:       gsetField("bp_checks"),
  };
}

// ─── Field metadata ───────────────────────────────────────────────────────────
const MV_FIELDS = [
  { key: "medication_name", label: "Medication Name" },
  { key: "dosage",          label: "Dosage" },
  { key: "frequency",       label: "Frequency" },
  { key: "route",           label: "Route" },
  { key: "status",          label: "Status" },
  { key: "start_date",      label: "Start Date" },
  { key: "end_date",        label: "End Date" },
];

const LWW_FIELDS = [
  { key: "patient_id",  label: "Patient ID" },
  { key: "prescriber",  label: "Prescriber" },
];

const GSET_FIELDS = [
  { key: "clinical_notes", label: "Clinical Notes" },
  { key: "bp_checks",      label: "BP Checks" },
];

// ─── Utilities ────────────────────────────────────────────────────────────────

/** Extract a display value from a server field dict. */
function displayValue(fieldDict) {
  if (!fieldDict) return "—";
  if (fieldDict.type === "MVRegister") {
    const vals = fieldDict.values?.map(v => v.value) ?? [];
    return vals.length === 0 ? "—" : [...new Set(vals)].join(" / ");
  }
  if (fieldDict.type === "GSet") {
    return (fieldDict.items ?? []).join("; ") || "—";
  }
  if (fieldDict.type === "LWWRegister") {
    return fieldDict.value || "—";
  }
  return "—";
}

/** Check if a field has a conflict (multiple distinct values in MVRegister). */
function hasConflict(fieldDict) {
  if (!fieldDict || fieldDict.type !== "MVRegister") return false;
  const vals = new Set((fieldDict.values ?? []).map(v => v.value));
  return vals.size > 1;
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const COLORS = {
  navy:        "#1B2A4A",
  navyLight:   "#2C3E6B",
  navyDim:     "#0F1A30",
  amber:       "#D4860A",
  amberLight:  "#F5A623",
  amberBg:     "#FFF8EC",
  white:       "#FFFFFF",
  offWhite:    "#F7F8FA",
  border:      "#DDE1EA",
  textPrimary: "#1B2A4A",
  textMuted:   "#6B7A99",
  green:       "#1A7F5A",
  greenBg:     "#EBF7F3",
  red:         "#C0392B",
  redBg:       "#FDF0EE",
};

const styles = {
  // Layout
  page: {
    minHeight: "100vh",
    background: COLORS.offWhite,
    fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    color: COLORS.textPrimary,
  },
  // Status bar
  statusBar: (status) => ({
    background: status === "conflict" ? COLORS.amber :
                status === "synced"   ? COLORS.green :
                status === "syncing"  ? COLORS.navyLight : COLORS.navy,
    color: COLORS.white,
    padding: "10px 24px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "13px",
    letterSpacing: "0.02em",
    transition: "background 0.3s ease",
  }),
  statusDot: (status) => ({
    width: 8, height: 8, borderRadius: "50%",
    background: status === "conflict" ? COLORS.amberLight :
                status === "synced"   ? "#4ECCA3" :
                status === "syncing"  ? "#A0B0D0" : "#6B7A99",
    display: "inline-block",
    marginRight: 8,
    animation: status === "syncing" ? "pulse 1s infinite" : "none",
  }),
  // Header
  header: {
    background: COLORS.navy,
    color: COLORS.white,
    padding: "20px 24px 16px",
    borderBottom: `3px solid ${COLORS.amberLight}`,
  },
  headerTitle: {
    fontSize: "22px",
    fontWeight: 700,
    letterSpacing: "-0.02em",
    margin: 0,
  },
  headerSub: {
    fontSize: "13px",
    color: "#A0B0D0",
    marginTop: 4,
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
  },
  // Main content
  main: {
    maxWidth: 820,
    margin: "0 auto",
    padding: "32px 24px",
  },
  // Card
  card: {
    background: COLORS.white,
    borderRadius: 10,
    border: `1px solid ${COLORS.border}`,
    padding: "24px 28px",
    marginBottom: 20,
    boxShadow: "0 1px 4px rgba(27,42,74,0.06)",
  },
  cardTitle: {
    fontSize: "13px",
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: COLORS.textMuted,
    marginBottom: 18,
  },
  // Fields
  fieldGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "16px 24px",
  },
  fieldGroup: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  fieldLabel: {
    fontSize: "12px",
    fontWeight: 600,
    color: COLORS.textMuted,
    letterSpacing: "0.04em",
  },
  fieldInput: (conflict) => ({
    padding: "9px 12px",
    border: `1.5px solid ${conflict ? COLORS.amber : COLORS.border}`,
    borderRadius: 6,
    fontSize: "14px",
    color: COLORS.textPrimary,
    background: conflict ? COLORS.amberBg : COLORS.white,
    outline: "none",
    transition: "border-color 0.15s",
    fontFamily: "inherit",
  }),
  fieldValue: {
    fontSize: "14px",
    color: COLORS.textPrimary,
    padding: "6px 0",
    minHeight: 28,
  },
  fieldValueConflict: {
    fontSize: "14px",
    color: COLORS.amber,
    fontWeight: 600,
    padding: "6px 0",
  },
  // Buttons
  btnPrimary: {
    background: COLORS.navy,
    color: COLORS.white,
    border: "none",
    borderRadius: 7,
    padding: "11px 28px",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
    letterSpacing: "0.01em",
    transition: "background 0.15s",
  },
  btnAmber: {
    background: COLORS.amber,
    color: COLORS.white,
    border: "none",
    borderRadius: 7,
    padding: "9px 20px",
    fontSize: "13px",
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 0.15s",
  },
  btnGhost: {
    background: "transparent",
    color: COLORS.navy,
    border: `1.5px solid ${COLORS.border}`,
    borderRadius: 7,
    padding: "9px 20px",
    fontSize: "13px",
    fontWeight: 600,
    cursor: "pointer",
  },
  // Conflict card
  conflictCard: {
    background: COLORS.amberBg,
    border: `1.5px solid ${COLORS.amber}`,
    borderRadius: 8,
    padding: "16px 20px",
    marginBottom: 14,
  },
  conflictField: {
    fontSize: "13px",
    fontWeight: 700,
    color: COLORS.amber,
    marginBottom: 10,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  conflictOptions: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
  },
  conflictOption: (selected) => ({
    background: selected ? COLORS.navy : COLORS.white,
    color: selected ? COLORS.white : COLORS.textPrimary,
    border: `1.5px solid ${selected ? COLORS.navy : COLORS.border}`,
    borderRadius: 6,
    padding: "7px 16px",
    fontSize: "13px",
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.15s",
  }),
  // GSet
  gsetItem: {
    display: "inline-block",
    background: COLORS.offWhite,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 4,
    padding: "3px 10px",
    fontSize: "13px",
    marginRight: 6,
    marginBottom: 6,
  },
  gsetInput: {
    display: "flex",
    gap: 8,
    marginTop: 8,
  },
  // Login
  loginWrap: {
    minHeight: "100vh",
    background: COLORS.navy,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  loginCard: {
    background: COLORS.white,
    borderRadius: 14,
    padding: "48px 44px",
    width: 380,
    boxShadow: "0 8px 40px rgba(0,0,0,0.18)",
    textAlign: "center",
  },
  loginTitle: {
    fontSize: "24px",
    fontWeight: 800,
    color: COLORS.navy,
    marginBottom: 6,
  },
  loginSub: {
    fontSize: "14px",
    color: COLORS.textMuted,
    marginBottom: 32,
    lineHeight: 1.5,
  },
  loginInput: {
    width: "100%",
    padding: "12px 14px",
    border: `1.5px solid ${COLORS.border}`,
    borderRadius: 7,
    fontSize: "15px",
    fontFamily: "'JetBrains Mono','Fira Code',monospace",
    textAlign: "center",
    outline: "none",
    boxSizing: "border-box",
    marginBottom: 16,
    color: COLORS.navy,
  },
  // Alert
  alert: (type) => ({
    padding: "12px 16px",
    borderRadius: 7,
    fontSize: "13px",
    marginBottom: 16,
    background: type === "error" ? COLORS.redBg : COLORS.greenBg,
    color: type === "error" ? COLORS.red : COLORS.green,
    border: `1px solid ${type === "error" ? "#F5C6C2" : "#9FD4C0"}`,
  }),
};

// ─── Components ───────────────────────────────────────────────────────────────

function StatusBar({ replicaId, status, lastSync }) {
  const labels = {
    idle:     "Ready",
    syncing:  "Syncing…",
    synced:   "Synced",
    conflict: "Conflict detected — review required",
    error:    "Sync failed",
  };
  return (
    <div style={styles.statusBar(status)}>
      <span>
        <span style={styles.statusDot(status)} />
        {labels[status] || status}
      </span>
      <span style={{ fontFamily: "monospace", opacity: 0.8 }}>
        {replicaId && `replica: ${replicaId}`}
        {lastSync && `  ·  last sync: ${lastSync}`}
      </span>
    </div>
  );
}

function LoginScreen({ onLogin }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  function handleSubmit() {
    const trimmed = name.trim().toLowerCase().replace(/\s+/g, "_");
    if (!trimmed) { setError("Please enter your name."); return; }
    onLogin(trimmed);
  }

  return (
    <div style={styles.loginWrap}>
      <div style={styles.loginCard}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>💊</div>
        <div style={styles.loginTitle}>MedOrder Sync</div>
        <div style={styles.loginSub}>
          Enter your name to access the medication order. Your edits will be tracked under your identity.
        </div>
        {error && <div style={styles.alert("error")}>{error}</div>}
        <input
          style={styles.loginInput}
          placeholder="e.g. nurse, dr_smith, pharmacist"
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSubmit()}
          autoFocus
        />
        <button style={{ ...styles.btnPrimary, width: "100%" }} onClick={handleSubmit}>
          Continue
        </button>
      </div>
    </div>
  );
}

function GSetPanel({ fieldKey, label, serverItems, onAdd }) {
  const [input, setInput] = useState("");
  const [localItems, setLocalItems] = useState([]);
  const allItems = Array.from(new Set([...(serverItems ?? []), ...localItems]));

  function handleAdd() {
    const val = input.trim();
    if (!val) return;
    setLocalItems(prev => [...prev, val]);
    onAdd(fieldKey, val);
    setInput("");
  }

  return (
    <div style={styles.fieldGroup}>
      <div style={styles.fieldLabel}>{label}</div>
      <div style={{ marginBottom: 6 }}>
        {allItems.length === 0
          ? <span style={{ color: COLORS.textMuted, fontSize: 13 }}>No entries yet</span>
          : allItems.map((item, i) => <span key={i} style={styles.gsetItem}>{item}</span>)
        }
      </div>
      <div style={styles.gsetInput}>
        <input
          style={{ ...styles.fieldInput(false), flex: 1 }}
          placeholder={`Add ${label.toLowerCase()}…`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleAdd()}
        />
        <button style={styles.btnGhost} onClick={handleAdd}>Add</button>
      </div>
    </div>
  );
}

function ConflictPanel({ conflicts, serverOrder, onResolve }) {
  const [selections, setSelections] = useState({});

  function select(field, value) {
    setSelections(prev => ({ ...prev, [field]: value }));
  }

  function canSubmit() {
    return conflicts.every(f => selections[f] !== undefined);
  }

  return (
    <div style={styles.card}>
      <div style={{ ...styles.cardTitle, color: COLORS.amber }}>
        ⚠ Conflicts Require Review
      </div>
      <p style={{ fontSize: 13, color: COLORS.textMuted, marginBottom: 18 }}>
        The following fields were concurrently edited by different clinicians.
        Select the correct value for each field to resolve the conflict.
      </p>
      {conflicts.map(field => {
        const values = [...new Set(
          (serverOrder?.[field]?.values ?? []).map(v => v.value)
        )];
        return (
          <div key={field} style={styles.conflictCard}>
            <div style={styles.conflictField}>{field.replace(/_/g, " ")}</div>
            <div style={styles.conflictOptions}>
              {values.map(val => (
                <button
                  key={val}
                  style={styles.conflictOption(selections[field] === val)}
                  onClick={() => select(field, val)}
                >
                  {val}
                </button>
              ))}
            </div>
          </div>
        );
      })}
      <div style={{ marginTop: 8 }}>
        <button
          style={{ ...styles.btnAmber, opacity: canSubmit() ? 1 : 0.5 }}
          disabled={!canSubmit()}
          onClick={() => onResolve(selections)}
        >
          Submit Resolution
        </button>
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [replicaId, setReplicaId]       = useState(null);
  const [serverOrder, setServerOrder]   = useState(null);
  const [edits, setEdits]               = useState({});
  const [gsetAdditions, setGsetAdd]     = useState({});
  const [conflicts, setConflicts]       = useState([]);
  const [syncStatus, setSyncStatus]     = useState("idle");
  const [lastSync, setLastSync]         = useState(null);
  const [alert, setAlertMsg]            = useState(null);
  const [isNewOrder, setIsNewOrder]     = useState(false);

  // Pull current state from relay on login
  const pullState = useCallback(async () => {
    try {
      const res = await fetch(`${RELAY_URL}/sync`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setServerOrder(data);
      // Detect if order is empty / not yet created
      const dosageVals = data?.dosage?.values ?? [];
      setIsNewOrder(dosageVals.length === 0 || displayValue(data.dosage) === "—");
      return data;
    } catch (e) {
      setAlertMsg({ type: "error", text: `Could not reach relay: ${e.message}` });
      return null;
    }
  }, []);

  async function handleLogin(name) {
    setReplicaId(name);
    setSyncStatus("syncing");
    const data = await pullState();
    setSyncStatus(data ? "idle" : "error");
  }

  function handleEdit(field, value) {
    setEdits(prev => ({ ...prev, [field]: value }));
  }

  function handleGSetAdd(field, value) {
    setGsetAdd(prev => ({
      ...prev,
      [field]: [...(prev[field] ?? []), value],
    }));
  }

  async function handleSync() {
    setSyncStatus("syncing");
    setAlertMsg(null);
    try {
      const localOrder = buildLocalOrder(serverOrder, edits, replicaId, gsetAdditions, false);
      const res = await fetch(`${RELAY_URL}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(localOrder),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setServerOrder(data.merged_state);
      setConflicts(data.conflicts ?? []);
      setEdits({});
      setGsetAdd({});
      setLastSync(new Date().toLocaleTimeString());
      setIsNewOrder(false);

      if ((data.conflicts ?? []).length > 0) {
        setSyncStatus("conflict");
      } else {
        setSyncStatus("synced");
        setAlertMsg({ type: "success", text: "Order synced successfully." });
        setTimeout(() => setSyncStatus("idle"), 3000);
      }
    } catch (e) {
      setSyncStatus("error");
      setAlertMsg({ type: "error", text: `Sync failed: ${e.message}` });
    }
  }

  async function handleResolve(selections) {
    // Apply each resolution as a new edit and re-sync
    const resolvedEdits = { ...selections };
    setSyncStatus("syncing");
    setAlertMsg(null);
    try {
      const localOrder = buildLocalOrder(serverOrder, resolvedEdits, replicaId, {}, true);
      const res = await fetch(`${RELAY_URL}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(localOrder),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setServerOrder(data.merged_state);
      setConflicts(data.conflicts ?? []);
      setEdits({});
      setLastSync(new Date().toLocaleTimeString());

      if ((data.conflicts ?? []).length > 0) {
        setSyncStatus("conflict");
      } else {
        setSyncStatus("synced");
        setAlertMsg({ type: "success", text: "Conflicts resolved and order synced." });
        setTimeout(() => setSyncStatus("idle"), 3000);
      }
    } catch (e) {
      setSyncStatus("error");
      setAlertMsg({ type: "error", text: `Resolution failed: ${e.message}` });
    }
  }

  // ── Render: Login ──
  if (!replicaId) return <LoginScreen onLogin={handleLogin} />;

  // ── Render: App ──
  return (
    <div style={styles.page}>
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        input:focus { border-color: #1B2A4A !important; box-shadow: 0 0 0 3px rgba(27,42,74,0.1); }
        button:hover { filter: brightness(1.08); }
      `}</style>

      <StatusBar replicaId={replicaId} status={syncStatus} lastSync={lastSync} />

      <div style={styles.header}>
        <h1 style={styles.headerTitle}>Medication Order</h1>
        <div style={styles.headerSub}>
          {isNewOrder ? "No order on server — fill in fields to create one" : "Editing existing order — changes sync to relay"}
        </div>
      </div>

      <div style={styles.main}>
        {alert && (
          <div style={styles.alert(alert.type)}>{alert.text}</div>
        )}

        {/* Conflict panel */}
        {conflicts.length > 0 && (
          <ConflictPanel
            conflicts={conflicts}
            serverOrder={serverOrder}
            onResolve={handleResolve}
          />
        )}

        {/* LWW Fields */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>Patient & Prescriber</div>
          <div style={styles.fieldGrid}>
            {LWW_FIELDS.map(({ key, label }) => (
              <div key={key} style={styles.fieldGroup}>
                <label style={styles.fieldLabel}>{label}</label>
                <input
                  style={styles.fieldInput(false)}
                  value={edits[key] ?? displayValue(serverOrder?.[key])}
                  onChange={e => handleEdit(key, e.target.value)}
                  placeholder={`Enter ${label.toLowerCase()}`}
                />
              </div>
            ))}
          </div>
        </div>

        {/* MV-Register Fields */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>Medication Details</div>
          <div style={styles.fieldGrid}>
            {MV_FIELDS.map(({ key, label }) => {
              const conflict = hasConflict(serverOrder?.[key]);
              return (
                <div key={key} style={styles.fieldGroup}>
                  <label style={styles.fieldLabel}>
                    {label}
                    {conflict && <span style={{ color: COLORS.amber, marginLeft: 6 }}>⚠ conflict</span>}
                  </label>
                  <input
                    style={styles.fieldInput(conflict)}
                    value={edits[key] ?? (conflict ? "" : displayValue(serverOrder?.[key]))}
                    onChange={e => handleEdit(key, e.target.value)}
                    placeholder={conflict ? "Conflicted — resolve above" : `Enter ${label.toLowerCase()}`}
                  />
                  {conflict && (
                    <div style={{ fontSize: 12, color: COLORS.amber, marginTop: 2 }}>
                      Competing: {[...new Set((serverOrder?.[key]?.values ?? []).map(v => v.value))].join(" vs ")}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* G-Set Fields */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>Append-Only Records</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {GSET_FIELDS.map(({ key, label }) => (
              <GSetPanel
                key={key}
                fieldKey={key}
                label={label}
                serverItems={serverOrder?.[key]?.items ?? []}
                onAdd={handleGSetAdd}
              />
            ))}
          </div>
        </div>

        {/* Sync button */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button style={styles.btnGhost} onClick={pullState}>
            Pull Latest
          </button>
          <button
            style={{ ...styles.btnPrimary, opacity: syncStatus === "syncing" ? 0.6 : 1 }}
            disabled={syncStatus === "syncing"}
            onClick={handleSync}
          >
            {syncStatus === "syncing" ? "Syncing…" : isNewOrder ? "Create Order" : "Sync Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
