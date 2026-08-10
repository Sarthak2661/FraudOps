from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURE_RUN_ID = "phase3_full_002"


def default_feature_path(project_root: Path = PROJECT_ROOT) -> Path:
    preferred = project_root / "data" / "curated" / "analytical_features" / f"pipeline_run_id={DEFAULT_FEATURE_RUN_ID}" / "features.parquet"
    if preferred.exists():
        return preferred

    feature_root = project_root / "data" / "curated" / "analytical_features"
    candidates = sorted(
        feature_root.glob("pipeline_run_id=*/features.parquet"),
        key=lambda path: (path.stat().st_mtime, path.parent.name),
        reverse=True,
    )
    return candidates[0] if candidates else preferred
