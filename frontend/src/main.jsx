import React from "react";
import { createRoot } from "react-dom/client";
import { AlertTriangle, Activity, BriefcaseBusiness, Clock3, Gauge, ListChecks, Search, ShieldCheck, UserRoundCheck } from "lucide-react";
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
  { alert_id: "ALT-SAMPLE-001", transaction_id: "TXN-SAMPLE-001", risk_score: 0.84, amount: 920, priority: 5, customer_id: "cust-sample", decision: "MANUAL_REVIEW", alert_age_minutes: 18, status: "OPEN", assigned_analyst: "analyst1", sla_deadline: new Date(Date.now() + 5 * 3600_000).toISOString(), triggered_rules: ["R001", "R004"] },
  { alert_id: "ALT-SAMPLE-002", transaction_id: "TXN-SAMPLE-002", risk_score: 0.61, amount: 340, priority: 3, customer_id: "cust-travel", decision: "STEP_UP_AUTHENTICATION", alert_age_minutes: 42, status: "IN_REVIEW", assigned_analyst: "analyst2", sla_deadline: new Date(Date.now() + 2 * 3600_000).toISOString(), triggered_rules: ["R003"] },
];

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0);
}

function StatusPill({ value }) {
  return <span className={`pill ${String(value).toLowerCase()}`}>{value}</span>;
}

function RiskBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  return <div className="risk"><span style={{ width: `${pct}%` }} /><b>{pct}</b></div>;
}

function Metric({ label, value, icon: Icon }) {
  return <div className="metric"><Icon size={18} /><span>{label}</span><strong>{value}</strong></div>;
}

function AlertQueue({ alerts, selectedAlert, setSelectedAlert, refresh }) {
  return <section className="panel fill"><div className="toolbar"><h2>Alert Queue</h2><button onClick={refresh}>Refresh</button></div><div className="tableWrap"><table><thead><tr><th>Alert ID</th><th>Risk</th><th>Amount</th><th>Priority</th><th>Customer</th><th>Decision</th><th>Age</th><th>Status</th><th>Analyst</th><th>SLA</th></tr></thead><tbody>{alerts.map(alert => <tr key={alert.alert_id} className={selectedAlert?.alert_id === alert.alert_id ? "selected" : ""} onClick={() => setSelectedAlert(alert)}><td>{alert.alert_id}</td><td><RiskBar value={alert.risk_score} /></td><td>{money(alert.amount)}</td><td>{alert.priority}</td><td>{alert.customer_id || "-"}</td><td><StatusPill value={alert.decision} /></td><td>{alert.alert_age_minutes}m</td><td><StatusPill value={alert.status} /></td><td>{alert.assigned_analyst || "Unassigned"}</td><td>{new Date(alert.sla_deadline).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td></tr>)}</tbody></table></div></section>;
}

function Investigation({ alert, transaction }) {
  const rules = alert?.triggered_rules || [];
  const chart = [18, 32, 24, 41, 29, 76, 54, 92, 48, 36];
  return <section className="grid2"><div className="panel"><h2>Transaction Investigation</h2><dl className="details"><dt>Transaction</dt><dd>{alert?.transaction_id || transaction?.transaction_id || "Select an alert"}</dd><dt>Customer</dt><dd>{alert?.customer_id || transaction?.customer_id || "-"}</dd><dt>Amount</dt><dd>{money(alert?.amount || transaction?.amount)}</dd><dt>Decision</dt><dd>{alert ? <StatusPill value={alert.decision} /> : "-"}</dd><dt>Triggered Rules</dt><dd>{rules.length ? rules.join(", ") : "None"}</dd></dl><div className="explain"><h3>Explanation</h3><p>{rules.length ? "Rule and model signals indicate elevated exposure. Review customer, device, and merchant history before resolution." : "No active alert selected."}</p></div></div><div className="panel"><h2>Behavioural History</h2><div className="bars">{chart.map((v, i) => <span key={i} style={{ height: `${v}%` }} />)}</div><div className="miniGrid"><Metric label="Device age" value="2.4d" icon={Activity} /><Metric label="Prior hour" value="3 txns" icon={Clock3} /><Metric label="Similar alerts" value="7" icon={ListChecks} /><Metric label="SHAP top signal" value="amount ratio" icon={Gauge} /></div></div></section>;
}

function CaseManagement({ selectedAlert }) {
  const [caseRecord, setCaseRecord] = React.useState(null);
  const [note, setNote] = React.useState("");
  async function create() {
    const created = await api.createCase({ customer_id: selectedAlert?.customer_id, alert_ids: selectedAlert ? [selectedAlert.alert_id] : [], assigned_to: "analyst1", priority: selectedAlert?.priority || 3, case_summary: "Investigation opened from analyst console" });
    setCaseRecord(created);
  }
  async function addNote() {
    if (!caseRecord || !note.trim()) return;
    await api.addAction(caseRecord.case_id, { actor: "analyst1", action_type: "NOTE", notes: note });
    setCaseRecord(await api.getCase(caseRecord.case_id));
    setNote("");
  }
  async function resolve(outcome) {
    if (!caseRecord) return;
    setCaseRecord(await api.resolveCase(caseRecord.case_id, { actor: "analyst1", outcome, notes: `Resolved as ${outcome}` }));
  }
  return <section className="panel"><div className="toolbar"><h2>Case Management</h2><button onClick={create}>Create Case</button></div>{caseRecord ? <><dl className="details compact"><dt>Case</dt><dd>{caseRecord.case_id}</dd><dt>Status</dt><dd><StatusPill value={caseRecord.status} /></dd><dt>Assigned</dt><dd>{caseRecord.assigned_to || "-"}</dd><dt>Alerts</dt><dd>{caseRecord.alert_ids.join(", ") || "-"}</dd></dl><div className="noteRow"><input value={note} onChange={e => setNote(e.target.value)} placeholder="Add investigation note" /><button onClick={addNote}>Add Note</button></div><div className="outcomes">{["CONFIRMED_FRAUD", "LEGITIMATE", "CUSTOMER_AUTHENTICATED", "INSUFFICIENT_EVIDENCE", "DUPLICATE_ALERT", "RULE_ERROR"].map(item => <button key={item} onClick={() => resolve(item)}>{item}</button>)}</div><ul className="actions">{caseRecord.actions.map(action => <li key={action.action_id}><b>{action.action_type}</b><span>{action.notes}</span></li>)}</ul></> : <p className="muted">Create a case from the selected alert, then add notes, link alerts, assign ownership, and resolve it.</p>}</section>;
}

function CustomerTimeline({ alert }) {
  const events = ["Profile change", "Known device purchase", "Failed login", "International transaction", "Fraud alert", "Analyst note"].map((label, i) => ({ label, time: `${i + 1}h ago`, active: i >= 3 }));
  return <section className="panel"><h2>Customer Timeline</h2><div className="timeline">{events.map(event => <div key={event.label} className={event.active ? "hot" : ""}><span /> <b>{event.label}</b><em>{event.time}</em></div>)}</div><p className="muted">Customer: {alert?.customer_id || "Select an alert"}</p></section>;
}

function Workbench({ alerts, model, rules }) {
  const open = alerts.filter(a => a.status !== "CLOSED");
  return <section className="grid2"><div className="panel"><h2>Analyst Workbench</h2><div className="metrics"><Metric label="Assigned alerts" value={open.length} icon={AlertTriangle} /><Metric label="Cases due today" value="3" icon={BriefcaseBusiness} /><Metric label="SLA risk" value={open.filter(a => a.alert_age_minutes > 30).length} icon={Clock3} /><Metric label="Recently resolved" value="12" icon={ShieldCheck} /></div></div><div className="panel"><h2>Current Model & Rules</h2><dl className="details compact"><dt>Model</dt><dd>{model?.model_name || "-"}</dd><dt>Threshold</dt><dd>{model?.threshold?.toFixed?.(2) || "-"}</dd><dt>Features</dt><dd>{model?.feature_count || 0}</dd><dt>Rules</dt><dd>{rules.length}</dd></dl></div></section>;
}

function ScorePanel({ onScored }) {
  const [amount, setAmount] = React.useState("920");
  const [probability, setProbability] = React.useState("0.82");
  async function score() {
    const result = await api.score({ transaction_id: `ui-${Date.now()}`, customer_id: "ui-customer", amount: Number(amount), currency: "USD", model_probability_override: Number(probability) });
    onScored(result);
  }
  return <div className="scorePanel"><input value={amount} onChange={e => setAmount(e.target.value)} /><input value={probability} onChange={e => setProbability(e.target.value)} /><button onClick={score}>Score Transaction</button></div>;
}

function App() {
  const [tab, setTab] = React.useState("queue");
  const [alerts, setAlerts] = React.useState(sampleAlerts);
  const [selectedAlert, setSelectedAlert] = React.useState(sampleAlerts[0]);
  const [model, setModel] = React.useState(null);
  const [rules, setRules] = React.useState([]);
  const [apiState, setApiState] = React.useState("checking");
  async function refresh() {
    try {
      await api.health();
      const [alertRows, modelInfo, ruleRows] = await Promise.all([api.alerts(), api.model(), api.rules()]);
      setAlerts(alertRows.length ? alertRows : sampleAlerts);
      setSelectedAlert(alertRows[0] || sampleAlerts[0]);
      setModel(modelInfo);
      setRules(ruleRows);
      setApiState("online");
    } catch {
      setApiState("offline");
    }
  }
  React.useEffect(() => { refresh(); }, []);
  async function onScored(result) {
    await refresh();
    if (result.alert_id) setSelectedAlert((await api.alert(result.alert_id)));
  }
  return <div className="app"><aside><div className="brand"><ShieldCheck /><div><h1>FraudOps</h1><span>{apiState === "online" ? "API online" : apiState === "offline" ? "Using sample data" : "Checking API"}</span></div></div><nav>{tabs.map(([id, label, Icon]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}><Icon size={18} />{label}</button>)}</nav></aside><main><header><div><h1>{tabs.find(t => t[0] === tab)?.[1]}</h1><p>Operational fraud review, scoring, and case workbench.</p></div><ScorePanel onScored={onScored} /></header>{tab === "queue" && <AlertQueue alerts={alerts} selectedAlert={selectedAlert} setSelectedAlert={setSelectedAlert} refresh={refresh} />}{tab === "investigation" && <Investigation alert={selectedAlert} />}{tab === "cases" && <CaseManagement selectedAlert={selectedAlert} />}{tab === "timeline" && <CustomerTimeline alert={selectedAlert} />}{tab === "workbench" && <Workbench alerts={alerts} model={model} rules={rules} />}</main></div>;
}

createRoot(document.getElementById("root")).render(<App />);
