from pathlib import Path

from fraudops.paths import default_feature_path


def _write_feature(root: Path, run_id: str) -> Path:
    path = root / "data" / "curated" / "analytical_features" / f"pipeline_run_id={run_id}" / "features.parquet"
    path.parent.mkdir(parents=True)
    path.write_text("placeholder", encoding="utf-8")
    return path


def test_default_feature_path_prefers_documented_snapshot(tmp_path: Path) -> None:
    preferred = _write_feature(tmp_path, "phase3_full_002")
    _write_feature(tmp_path, "airflow_ingestion_20260809")

    assert default_feature_path(tmp_path) == preferred


def test_default_feature_path_falls_back_to_newest_snapshot(tmp_path: Path) -> None:
    older = _write_feature(tmp_path, "airflow_ingestion_20260808")
    newest = _write_feature(tmp_path, "airflow_ingestion_20260809")
    older.touch()
    newest.touch()

    assert default_feature_path(tmp_path) == newest
