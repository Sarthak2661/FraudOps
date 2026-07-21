from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    sample_dir: Path
    raw_dir: Path
    validated_dir: Path
    rejected_dir: Path
    curated_dir: Path


def default_project_paths(root: Path | None = None) -> ProjectPaths:
    project_root = root or Path(__file__).resolve().parents[2]
    return ProjectPaths(
        root=project_root,
        sample_dir=project_root / "data" / "sample",
        raw_dir=project_root / "data" / "raw",
        validated_dir=project_root / "data" / "validated",
        rejected_dir=project_root / "data" / "rejected",
        curated_dir=project_root / "data" / "curated",
    )
