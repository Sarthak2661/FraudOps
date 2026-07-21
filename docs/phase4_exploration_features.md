# Phase 4: Exploratory Analysis and Behavioural Features

## Objective

Transform transaction history into point-in-time-safe fraud indicators.

## Main Artifacts

- `src/fraudops/features.py`: point-in-time feature engineering logic
- `scripts/build_training_dataset.py`: date-filtered training dataset builder
- `data/curated/analytical_features/`: curated feature Parquet outputs
- `notebooks/01_fraud_exploration.ipynb`: reproducible exploration notebook
- `docs/feature_dictionary.md`: feature definitions and leakage notes

## Build Features

Features are created as part of the batch pipeline:

```powershell
python scripts/run_batch_ingestion.py
```

Build a training dataset for a selected date range:

```powershell
python scripts/build_training_dataset.py --start-date 2026-07-01 --end-date 2026-07-14 --output data/curated/training_dataset_2026_07.parquet
```

## Leakage Rule

Feature values for a transaction may use only transactions earlier than that transaction. Rolling customer, device, and merchant histories use left-closed windows so the current transaction is excluded from its own history.

## Latest Verified Training Dataset

`data/curated/training_dataset_2026_07.parquet` contains 2,191 rows for transactions from `2026-07-01` through before `2026-07-14`.

## Definition of Done

- Features are reproducible
- No future information is used in rolling features
- Unit tests cover validation and point-in-time feature behavior
- Feature distributions are inspectable in the notebook
- Training data can be built from a selected date range
