from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fraudops.decisioning import evaluate_rules, load_yaml, normalized_rule_score
from fraudops.paths import default_feature_path

ID_COLUMNS = {
    "transaction_id",
    "transaction_external_id",
    "customer_id",
    "account_id",
    "card_id",
    "device_id",
    "merchant_id",
    "feature_pipeline_run_id",
    "fraud_scenario",
}
TARGET_COLUMNS = {"fraud_label", "is_fraud"}
TIME_COLUMNS = {"transaction_at"}
LEAKAGE_COLUMNS = {"label_source", "chargeback_date", "analyst_confirmed_at", "label_available_at"}


@dataclass(frozen=True)
class SplitData:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def load_features(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path).copy()
    frame["transaction_at"] = pd.to_datetime(frame["transaction_at"], utc=True)
    frame["is_fraud"] = frame["fraud_label"].eq("fraud").astype(int)
    return frame.sort_values("transaction_at").reset_index(drop=True)


def chronological_split(frame: pd.DataFrame, train_ratio: float = 0.60, validation_ratio: float = 0.20) -> SplitData:
    ordered = frame.sort_values("transaction_at").reset_index(drop=True)
    train_end = int(len(ordered) * train_ratio)
    validation_end = int(len(ordered) * (train_ratio + validation_ratio))
    return SplitData(
        train=ordered.iloc[:train_end].copy(),
        validation=ordered.iloc[train_end:validation_end].copy(),
        test=ordered.iloc[validation_end:].copy(),
    )


def feature_columns(frame: pd.DataFrame) -> list[str]:
    excluded = ID_COLUMNS | TARGET_COLUMNS | TIME_COLUMNS | LEAKAGE_COLUMNS
    columns = []
    for column in frame.columns:
        if column in excluded:
            continue
        if pd.api.types.is_bool_dtype(frame[column]) or pd.api.types.is_numeric_dtype(frame[column]):
            columns.append(column)
    return columns


def xy(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    return frame[columns].copy(), frame["is_fraud"].astype(int).copy()


def build_models(random_state: int) -> dict[str, Any]:
    return {
        "rules_only_baseline": None,
        "logistic_regression_balanced": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=random_state)),
            ]
        ),
        "random_forest_balanced": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=150,
                        min_samples_leaf=10,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("model", HistGradientBoostingClassifier(max_iter=150, learning_rate=0.06, random_state=random_state)),
            ]
        ),
        "isolation_forest_anomaly": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("model", IsolationForest(n_estimators=150, contamination=0.02, random_state=random_state, n_jobs=-1)),
            ]
        ),
    }


def predict_scores(model_name: str, model: Any, train_x: pd.DataFrame, train_y: pd.Series, eval_x: pd.DataFrame) -> np.ndarray:
    if model_name == "rules_only_baseline":
        raise ValueError("Rules-only scores are calculated separately.")
    if model_name == "isolation_forest_anomaly":
        model.fit(train_x)
        scores = -model.decision_function(eval_x)
        return (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)
    model.fit(train_x, train_y)
    if hasattr(model, "predict_proba"):
        return model.predict_proba(eval_x)[:, 1]
    decision = model.decision_function(eval_x)
    return (decision - decision.min()) / (decision.max() - decision.min() + 1e-9)


def rules_scores(frame: pd.DataFrame, rules_config: dict[str, Any]) -> np.ndarray:
    scores = []
    for _, row in frame.iterrows():
        triggered = evaluate_rules(row.to_dict(), rules_config)
        scores.append(normalized_rule_score(triggered))
    return np.array(scores, dtype=float)


def expected_financial_cost(y_true: pd.Series, scores: np.ndarray, amounts: pd.Series, threshold: float, cost_config: dict[str, Any]) -> float:
    predictions = scores >= threshold
    fraud_loss = np.maximum(amounts.astype(float).to_numpy(), float(cost_config.get("average_fraud_loss", 250.0)))
    review_cost = float(cost_config.get("average_manual_review_cost", 8.50))
    legitimate_decline_cost = float(cost_config.get("legitimate_decline_cost", 45.0))
    y = y_true.to_numpy().astype(bool)
    false_negative_cost = np.where(y & ~predictions, fraud_loss, 0.0)
    false_positive_cost = np.where(~y & predictions, review_cost + legitimate_decline_cost * 0.10, 0.0)
    true_positive_cost = np.where(y & predictions, review_cost, 0.0)
    return float(false_negative_cost.sum() + false_positive_cost.sum() + true_positive_cost.sum())


def fraud_value_recall(y_true: pd.Series, scores: np.ndarray, amounts: pd.Series, threshold: float) -> float:
    fraud_mask = y_true.astype(bool).to_numpy()
    total_value = amounts.astype(float).to_numpy()[fraud_mask].sum()
    if total_value == 0:
        return 0.0
    captured = amounts.astype(float).to_numpy()[fraud_mask & (scores >= threshold)].sum()
    return float(captured / total_value)


def recall_at_capacity(y_true: pd.Series, scores: np.ndarray, capacity: int) -> float:
    if y_true.sum() == 0:
        return 0.0
    top = np.argsort(scores)[::-1][: min(capacity, len(scores))]
    return float(y_true.iloc[top].sum() / y_true.sum())


def choose_threshold(y_true: pd.Series, scores: np.ndarray, amounts: pd.Series, cost_config: dict[str, Any]) -> tuple[float, float]:
    candidates = np.linspace(0.05, 0.95, 19)
    costs = [(threshold, expected_financial_cost(y_true, scores, amounts, threshold, cost_config)) for threshold in candidates]
    return min(costs, key=lambda item: item[1])


def metrics_for(y_true: pd.Series, scores: np.ndarray, amounts: pd.Series, threshold: float, cost_config: dict[str, Any], latency_ms: float) -> dict[str, float]:
    predictions = scores >= threshold
    precision, recall, _ = precision_recall_curve(y_true, scores)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "pr_auc": float(auc(recall, precision)),
        "roc_auc": float(roc_auc_score(y_true, scores)) if y_true.nunique() > 1 else 0.0,
        "fraud_value_recall": fraud_value_recall(y_true, scores, amounts, threshold),
        "false_positive_rate": float(fp / max(1, fp + tn)),
        "recall_at_fixed_review_capacity": recall_at_capacity(y_true, scores, int(cost_config.get("analyst_daily_capacity", 500))),
        "expected_financial_cost": expected_financial_cost(y_true, scores, amounts, threshold, cost_config),
        "inference_latency_ms_per_record": float(latency_ms),
        "threshold": float(threshold),
        "true_positives": float(tp),
        "false_positives": float(fp),
        "true_negatives": float(tn),
        "false_negatives": float(fn),
    }


def log_run(model_name: str, model: Any, params: dict[str, Any], metrics: dict[str, float], artifacts: dict[str, Path]) -> None:
    with mlflow.start_run(run_name=model_name):
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        for artifact_path in artifacts.values():
            if artifact_path.exists():
                mlflow.log_artifact(str(artifact_path))
        if model is not None and model_name != "isolation_forest_anomaly":
            mlflow.sklearn.log_model(model, name="model", serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE)


def train_and_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    features = load_features(args.features)
    splits = chronological_split(features)
    columns = feature_columns(features)
    rules_config = load_yaml(args.rules)
    cost_config = load_yaml(args.cost_config)
    mlflow.set_tracking_uri(args.mlflow_tracking_uri)
    mlflow.set_experiment(args.experiment_name)

    train_x, train_y = xy(splits.train, columns)
    val_x, val_y = xy(splits.validation, columns)
    models = build_models(args.random_state)
    comparison_rows = []
    fitted_models: dict[str, Any] = {}
    thresholds: dict[str, float] = {}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    split_summary = {
        "feature_version": args.feature_version,
        "data_period": {
            "train": [splits.train["transaction_at"].min().isoformat(), splits.train["transaction_at"].max().isoformat()],
            "validation": [splits.validation["transaction_at"].min().isoformat(), splits.validation["transaction_at"].max().isoformat()],
            "final_test_held_out": [splits.test["transaction_at"].min().isoformat(), splits.test["transaction_at"].max().isoformat()],
        },
        "training_record_count": int(len(splits.train)),
        "validation_record_count": int(len(splits.validation)),
        "final_test_record_count": int(len(splits.test)),
        "training_fraud_rate": float(train_y.mean()),
        "features": columns,
    }
    split_path = args.output_dir / "split_summary.json"
    split_path.write_text(json.dumps(split_summary, indent=2), encoding="utf-8")

    for model_name, model in models.items():
        start = time.perf_counter()
        if model_name == "rules_only_baseline":
            val_scores = rules_scores(splits.validation, rules_config)
        else:
            val_scores = predict_scores(model_name, model, train_x, train_y, val_x)
            fitted_models[model_name] = model
        latency_ms = (time.perf_counter() - start) * 1000 / max(1, len(splits.validation))
        threshold, _ = choose_threshold(val_y, val_scores, splits.validation["transaction_amount"], cost_config)
        thresholds[model_name] = threshold
        metrics = metrics_for(val_y, val_scores, splits.validation["transaction_amount"], threshold, cost_config, latency_ms)
        row = {"model_name": model_name, "split": "validation", **metrics}
        comparison_rows.append(row)
        params = {
            "feature_version": args.feature_version,
            "data_period": json.dumps(split_summary["data_period"]),
            "training_record_count": len(splits.train),
            "fraud_rate": float(train_y.mean()),
            "threshold": threshold,
            "model_name": model_name,
        }
        artifacts = {"split_summary": split_path}
        log_run(model_name, fitted_models.get(model_name), params, metrics, artifacts)

    comparison = pd.DataFrame(comparison_rows).sort_values(["expected_financial_cost", "pr_auc"], ascending=[True, False])
    comparison_path = args.output_dir / "model_comparison_validation.csv"
    comparison.to_csv(comparison_path, index=False)
    selected_model_name = comparison.iloc[0]["model_name"]
    selected_reason = (
        f"Selected {selected_model_name} because it had the lowest validation expected financial cost "
        f"while preserving PR-AUC and recall-at-capacity visibility. Final test was held out until after this selection."
    )

    test_metrics = {}
    selected_model = fitted_models.get(selected_model_name)
    test_x, test_y = xy(splits.test, columns)
    start = time.perf_counter()
    if selected_model_name == "rules_only_baseline":
        test_scores = rules_scores(splits.test, rules_config)
    else:
        test_scores = predict_scores(selected_model_name, selected_model, train_x, train_y, test_x)
    latency_ms = (time.perf_counter() - start) * 1000 / max(1, len(splits.test))
    test_metrics = metrics_for(test_y, test_scores, splits.test["transaction_amount"], thresholds[selected_model_name], cost_config, latency_ms)
    test_path = args.output_dir / "selected_model_final_test_metrics.json"
    test_path.write_text(json.dumps(test_metrics, indent=2), encoding="utf-8")

    selected_artifact_path = args.output_dir / "selected_model.joblib"
    if selected_model is not None:
        joblib.dump({"model": selected_model, "features": columns, "threshold": thresholds[selected_model_name]}, selected_artifact_path)

    selection_doc = {
        "selected_model": selected_model_name,
        "selection_reason": selected_reason,
        "validation_threshold": thresholds[selected_model_name],
        "validation_comparison_path": str(comparison_path),
        "final_test_metrics_path": str(test_path),
        "selected_model_artifact": str(selected_artifact_path) if selected_model is not None else None,
    }
    selection_path = args.output_dir / "model_selection.json"
    selection_path.write_text(json.dumps(selection_doc, indent=2), encoding="utf-8")

    with mlflow.start_run(run_name=f"selected_final_test_{selected_model_name}"):
        mlflow.log_params({"selected_model": selected_model_name, "threshold": thresholds[selected_model_name], "feature_version": args.feature_version})
        mlflow.log_metrics({f"final_test_{key}": value for key, value in test_metrics.items()})
        mlflow.log_artifact(str(selection_path))
        mlflow.log_artifact(str(comparison_path))
        if selected_model is not None:
            mlflow.log_artifact(str(selected_artifact_path))

    return {"comparison": comparison.to_dict(orient="records"), "selection": selection_doc, "final_test_metrics": test_metrics}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train FraudOps baseline fraud models with chronological splits and MLflow logging.")
    parser.add_argument("--features", type=Path, default=default_feature_path())
    parser.add_argument("--rules", type=Path, default=PROJECT_ROOT / "configs" / "rules.yaml")
    parser.add_argument("--cost-config", type=Path, default=PROJECT_ROOT / "configs" / "cost_config.yaml")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "modeling")
    parser.add_argument("--mlflow-tracking-uri", default=f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}")
    parser.add_argument("--experiment-name", default="FraudOps Baseline Models")
    parser.add_argument("--feature-version", default="phase4_features_v1")
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    result = train_and_evaluate(parse_args())
    print(json.dumps(result["selection"], indent=2))


if __name__ == "__main__":
    main()
