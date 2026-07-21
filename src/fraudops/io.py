from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_csv_table(source_dir: Path, table_name: str) -> pd.DataFrame:
    path = source_dir / f"{table_name}.csv"
    return pd.read_csv(path, keep_default_na=False)


def write_parquet_partitioned(df: pd.DataFrame, base_dir: Path, timestamp_column: str) -> list[Path]:
    frame = df.copy()
    timestamps = pd.to_datetime(frame[timestamp_column], utc=True, errors="coerce")
    frame["year"] = timestamps.dt.year.astype("Int64").astype(str)
    frame["month"] = timestamps.dt.month.astype("Int64").astype(str).str.zfill(2)
    frame["day"] = timestamps.dt.day.astype("Int64").astype(str).str.zfill(2)

    written: list[Path] = []
    for (year, month, day), partition in frame.groupby(["year", "month", "day"], dropna=False):
        partition_dir = base_dir / f"year={year}" / f"month={month}" / f"day={day}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        output_path = partition_dir / "transactions.parquet"
        partition.drop(columns=["year", "month", "day"]).to_parquet(output_path, index=False)
        written.append(output_path)
    return written


def read_parquet_tree(base_dir: Path) -> pd.DataFrame:
    files = sorted(base_dir.rglob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)


def write_single_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path
