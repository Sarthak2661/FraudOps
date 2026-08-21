from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api.schemas import ModelCurrentResponse, RuleResponse
from fraudops.decisioning import load_yaml

MODEL_PATH = PROJECT_ROOT / "reports" / "modeling" / "selected_model.joblib"
FINAL_METRICS_PATH = PROJECT_ROOT / "reports" / "modeling" / "selected_model_final_test_metrics.json"
RULES_PATH = PROJECT_ROOT / "configs" / "rules.yaml"
COST_CONFIG_PATH = PROJECT_ROOT / "configs" / "cost_config.yaml"
DEFAULT_FALLBACK_PROBABILITY = 0.01


@lru_cache(maxsize=1)
def load_model_bundle() -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def load_rules_config() -> dict[str, Any]:
    return load_yaml(RULES_PATH)


@lru_cache(maxsize=1)
def load_cost_config() -> dict[str, Any]:
    return load_yaml(COST_CONFIG_PATH)


def current_model() -> ModelCurrentResponse:
    artifact_exists = MODEL_PATH.exists()
    bundle = load_model_bundle()
    metrics = json.loads(FINAL_METRICS_PATH.read_text(encoding="utf-8")) if FINAL_METRICS_PATH.exists() else {}
    if bundle:
        return ModelCurrentResponse(
            model_name="random_forest_balanced",
            model_status="READY",
            scoring_mode="model_artifact",
            threshold=float(bundle.get("threshold")),
            feature_count=len(bundle.get("features", [])),
            artifact_path=str(MODEL_PATH),
            artifact_exists=artifact_exists,
            trained_model_available=True,
            fallback_probability=None,
            metrics=metrics,
            message="Using the trained model artifact for scoring.",
        )
    return ModelCurrentResponse(
        model_name="unavailable",
        model_status="FALLBACK",
        scoring_mode="fallback_default_probability",
        threshold=None,
        feature_count=0,
        artifact_path=str(MODEL_PATH) if artifact_exists else None,
        artifact_exists=artifact_exists,
        trained_model_available=False,
        fallback_probability=DEFAULT_FALLBACK_PROBABILITY,
        metrics=metrics,
        message="Trained model artifact is not available. Run python scripts\\train_baseline_models.py to regenerate reports/modeling/selected_model.joblib.",
    )


def rules() -> list[RuleResponse]:
    return [
        RuleResponse(
            rule_id=item["rule_id"],
            name=item["name"],
            description=item.get("description", ""),
            severity=item.get("severity", "medium"),
            active=bool(item.get("active", True)),
            risk_points=float(item.get("risk_points", 0)),
            decision_override=item.get("decision_override"),
        )
        for item in load_rules_config().get("rules", [])
    ]
