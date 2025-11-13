"""Utilities for extracting basic metadata from LIS and DLIS well log files."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Iterable, List, Optional


class WellLogError(Exception):
    """Raised when a well log cannot be parsed."""


@dataclass
class WellLogSummary:
    """Simple serialisable representation of the extracted metadata."""

    file_name: str
    log_format: str
    well_names: List[str]
    curve_names: List[str]
    depth_min: Optional[float]
    depth_max: Optional[float]
    depth_unit: Optional[str]
    notes: List[str]

    def to_dict(self) -> dict:
        summary = asdict(self)
        summary["format"] = summary.pop("log_format")
        return summary


SUPPORTED_EXTENSIONS = {".lis": "LIS", ".dlis": "DLIS"}


def load_summary(path: Path) -> WellLogSummary:
    """Load a LIS/DLIS file and return a :class:`WellLogSummary` instance."""

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise WellLogError("Unsupported file type. Expected a .lis or .dlis file.")

    log_format = SUPPORTED_EXTENSIONS[suffix]
    notes: List[str] = []

    # Attempt to use dlisio when available – it provides a robust parser.
    try:
        summary = _load_with_dlisio(path, log_format)
        summary.notes.extend(notes)
        return summary
    except ImportError:
        notes.append("dlisio is not installed. Falling back to heuristic text parsing.")
    except Exception as exc:  # pragma: no cover - best effort fallback
        notes.append(f"dlisio parsing failed ({exc!s}). Using heuristic parser instead.")

    summary = _load_with_heuristics(path, log_format)
    summary.notes.extend(notes)
    return summary


def _load_with_dlisio(path: Path, log_format: str) -> WellLogSummary:
    """Attempt to parse the log using the `dlisio` package."""

    import importlib

    dlisio = importlib.import_module("dlisio")
    loader = dlisio.lis if log_format == "LIS" else dlisio.dlis
    files = loader.load(str(path))

    well_names: List[str] = []
    curve_names: List[str] = []
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None
    depth_unit: Optional[str] = None

    for log_file in files:
        # Extract well metadata when available
        objects = getattr(log_file, "objects", None)
        if callable(objects):
            try:
                for obj in objects():  # type: ignore[call-arg]
                    name = getattr(obj, "well_name", None) or getattr(obj, "name", None)
                    if isinstance(name, str):
                        well_names.append(name.strip())
            except TypeError:
                # Some versions of dlisio require a class filter – ignore gracefully
                pass

        # Curves are provided via the ``curves`` generator on the log file
        curves = getattr(log_file, "curves", None)
        if callable(curves):
            for curve in curves():
                curve_name = getattr(curve, "name", None)
                if isinstance(curve_name, str):
                    curve_names.append(curve_name.strip())
                if depth_unit is None:
                    depth_unit = getattr(curve, "dimension", None)
                data = getattr(curve, "data", None)
                if data is not None:
                    try:
                        iterable = list(data)
                    except TypeError:
                        iterable = []
                    if iterable:
                        curve_min = _safe_float(iterable[0])
                        curve_max = _safe_float(iterable[-1])
                        if curve_min is not None and (depth_min is None or curve_min < depth_min):
                            depth_min = curve_min
                        if curve_max is not None and (depth_max is None or curve_max > depth_max):
                            depth_max = curve_max

        # Many DLIS/LIS files expose well information in an attribute named ``well``
        well = getattr(log_file, "well", None)
        if well:
            for attr in ("name", "well", "well_name"):
                value = getattr(well, attr, None)
                if isinstance(value, str):
                    well_names.append(value.strip())

    notes = ["Parsed using dlisio."]
    return WellLogSummary(
        file_name=path.name,
        log_format=log_format,
        well_names=_unique_preserve(well_names),
        curve_names=_unique_preserve(curve_names),
        depth_min=depth_min,
        depth_max=depth_max,
        depth_unit=depth_unit,
        notes=notes,
    )


def _load_with_heuristics(path: Path, log_format: str) -> WellLogSummary:
    """Fallback parser that searches for common textual markers."""

    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("latin-1", errors="ignore")

    well_names = _extract_well_names(text)
    curve_names = _extract_curve_names(text)
    depth_min, depth_max = _extract_depths(text)

    notes = ["Parsed using heuristic text search. Results may be approximate."]

    return WellLogSummary(
        file_name=path.name,
        log_format=log_format,
        well_names=well_names or ["Not found"],
        curve_names=curve_names,
        depth_min=depth_min,
        depth_max=depth_max,
        depth_unit=None,
        notes=notes,
    )


def _extract_well_names(text: str) -> List[str]:
    patterns = [
        r"WELL(?:\s+NAME)?\s*[:=-]\s*([A-Za-z0-9_\-\s]{3,})",
        r"NAME\s*[:=-]\s*([A-Za-z0-9_\-\s]{3,})\s*WELL",
    ]
    names: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidate = match.group(1).strip()
            if candidate:
                names.append(candidate)
    return _unique_preserve(names)


def _extract_curve_names(text: str) -> List[str]:
    curves: List[str] = []
    for line in text.splitlines():
        if not line:
            continue
        lower = line.lower()
        if "curve" in lower or "mnemonic" in lower or "mnem" in lower:
            tokens = re.split(r"[\s,:;]+", line)
            for token in tokens:
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{1,15}", token):
                    curves.append(token)
    return _unique_preserve(curves)


def _extract_depths(text: str) -> tuple[Optional[float], Optional[float]]:
    start_patterns = [
        r"(?:start|from)\s*depth\s*[:=-]?\s*(-?\d+(?:\.\d+)?)",
        r"depth\s*\(start\)\s*[:=-]?\s*(-?\d+(?:\.\d+)?)",
    ]
    end_patterns = [
        r"(?:end|to)\s*depth\s*[:=-]?\s*(-?\d+(?:\.\d+)?)",
        r"depth\s*\(end\)\s*[:=-]?\s*(-?\d+(?:\.\d+)?)",
    ]

    depth_min = _search_first_float(text, start_patterns)
    depth_max = _search_first_float(text, end_patterns)

    if depth_min is None and depth_max is None:
        # Sometimes depth ranges are given as "DEPTH 1000-3500"
        range_match = re.search(r"depth\s*[:=-]?\s*(-?\d+(?:\.\d+)?)\s*[-to]+\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if range_match:
            depth_min = _safe_float(range_match.group(1))
            depth_max = _safe_float(range_match.group(2))

    return depth_min, depth_max


def _search_first_float(text: str, patterns: Iterable[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _safe_float(match.group(1))
    return None


def _safe_float(value: object) -> Optional[float]:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _unique_preserve(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        key = item.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            result.append(key)
    return result
