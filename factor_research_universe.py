"""Explicit, offline orchestration for an isolated formal research Universe."""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from config import DATA_DIR_PATH, REPO_ROOT, RESULTS_DIR_PATH
from factor_composite import build_composite_factor_table
from factor_normalization import build_normalized_factor_table
from factor_research_report import generate_factor_research_report
from factor_snapshot import build_factor_snapshot_table
from factor_validation import run_factor_validation
from factor_validation_robustness import (
    build_alternative_entry_validation, build_coverage_diagnostics,
    build_date_contribution_diagnostics, build_entry_comparison,
    build_regime_diagnostics, build_robust_return_statistics,
    build_symbol_influence_table, classify_market_regimes,
)
from universe_manager import load_universe, validate_universe


EXPECTED_RESEARCH_SYMBOLS = 50
MIN_FACTOR_ROWS = 60
MIN_FORWARD_VALIDATION_ROWS = 120
RESEARCH_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")
SAFETY_LINES = [
    "The Scale50 Universe is a research sample, not an investment recommendation.",
    "Universe inclusion does not approve a security for purchase.",
    "Successful market-data validation does not validate a strategy.",
    "Composite factor rankings are research diagnostics only.",
    "Historical validation does not prove future performance.",
    "No brokerage order is created by the Scale50 research workflow.",
]


def load_research_universe(universe_path, *, expected_symbol_count=50):
    """Load only the explicitly named Universe and enforce its exact size."""
    path = Path(universe_path)
    summary = validate_universe(path)
    symbols = load_universe(path)
    if summary["duplicate_rows"] or summary["invalid_rows"]:
        raise ValueError("Research Universe contains duplicate or invalid entries")
    if len(symbols) != expected_symbol_count:
        raise ValueError(
            f"Research Universe requires exactly {expected_symbol_count} symbols; "
            f"loaded {len(symbols)}"
        )
    return symbols


def _read_market_file(path):
    try:
        frame = pd.read_csv(path)
        if "Date" not in frame or "Close" not in frame:
            raise ValueError("Missing Date or Close column")
        dates = pd.to_datetime(frame["Date"], errors="coerce")
        closes = pd.to_numeric(frame["Close"], errors="coerce")
        valid = dates.notna() & closes.notna()
        if not valid.any():
            raise ValueError("No valid Date/Close rows")
        return frame, dates[valid], int(valid.sum())
    except Exception as error:
        raise ValueError(str(error)) from error


def inspect_research_market_data(symbols, *, data_dir=None):
    """Inspect every expected local CSV without modifying or repairing it."""
    directory = DATA_DIR_PATH if data_dir is None else Path(data_dir)
    requested = list(symbols)
    missing, invalid, with_data = [], [], []
    row_counts, first_dates, latest_dates = {}, {}, {}
    existing = valid_files = total_bytes = 0
    for symbol in requested:
        path = directory / f"{symbol}.csv"
        if not path.is_file():
            missing.append(symbol)
            continue
        existing += 1
        total_bytes += path.stat().st_size
        try:
            _, dates, count = _read_market_file(path)
            valid_files += 1; with_data.append(symbol); row_counts[symbol] = count
            first_dates[symbol] = dates.min().strftime("%Y-%m-%d")
            latest_dates[symbol] = dates.max().strftime("%Y-%m-%d")
        except ValueError as error:
            invalid.append({"symbol": symbol, "message": str(error)})
    factor_eligible = [symbol for symbol in requested if row_counts.get(symbol, 0) >= MIN_FACTOR_ROWS]
    forward_eligible = [symbol for symbol in requested if row_counts.get(symbol, 0) >= MIN_FORWARD_VALIDATION_ROWS]
    warnings = []
    if missing: warnings.append(f"Missing market data files: {len(missing)}")
    if invalid: warnings.append(f"Invalid market data files: {len(invalid)}")
    if len(factor_eligible) != len(requested): warnings.append("Incomplete factor-history eligibility")
    return {
        "symbol_count": len(requested), "existing_files": existing,
        "missing_files": len(missing), "valid_files": valid_files,
        "invalid_files": len(invalid), "symbols_with_data": with_data,
        "symbols_missing_data": missing, "invalid_entries": invalid,
        "row_counts": row_counts, "first_dates": first_dates,
        "latest_dates": latest_dates, "total_bytes": total_bytes,
        "factor_eligible_symbols": factor_eligible,
        "forward_validation_eligible_symbols": forward_eligible,
        "warnings": warnings,
    }


def build_research_output_paths(research_name="scale50", results_dir=None):
    if not isinstance(research_name, str) or not RESEARCH_NAME_PATTERN.fullmatch(research_name):
        raise ValueError("research_name must use lowercase letters, digits, underscores, or hyphens")
    directory = RESULTS_DIR_PATH if results_dir is None else Path(results_dir)
    stems = {
        "snapshot": "factor_snapshot.csv", "normalized": "factor_normalized.csv",
        "composite": "factor_composite.csv", "validation": "factor_validation.csv",
        "rank_ic": "factor_rank_ic.csv", "group_returns": "factor_group_returns.csv",
        "turnover": "factor_turnover.csv",
        "date_contributions": "factor_validation_date_contributions.csv",
        "robust_stats": "factor_validation_robust_stats.csv",
        "symbol_influence": "factor_validation_symbol_influence.csv",
        "entry_comparison": "factor_validation_entry_comparison.csv",
        "regimes": "factor_validation_regimes.csv",
        "coverage": "factor_validation_coverage.csv",
        "report": "factor_report.html",
        "report_json": "factor_report.json",
        "summary": "factor_research_summary.json",
    }
    return {key: directory / f"{research_name}_{stem}" for key, stem in stems.items()}


def _display(path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return path.name


def _json_market(inspection):
    return {
        key: value for key, value in inspection.items()
        if key not in ("factor_eligible_symbols", "forward_validation_eligible_symbols")
    } | {
        "factor_eligible_count": len(inspection["factor_eligible_symbols"]),
        "forward_validation_eligible_count": len(inspection["forward_validation_eligible_symbols"]),
    }


def run_factor_research_universe(
    universe_path, *, research_name="scale50", start_date=None, end_date=None,
    offline=True, require_complete_data=True,
):
    if not offline:
        raise ValueError("Phase 7 supports offline research runs only")
    symbols = load_research_universe(universe_path)
    inspection = inspect_research_market_data(symbols)
    invalid_symbols = [entry["symbol"] for entry in inspection["invalid_entries"]]
    ineligible = [s for s in symbols if s not in inspection["factor_eligible_symbols"]]
    affected = list(dict.fromkeys(inspection["symbols_missing_data"] + invalid_symbols + ineligible))
    if require_complete_data and affected:
        raise ValueError(
            f"Incomplete research data: missing symbol count={inspection['missing_files']}; "
            f"invalid symbol count={inspection['invalid_files']}; affected symbols={affected}"
        )
    used = list(inspection["factor_eligible_symbols"])
    paths = build_research_output_paths(research_name)
    snapshot = build_factor_snapshot_table(
        used, include_runtime_sources=False
    )
    normalized = build_normalized_factor_table(snapshot)
    composite = build_composite_factor_table(normalized)
    market_data = {}
    for symbol in used:
        frame, _, _ = _read_market_file(DATA_DIR_PATH / f"{symbol}.csv")
        market_data[symbol] = frame
    validation_run = run_factor_validation(
        used, market_data, start_date=start_date, end_date=end_date,
        rebalance_frequency="monthly",
        output_paths={
            name: paths[name]
            for name in ("validation", "rank_ic", "group_returns", "turnover")
        },
    )
    validation = validation_run["validation"]
    rank_ic = validation_run["rank_ic"]
    groups = validation_run["group_returns"]
    turnover = validation_run["turnover"]
    validation_summary = validation_run["summary"]
    next_close = build_alternative_entry_validation(validation, market_data)
    date_contributions = build_date_contribution_diagnostics(groups)
    robust_stats = build_robust_return_statistics(groups)
    symbol_influence = build_symbol_influence_table(validation)
    entry_comparison = build_entry_comparison(validation, next_close)
    spy = market_data.get("SPY")
    regimes = classify_market_regimes(
        validation.RebalanceDate.drop_duplicates().tolist(), spy
    )
    regime_results = build_regime_diagnostics(validation, regimes)
    coverage = build_coverage_diagnostics(validation)
    tables = {
        "snapshot": snapshot, "normalized": normalized,
        "composite": composite,
        "date_contributions": date_contributions, "robust_stats": robust_stats,
        "symbol_influence": symbol_influence,
        "entry_comparison": entry_comparison, "regimes": regime_results,
        "coverage": coverage,
    }
    for name, table in tables.items():
        paths[name].parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(paths[name], index=False, encoding="utf-8")
    report_result = generate_factor_research_report(
        validation_run["output_paths"],
        {
            name: paths[name] for name in ("robust_stats", "regimes", "coverage")
        },
        universe="Scale50" if research_name == "scale50" else research_name,
        html_path=paths["report"], json_path=paths["report_json"],
    )
    warnings = list(inspection["warnings"])
    if spy is None:
        warnings.append("Local SPY data unavailable; regime classification used no benchmark")
    complete = len(used) == EXPECTED_RESEARCH_SYMBOLS and not affected
    if not complete: warnings.append("Incomplete research Universe run")
    summary = {
        "research_name": research_name, "universe_path": _display(universe_path),
        "symbols_requested": EXPECTED_RESEARCH_SYMBOLS,
        "symbols_loaded": len(symbols), "symbols_used": used,
        "complete_data": complete, "market_data": _json_market(inspection),
        "factor_snapshot": {"rows": len(snapshot)},
        "normalization": {"rows": len(normalized)},
        "composite": {"rows": len(composite)},
        "validation": validation_summary,
        "factor_report": report_result["report"],
        "robustness": {"regime_rows": len(regime_results)},
        "outputs": {key: _display(path) for key, path in paths.items()},
        "warnings": warnings, "safety": list(SAFETY_LINES),
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return summary


def _print_inspection(symbols, inspection):
    print("Scale50 Research Universe Inspection")
    print(f"Symbols: {len(symbols)}")
    for key in ("existing_files", "missing_files", "valid_files", "invalid_files"):
        print(f"{key.replace('_', ' ').title()}: {inspection[key]}")
    print(f"Factor Eligible: {len(inspection['factor_eligible_symbols'])}")
    print(f"Forward Validation Eligible: {len(inspection['forward_validation_eligible_symbols'])}")
    for line in SAFETY_LINES: print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an explicit research Universe")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--name", default="scale50")
    parser.add_argument("--start"); parser.add_argument("--end")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--allow-incomplete", action="store_true")
    try:
        args = parser.parse_args(argv)
        symbols = load_research_universe(args.universe)
        if args.inspect_only:
            _print_inspection(symbols, inspect_research_market_data(symbols))
            return 0
        summary = run_factor_research_universe(
            args.universe, research_name=args.name,
            start_date=args.start, end_date=args.end, offline=True,
            require_complete_data=not args.allow_incomplete,
        )
        print("Scale50 Factor Research")
        print(f"Complete Data: {summary['complete_data']}")
        print(f"Symbols Used: {len(summary['symbols_used'])}")
        for line in SAFETY_LINES: print(line)
        return 0
    except (FileNotFoundError, ValueError, OSError, pd.errors.ParserError) as error:
        print(f"Research Universe error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__": raise SystemExit(main())
