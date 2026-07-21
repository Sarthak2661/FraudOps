# Phase 8: React Analyst Console

## Objective

Create an operational fraud-investigation application with a polished production-style UI.

## Run

```powershell
cd C:\Users\sarth\Documents\FraudOps\frontend
pnpm install
pnpm run dev
```

Open:

```text
http://127.0.0.1:5173
```

If `pnpm` is not on PATH, use Node.js tooling installed locally or run from VS Code's integrated terminal after installing Node.js.

## Views

1. Alert Queue
   - Alert ID, risk score, amount, priority, customer, decision, age, status, analyst, SLA
2. Transaction Investigation
   - Transaction details, customer/device/merchant context, triggered rules, behavioural chart, explanation area
3. Case Management
   - Create case, add notes, link alerts, assign analyst, update and resolve cases
4. Customer Timeline
   - Transactions, device/profile events, failed logins, alerts, and investigations
5. Analyst Workbench
   - Assigned alerts, due cases, SLA risk, resolved work, current model and rule count

## API Integration

The console uses `VITE_FRAUDOPS_API_URL` when provided, otherwise defaults to:

```text
http://127.0.0.1:8000
```

If the API is offline, it falls back to sample-data rows so the UI still renders during local walkthroughs.

## Definition of Done

- React app builds successfully
- Analyst pages are present
- UI can score a transaction through FastAPI
- Alert and case workflows call the backend endpoints
- The interface is production-style and product-like, not a quick notebook dashboard
