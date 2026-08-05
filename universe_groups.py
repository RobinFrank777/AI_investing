"""Composable, opt-in market universe groups."""

import re
import sys
from pathlib import Path

import pandas as pd

from config import REPO_ROOT, display_path
from universe_manager import DISABLED_VALUES, ENABLED_VALUES, load_universe


PROJECT_ROOT = REPO_ROOT
REQUIRED_COLUMNS = ("Universe", "Enabled", "File")
GROUP_NAME_PATTERN = re.compile(r"^[a-z0-9_-]{1,50}$")


def _read_config(config_path):
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Universe group config not found: {path}")
    try:
        frame = pd.read_csv(path)
    except Exception as error:
        raise ValueError(f"Unable to read universe group config: {path}") from error

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            "Universe group config is missing required column(s): "
            + ", ".join(missing)
        )
    return path, frame


def _enabled_state(value):
    if value is None or pd.isna(value):
        return False, True
    normalized = str(value).strip().lower()
    if normalized in ENABLED_VALUES:
        return True, True
    if normalized in DISABLED_VALUES or not normalized:
        return False, True
    return False, False


def _safe_group_path(value):
    if value is None or pd.isna(value) or not str(value).strip():
        raise ValueError("File path is empty.")

    raw = str(value).strip()
    if "://" in raw or raw.lower().startswith("file:"):
        raise ValueError("URLs are not allowed.")

    relative_path = Path(raw)
    if relative_path.is_absolute():
        raise ValueError("Absolute paths are not allowed.")
    if ".." in relative_path.parts:
        raise ValueError("Parent path components are not allowed.")
    if relative_path.suffix.lower() != ".csv":
        raise ValueError("Universe group files must use the .csv extension.")

    root = PROJECT_ROOT.resolve()
    resolved = (root / relative_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("File path escapes the project root.") from error
    return resolved


def _parse_config(config_path):
    source_path, frame = _read_config(config_path)
    groups = []
    duplicates = []
    invalid_entries = []
    warnings = []
    seen_names = set()

    for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
        raw_name = row["Universe"]
        name = "" if raw_name is None or pd.isna(raw_name) else str(raw_name).strip().lower()
        enabled, recognized = _enabled_state(row["Enabled"])
        if not recognized:
            warnings.append(
                f"Row {row_number}: unrecognized Enabled value "
                f"{row['Enabled']!r}; treated as disabled."
            )

        reasons = []
        if not GROUP_NAME_PATTERN.fullmatch(name):
            reasons.append(
                "Universe must use 1-50 lowercase letters, digits, underscores, or hyphens."
            )
        elif name in seen_names:
            reasons.append(f"Duplicate Universe name: {name}")
            if name not in duplicates:
                duplicates.append(name)

        file_path = None
        try:
            file_path = _safe_group_path(row["File"])
        except ValueError as error:
            reasons.append(str(error))

        if reasons:
            invalid_entries.append(
                {
                    "row": row_number,
                    "universe": raw_name,
                    "file": row["File"],
                    "reasons": reasons,
                }
            )
            continue

        seen_names.add(name)
        groups.append(
            {"name": name, "enabled": enabled, "file_path": file_path}
        )

    return {
        "source_path": source_path,
        "total_rows": len(frame),
        "groups": groups,
        "duplicates": duplicates,
        "invalid_entries": invalid_entries,
        "warnings": warnings,
    }


def load_universe_config(config_path):
    """Load a structurally valid group config without reading group symbols."""
    parsed = _parse_config(config_path)
    if parsed["invalid_entries"]:
        details = "; ".join(
            f"row {entry['row']}: {', '.join(entry['reasons'])}"
            for entry in parsed["invalid_entries"]
        )
        raise ValueError(f"Invalid universe group config: {details}")
    return parsed["groups"]


def validate_universe_config(config_path):
    """Return a stable validation summary, including enabled group files."""
    parsed = _parse_config(config_path)
    invalid_entries = list(parsed["invalid_entries"])
    invalid_names = {
        str(entry["universe"]).strip().lower()
        for entry in invalid_entries
        if entry["universe"] is not None
    }

    for group in parsed["groups"]:
        if not group["enabled"]:
            continue
        try:
            load_universe(group["file_path"])
        except (FileNotFoundError, ValueError) as error:
            invalid_names.add(group["name"])
            invalid_entries.append(
                {
                    "row": None,
                    "universe": group["name"],
                    "file": group["file_path"],
                    "reasons": [f"Enabled group is invalid: {error}"],
                }
            )

    valid_groups = sum(
        1 for group in parsed["groups"] if group["name"] not in invalid_names
    )
    enabled_groups = sum(1 for group in parsed["groups"] if group["enabled"])
    warnings = list(parsed["warnings"])
    if enabled_groups == 0:
        warnings.append("No enabled universe groups were found.")

    return {
        "source_path": parsed["source_path"],
        "total_rows": parsed["total_rows"],
        "enabled_groups": enabled_groups,
        "disabled_groups": parsed["total_rows"] - enabled_groups,
        "valid_groups": valid_groups,
        "invalid_groups": len(invalid_entries),
        "groups": parsed["groups"],
        "duplicates": parsed["duplicates"],
        "invalid_entries": invalid_entries,
        "warnings": warnings,
    }


def load_combined_universe(config_path):
    """Load enabled groups in config order and deduplicate their symbols."""
    groups = load_universe_config(config_path)
    combined = []
    seen = set()
    for group in groups:
        if not group["enabled"]:
            continue
        try:
            symbols = load_universe(group["file_path"])
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"Universe Group {group['name']!r} could not be loaded: {error}"
            ) from error
        except ValueError as error:
            raise ValueError(
                f"Universe Group {group['name']!r} could not be loaded: {error}"
            ) from error
        for symbol in symbols:
            if symbol not in seen:
                seen.add(symbol)
                combined.append(symbol)
    return combined


def _print_summary(summary, symbols):
    print("Universe Groups Validation")
    print(f"Config: {display_path(summary['source_path'])}")
    print(f"Groups: {summary['total_rows']}")
    print(f"Enabled: {summary['enabled_groups']}")
    print(f"Disabled: {summary['disabled_groups']}")
    print(f"Invalid: {summary['invalid_groups']}")
    print("\nEnabled Groups:")
    for group in summary["groups"]:
        if group["enabled"]:
            print(f"{group['name']} -> {display_path(group['file_path'])}")
    print("\nCombined Symbols:")
    for symbol in symbols:
        print(symbol)
    if summary["warnings"]:
        print("\nWarnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Usage: python universe_groups.py <config.csv>", file=sys.stderr)
        return 2
    try:
        summary = validate_universe_config(arguments[0])
        if summary["invalid_groups"]:
            details = "; ".join(
                ", ".join(entry["reasons"])
                for entry in summary["invalid_entries"]
            )
            raise ValueError(f"Universe group validation failed: {details}")
        symbols = load_combined_universe(arguments[0])
        _print_summary(summary, symbols)
    except (FileNotFoundError, ValueError) as error:
        print(f"Universe Groups error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
