import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  ListChecks,
  Loader2,
  RefreshCcw,
  Search,
  Send,
  ShieldCheck,
  UserRoundCheck,
  Wifi,
  WifiOff,
} from "lucide-react";
import { api } from "./lib/api";
import "./styles.css";

const tabs = [
  ["queue", "Alert Queue", AlertTriangle],
  ["investigation", "Investigation", Search],
  ["cases", "Cases", BriefcaseBusiness],
  ["timeline", "Timeline", Clock3],
  ["workbench", "Workbench", UserRoundCheck],
];

const sampleAlerts = [
  {
    alert_id: "ALT-SAMPLE-001",
    transaction_id: "TXN-SAMPLE-001",
    risk_score: 0.84,
    amount: 920,
    priority: 5,
    customer_id: "cust-sample",
    decision: "MANUAL_REVIEW",
    alert_age_minutes: 18,
    status: "OPEN",
    assigned_analyst: "analyst1",
    sla_deadline: new Date(Date.now() + 5 * 3600_000).toISOString(),
    triggered_rules: ["R001", "R004"],
  },
  {
    alert_id: "ALT-SAMPLE-002",
    transaction_id: "TXN-SAMPLE-002",
    risk_score: 0.61,
    amount: 340,
    priority: 3,
    customer_id: "cust-travel",
    decision: "STEP_UP_AUTHENTICATION",
    alert_age_minutes: 42,
    status: "IN_REVIEW",
    assigned_analyst: "analyst2",
    sla_deadline: new Date(Date.now() + 2 * 3600_000).toISOString(),
    triggered_rules: ["R003"],
  },
];

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0);
}

function formatTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function modelLabel(value) {
  return value ? String(value) : "-";
}

function scoreLabel(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "-";
}

function decisionContext(riskScore, threshold, decision) {
  if (!Number.isFinite(riskScore) || !Number.isFinite(threshold)) return "";
  const decisionText = String(decision || "").replaceAll("_", " ");
  return `Above ${scoreLabel(threshold)} threshold; cost rules selected ${decisionText}.`;
}

function StatusPill({ value }) {
  return <span className={`pill ${String(value).toLowerCase()}`}>{String(value).replaceAll("_", " ")}</span>;
}

function RiskBar({ value, threshold }) {
  const pct = Math.round((value || 0) * 100);
  const thresholdPct = Math.max(0, Math.min(100, Math.round((threshold || 0) * 100)));
  return (
    <div className="riskWrap">
      <div className="risk" aria-label={`Risk ${pct}%, threshold ${thresholdPct}%`}>
        <span style={{ width: `${pct}%` }} />
        {Number.isFinite(threshold) && <i style={{ left: `${thresholdPct}%` }} title={`Threshold ${thresholdPct}%`} />}
        <b>{pct}</b>
      </div>
      {Number.isFinite(threshold) && <small>threshold {scoreLabel(threshold)}</small>}
    </div>
  );
}

function Metric({ label, value, icon: Icon }) {
  return (
    <div className="metric">
      <Icon size={18} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StateBlock({ title, body, icon: Icon = Database, action }) {
  return (
    <div className="stateBlock">
      <Icon size={22} />
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}

function TopNotice({ apiState, error }) {
  if (apiState === "online" && !error) return null;
  const offline = apiState === "offline";
  return (
    <div className={`notice ${offline ? "warning" : "info"}`}>
      {offline ? <WifiOff size={18} /> : <Loader2 className="spin" size={18} />}
      <span>{offline ? `API unavailable. Showing sample data. ${error || ""}` : "Connecting to the API..."}</span>
    </div>
  );
}

function AlertQueue({ alerts, selectedAlert, setSelectedAlert, refresh, loading, usingSamples, threshold }) {
  return (
    <section className="panel fill">
      <div className="toolbar">
        <div>
          <h2>Alert Queue</h2>
          <p>{usingSamples ? "Sample alerts are displayed until the API returns live alerts." : `${alerts.length} active alerts from the API.`}</p>
        </div>
        <button onClick={refresh} disabled={loading}>
          {loading ? <Loader2 className="spin" size={16} /> : <RefreshCcw size={16} />}
          Refresh
        </button>
      </div>
      {loading ? (
        <StateBlock title="Loading alerts" body="Fetching the latest alert queue from the API." icon={Loader2} />
      ) : alerts.length === 0 ? (
        <StateBlock title="No alerts" body="Score a higher-risk transaction or run the Kafka demo to populate the queue." icon={CheckCircle2} />
      ) : (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Risk</th>
                <th>Amount</th>
                <th>Priority</th>
                <th>Customer</th>
                <th>Decision</th>
                <th>Age</th>
                <th>Status</th>
                <th>Analyst</th>
                <th>SLA</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr
                  key={alert.alert_id}
                  className={selectedAlert?.alert_id === alert.alert_id ? "selected" : ""}
                  onClick={() => setSelectedAlert(alert)}
                >
                  <td data-label="Alert ID">{alert.alert_id}</td>
                  <td data-label="Risk"><RiskBar value={alert.risk_score} threshold={threshold} /></td>
                  <td data-label="Amount">{money(alert.amount)}</td>
                  <td data-label="Priority">{alert.priority}</td>
                  <td data-label="Customer">{alert.customer_id || "-"}</td>
                  <td data-label="Decision">
                    <StatusPill value={alert.decision} />
                    {decisionContext(alert.risk_score, threshold, alert.decision) && (
                      <small className="decisionNote">{decisionContext(alert.risk_score, threshold, alert.decision)}</small>
                    )}
                  </td>
                  <td data-label="Age">{alert.alert_age_minutes}m</td>
                  <td data-label="Status"><StatusPill value={alert.status} /></td>
                  <td data-label="Analyst">{alert.assigned_analyst || "Unassigned"}</td>
                  <td data-label="SLA">{formatTime(alert.sla_deadline)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Investigation({ alert }) {
  const rules = alert?.triggered_rules || [];
  const chart = [18, 32, 24, 41, 29, 76, 54, 92, 48, 36];
  if (!alert) {
    return <StateBlock title="Select an alert" body="Choose an alert from the queue to inspect transaction, customer, device, and rule context." icon={Search} />;
  }
  return (
    <section className="grid2">
      <div className="panel">
        <h2>Transaction Investigation</h2>
        <dl className="details">
          <dt>Transaction</dt><dd>{alert.transaction_id}</dd>
          <dt>Customer</dt><dd>{alert.customer_id || "-"}</dd>
          <dt>Amount</dt><dd>{money(alert.amount)}</dd>
          <dt>Decision</dt><dd><StatusPill value={alert.decision} /></dd>
          <dt>Triggered Rules</dt><dd>{rules.length ? rules.join(", ") : "None"}</dd>
        </dl>
        <div className="explain">
          <h3>Explanation</h3>
          <p>Rule and model signals indicate elevated exposure. Review customer, device, and merchant history before resolution.</p>
        </div>
      </div>
      <div className="panel">
        <h2>Behavioural History</h2>
        <div className="bars" aria-label="Behavioral transaction history">
          {chart.map((value, index) => <span key={index} style={{ height: `${value}%` }} />)}
        </div>
        <div className="miniGrid">
          <Metric label="Device age" value="2.4d" icon={Activity} />
          <Metric label="Prior hour" value="3 txns" icon={Clock3} />
          <Metric label="Similar alerts" value="7" icon={ListChecks} />
          <Metric label="Top signal" value="amount ratio" icon={Gauge} />
        </div>
      </div>
    </section>
  );
}

function CaseManagement({ selectedAlert }) {
  const [caseRecord, setCaseRecord] = React.useState(null);
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");

  async function run(action) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err.message || "Case action failed.");
    } finally {
      setBusy(false);
    }
  }

  function create() {
    run(async () => {
      const created = await api.createCase({
        customer_id: selectedAlert?.customer_id,
        alert_ids: selectedAlert ? [selectedAlert.alert_id] : [],
        assigned_to: "analyst1",
        priority: selectedAlert?.priority || 3,
        case_summary: "Investigation opened from analyst console",
      });
      setCaseRecord(created);
    });
  }

  function addNote() {
    if (!caseRecord || !note.trim()) return;
    run(async () => {
      await api.addAction(caseRecord.case_id, { actor: "analyst1", action_type: "NOTE", notes: note });
      setCaseRecord(await api.getCase(caseRecord.case_id));
      setNote("");
    });
  }

  function resolve(outcome) {
    if (!caseRecord) return;
    run(async () => {
      setCaseRecord(await api.resolveCase(caseRecord.case_id, { actor: "analyst1", outcome, notes: `Resolved as ${outcome}` }));
    });
  }

  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <h2>Case Management</h2>
          <p>{selectedAlert ? `Selected alert: ${selectedAlert.alert_id}` : "Select an alert before creating a linked case."}</p>
        </div>
        <button onClick={create} disabled={busy || !selectedAlert}>
          {busy ? <Loader2 className="spin" size={16} /> : <BriefcaseBusiness size={16} />}
          Create Case
        </button>
      </div>
      {error && <div className="inlineError">{error}</div>}
      {caseRecord ? (
        <>
          <dl className="details compact">
            <dt>Case</dt><dd>{caseRecord.case_id}</dd>
            <dt>Status</dt><dd><StatusPill value={caseRecord.status} /></dd>
            <dt>Assigned</dt><dd>{caseRecord.assigned_to || "-"}</dd>
            <dt>Alerts</dt><dd>{caseRecord.alert_ids.join(", ") || "-"}</dd>
          </dl>
          <div className="noteRow">
            <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add investigation note" />
            <button onClick={addNote} disabled={busy || !note.trim()}>Add Note</button>
          </div>
          <div className="outcomes">
            {["CONFIRMED_FRAUD", "LEGITIMATE", "CUSTOMER_AUTHENTICATED", "INSUFFICIENT_EVIDENCE", "DUPLICATE_ALERT", "RULE_ERROR"].map((item) => (
              <button key={item} onClick={() => resolve(item)} disabled={busy}>{item.replaceAll("_", " ")}</button>
            ))}
          </div>
          <ul className="actions">
            {caseRecord.actions.length ? caseRecord.actions.map((action) => (
              <li key={action.action_id}><b>{action.action_type}</b><span>{action.notes || "No notes"}</span></li>
            )) : <li><span>No case actions recorded yet.</span></li>}
          </ul>
        </>
      ) : (
        <StateBlock title="No case open" body="Create a case from the selected alert, then add notes and record the outcome." icon={BriefcaseBusiness} />
      )}
    </section>
  );
}

function CustomerTimeline({ alert }) {
  if (!alert) {
    return <StateBlock title="No customer selected" body="Select an alert to view a customer timeline." icon={Clock3} />;
  }
  const events = ["Profile change", "Known device purchase", "Failed login", "International transaction", "Fraud alert", "Analyst note"].map((label, index) => ({
    label,
    time: `${index + 1}h ago`,
    active: index >= 3,
  }));
  return (
    <section className="panel">
      <h2>Customer Timeline</h2>
      <div className="timeline">
        {events.map((event) => (
          <div key={event.label} className={event.active ? "hot" : ""}>
            <span />
            <b>{event.label}</b>
            <em>{event.time}</em>
          </div>
        ))}
      </div>
      <p className="muted">Customer: {alert.customer_id || "-"}</p>
    </section>
  );
}

function Workbench({ alerts, model, rules, loading }) {
  const open = alerts.filter((alert) => alert.status !== "CLOSED");
  return (
    <section className="grid2">
      <div className="panel">
        <h2>Analyst Workbench</h2>
        <div className="metrics">
          <Metric label="Assigned alerts" value={open.length} icon={AlertTriangle} />
          <Metric label="Cases due today" value="3" icon={BriefcaseBusiness} />
          <Metric label="SLA risk" value={open.filter((alert) => alert.alert_age_minutes > 30).length} icon={Clock3} />
          <Metric label="Recently resolved" value="12" icon={ShieldCheck} />
        </div>
      </div>
      <div className="panel">
        <h2>Current Model & Rules</h2>
        {loading ? (
          <StateBlock title="Loading model" body="Fetching model artifact metadata." icon={Loader2} />
        ) : (
          <dl className="details compact">
            <dt>Model</dt><dd>{modelLabel(model?.model_name)}</dd>
            <dt>Status</dt><dd>{model?.model_status ? <StatusPill value={model.model_status} /> : "-"}</dd>
            <dt>Threshold</dt><dd>{model?.threshold?.toFixed?.(2) || "-"}</dd>
            <dt>Features</dt><dd>{model?.feature_count || 0}</dd>
            <dt>Rules</dt><dd>{rules.length}</dd>
          </dl>
        )}
      </div>
    </section>
  );
}

function ScorePanel({ onScored }) {
  const [amount, setAmount] = React.useState("920");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");

  async function score() {
    setBusy(true);
    setError("");
    try {
      const result = await api.score({
        transaction_id: `ui-${Date.now()}`,
        customer_id: "ui-customer",
        amount: Number(amount),
        currency: "USD",
      });
      await onScored(result);
    } catch (err) {
      setError(err.message || "Scoring failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scoreCard">
      <label htmlFor="score-amount">Quick score</label>
      <div className="scoreControls">
        <input id="score-amount" value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" />
        <button onClick={score} disabled={busy || !Number(amount)}>
          {busy ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
          Score Transaction
        </button>
      </div>
      {error && <span className="scoreError">{error}</span>}
    </div>
  );
}

function LastScored({ result, threshold }) {
  if (!result) return null;
  return (
    <div className="lastScored">
      <CheckCircle2 size={18} />
      <span>
        Last scored <b>{result.transaction_id}</b>: <b>{scoreLabel(result.risk_score)}</b> risk
        {Number.isFinite(threshold) ? ` against ${scoreLabel(threshold)} threshold` : ""}, {result.decision.replaceAll("_", " ")}
        {result.alert_id ? `, alert ${result.alert_id}` : ", no alert"}.
        {decisionContext(result.risk_score, threshold, result.decision) && <em>{decisionContext(result.risk_score, threshold, result.decision)}</em>}
      </span>
    </div>
  );
}

function App() {
  const [tab, setTab] = React.useState("queue");
  const [alerts, setAlerts] = React.useState([]);
  const [selectedAlert, setSelectedAlert] = React.useState(null);
  const [model, setModel] = React.useState(null);
  const [rules, setRules] = React.useState([]);
  const [apiState, setApiState] = React.useState("checking");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [usingSamples, setUsingSamples] = React.useState(false);
  const [lastScored, setLastScored] = React.useState(null);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      await api.health();
      const [alertRows, modelInfo, ruleRows] = await Promise.all([api.alerts(), api.model(), api.rules()]);
      const nextAlerts = alertRows.length ? alertRows : [];
      setAlerts(nextAlerts);
      setSelectedAlert((current) => nextAlerts.find((alert) => alert.alert_id === current?.alert_id) || nextAlerts[0] || null);
      setModel(modelInfo);
      setRules(ruleRows);
      setUsingSamples(false);
      setApiState("online");
    } catch (err) {
      setAlerts(sampleAlerts);
      setSelectedAlert((current) => current || sampleAlerts[0]);
      setUsingSamples(true);
      setApiState("offline");
      setError(err.message || "API request failed.");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    refresh();
  }, []);

  async function onScored(result) {
    setLastScored(result);
    await refresh();
    if (result.alert_id) {
      try {
        setSelectedAlert(await api.alert(result.alert_id));
        setTab("queue");
      } catch {
        setTab("queue");
      }
    }
  }

  const activeTab = tabs.find(([id]) => id === tab);

  return (
    <div className="app">
      <aside>
        <div className="brand">
          <ShieldCheck />
          <div>
            <h1>FraudOps</h1>
            <span>{apiState === "online" ? "API online" : apiState === "offline" ? "Sample mode" : "Checking API"}</span>
          </div>
        </div>
        <nav>
          {tabs.map(([id, label, Icon]) => (
            <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <main>
        <header>
          <div className="titleBlock">
            <div className="eyebrow">{apiState === "online" ? <Wifi size={15} /> : <WifiOff size={15} />} {apiState === "online" ? "Live API" : "Local preview"}</div>
            <h1>{activeTab?.[1]}</h1>
            <p>Operational fraud review, scoring, and case workbench.</p>
          </div>
          <ScorePanel onScored={onScored} />
        </header>
        <TopNotice apiState={apiState} error={error} />
        <LastScored result={lastScored} threshold={model?.threshold} />
        {tab === "queue" && (
          <AlertQueue
            alerts={alerts}
            selectedAlert={selectedAlert}
            setSelectedAlert={setSelectedAlert}
            refresh={refresh}
            loading={loading}
            usingSamples={usingSamples}
            threshold={model?.threshold}
          />
        )}
        {tab === "investigation" && <Investigation alert={selectedAlert} />}
        {tab === "cases" && <CaseManagement selectedAlert={selectedAlert} />}
        {tab === "timeline" && <CustomerTimeline alert={selectedAlert} />}
        {tab === "workbench" && <Workbench alerts={alerts} model={model} rules={rules} loading={loading} />}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
