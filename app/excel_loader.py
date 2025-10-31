from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


class ExcelIngestionError(Exception):
    """Raised when an Excel workbook cannot be parsed."""


def normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_")


def load_excel(path: Path) -> dict[str, list[dict]]:
    try:
        excel_file = pd.ExcelFile(path)
    except Exception as exc:  # pragma: no cover - defensive, pandas raises multiple types
        raise ExcelIngestionError(f"Failed to read Excel file: {exc}") from exc

    sheets: dict[str, list[dict]] = {}
    for sheet_name in excel_file.sheet_names:
        df = excel_file.parse(sheet_name)
        if df.empty:
            sheets[sheet_name] = []
            continue

        df.columns = [normalize_header(str(col)) for col in df.columns]
        df = df.reset_index().rename(columns={"index": "row_index"})
        rows: list[dict] = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            row_index = int(row_dict.pop("row_index"))
            cleaned = _clean_row(row_dict)
            rows.append(
                {
                    "row_index": row_index,
                    "company": _first_non_null(cleaned, ["company"]),
                    "field": _first_non_null(cleaned, ["field"]),
                    "well_name": _first_non_null(cleaned, ["well_name", "well"]),
                    "formation": _first_non_null(cleaned, ["formation", "formation_name"]),
                    "data": cleaned,
                }
            )
        sheets[sheet_name] = rows
    return sheets


def _first_non_null(row: dict, keys: Iterable[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not pd.isna(value):
            return str(value)
    return None


def _clean_row(row: dict) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in row.items():
        if pd.isna(value):
            continue
        if hasattr(value, "item"):
            try:
                value = value.item()
            except Exception:  # pragma: no cover - fallback for unexpected types
                value = value
        cleaned[str(key)] = value
    return cleaned
