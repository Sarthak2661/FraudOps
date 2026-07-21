# Phase 5: Baseline Models and MLflow

## Objective

Train defensible baseline fraud models with chronological splitting and MLflow experiment tracking.

## Models

Implemented in `src/fraudops/modeling.py` and run by `scripts/train_baseline_models.py`:

- Rules-only baseline
- Logistic Regression with `class_weight="balanced"`
- Random Forest with balanced subsampling
- HistGradientBoostingClassifier
- Isolation Forest anomaly baseline

No deep learning is used.

## Split Strategy

Transactions are sorted by `transaction_at`:

- First 60%: training
- Next 20%: validation
- Final 20%: final test

The final test set is evaluated only after the selected model is chosen from validation results.

## Metrics

The training script logs:

- Precision
- Recall
- F1
- PR-AUC
- ROC-AUC
- Fraud-value recall
- False-positive rate
- Recall at fixed review capacity
- Expected financial cost
- Inference latency
- Threshold
- Confusion-matrix counts

## MLflow

This project uses a local SQLite MLflow backend:

```powershell
python scripts/train_baseline_models.py
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db --host 0.0.0.0 --port 5000
```

Open:

```text
http://localhost:5000
```

## Latest Result

Selected model: `random_forest_balanced`

Reason: lowest validation expected financial cost while keeping fraud metrics visible. Final test was held out until after validation selection.

Final test metrics are saved in:

```text
reports/modeling/selected_model_final_test_metrics.json
```

Model artifact:

```text
reports/modeling/selected_model.joblib
```
