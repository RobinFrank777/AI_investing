"""Select the active market universe source without parsing its contents."""

import argparse
import sys
from pathlib import Path

import config
import universe_groups
import universe_manager


ALLOWED_MODES = ("single", "groups")
EMPTY_UNIVERSE_WARNING = "No enabled symbols found in active universe."


def _normalize_mode(mode):
    selected = config.UNIVERSE_MODE if mode is None else mode
    normalized = str(selected).strip().lower()
    if normalized not in ALLOWED_MODES:
        raise ValueError(
            "Unsupported universe mode "
            f"{selected!r}. Allowed values: {', '.join(ALLOWED_MODES)}"
        )
    return normalized


def _groups_path(groups_config_path):
    return Path(
        config.UNIVERSE_CONFIG_PATH
        if groups_config_path is None
        else groups_config_path
    )


def load_active_universe(mode=None, watchlist_path=None, groups_config_path=None):
    """Load symbols from the explicitly selected single or groups source."""
    selected_mode = _normalize_mode(mode)
    if selected_mode == "single":
        if watchlist_path is None:
            return universe_manager.load_universe()
        return universe_manager.load_universe(watchlist_path)

    config_path = _groups_path(groups_config_path)
    if not config_path.is_file():
        raise FileNotFoundError(
            "Groups mode requires a universe configuration file: "
            f"{config_path}"
        )
    return universe_groups.load_combined_universe(config_path)


def validate_active_universe(
    mode=None, watchlist_path=None, groups_config_path=None
):
    """Return a stable summary for the explicitly selected active source."""
    selected_mode = _normalize_mode(mode)
    if selected_mode == "single":
        if watchlist_path is None:
            source_summary = universe_manager.validate_universe()
        else:
            source_summary = universe_manager.validate_universe(watchlist_path)
        symbols = source_summary["symbols"]
        warnings = list(source_summary["warnings"])
        if not symbols and EMPTY_UNIVERSE_WARNING not in warnings:
            warnings.append(EMPTY_UNIVERSE_WARNING)
        return {
            "mode": selected_mode,
            "source_path": source_summary["source_path"],
            "symbol_count": len(symbols),
            "symbols": symbols,
            "warnings": warnings,
        }

    config_path = _groups_path(groups_config_path)
    if not config_path.is_file():
        raise FileNotFoundError(
            "Groups mode requires a universe configuration file: "
            f"{config_path}"
        )
    groups_summary = universe_groups.validate_universe_config(config_path)
    if groups_summary["invalid_groups"]:
        details = "; ".join(
            ", ".join(entry["reasons"])
            for entry in groups_summary["invalid_entries"]
        )
        raise ValueError(f"Invalid active universe groups: {details}")
    symbols = universe_groups.load_combined_universe(config_path)
    warnings = list(groups_summary["warnings"])
    if not symbols and EMPTY_UNIVERSE_WARNING not in warnings:
        warnings.append(EMPTY_UNIVERSE_WARNING)
    return {
        "mode": selected_mode,
        "source_path": groups_summary["source_path"],
        "symbol_count": len(symbols),
        "symbols": symbols,
        "warnings": warnings,
        "group_count": groups_summary["total_rows"],
        "enabled_group_count": groups_summary["enabled_groups"],
    }


def _build_parser():
    parser = argparse.ArgumentParser(description="Validate the active market universe.")
    parser.add_argument("--mode", help="Universe mode: single or groups")
    parser.add_argument("--watchlist", type=Path, help="Single-universe CSV path")
    parser.add_argument("--config", type=Path, help="Universe Groups config CSV path")
    return parser


def _print_summary(summary):
    print("Active Market Universe")
    print(f"Mode: {summary['mode']}")
    print(f"Source: {config.display_path(summary['source_path'])}")
    print(f"Symbols: {summary['symbol_count']}")
    print()
    for symbol in summary["symbols"]:
        print(symbol)
    if summary["warnings"]:
        print("\nWarnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")


def main(argv=None):
    arguments = _build_parser().parse_args(argv)
    try:
        summary = validate_active_universe(
            mode=arguments.mode,
            watchlist_path=arguments.watchlist,
            groups_config_path=arguments.config,
        )
        _print_summary(summary)
    except (FileNotFoundError, ValueError) as error:
        print(f"Active universe error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
