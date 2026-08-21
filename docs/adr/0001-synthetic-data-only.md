# ADR 0001: Synthetic Data Only

## Status

Accepted

## Context

FraudOps demonstrates banking fraud detection, analyst review, model training, and reporting workflows. Real banking data can contain personal information, payment identifiers, account data, dispute history, device metadata, and regulated financial records. Using real data would create privacy, security, legal, and governance risks that are unnecessary for a portfolio project.

## Decision

FraudOps will use generated synthetic data only. The repository must not include real customer data, production payment records, private credentials, or copied bank datasets with uncertain licensing.

## Consequences

- The project can be shared publicly without exposing real customers.
- Fraud scenarios, delayed labels, devices, merchants, false positives, and analyst outcomes can be modeled deliberately.
- Model metrics are demonstration metrics, not production performance claims.
- Any future production-like deployment must replace synthetic assumptions with formal data governance, privacy review, access controls, and validation against approved data sources.
