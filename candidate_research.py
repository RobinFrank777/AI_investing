"""Approved Candidate ResearchNote artifact validator and guarded applier.

This module does NOT retrieve external information and does NOT generate research.
It accepts only already-reviewed APPROVED research artifacts, validates them,
then delegates the actual cell-level write to observation_workbook.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, datetime
from pathlib import Path

from observation_workbook import update_candidate_research_note


OBSERVATION_DIR = Path.home() / "Documents" / "AI_investing_observation"
PRODUCTION_WORKBOOK_PATH = OBSERVATION_DIR / "AI_investing_observation.xlsx"
PRODUCTION_TEMP_PATH = (
    OBSERVATION_DIR / "AI_investing_observation.research-note.tmp.xlsx"
)
PRODUCTION_BACKUP_DIR = OBSERVATION_DIR / "backups"


def load_reviews(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise FileNotFoundError(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = payload.get("reviews") if isinstance(payload, dict) else payload

    if not isinstance(reviews, list) or not reviews:
        raise RuntimeError(
            "Research artifact must contain a non-empty review list."
        )

    return reviews


def validate_reviews(reviews: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    seen: set[tuple[date, str]] = set()

    for index, raw in enumerate(reviews, start=1):
        if not isinstance(raw, dict):
            raise RuntimeError(f"Review #{index} must be an object.")

        required = ("Date", "Ticker", "Status", "ResearchNote", "Sources")
        missing = [field for field in required if field not in raw]
        if missing:
            raise RuntimeError(
                f"Review #{index} missing fields: {', '.join(missing)}"
            )

        try:
            review_date = date.fromisoformat(str(raw["Date"]).strip())
        except ValueError as exc:
            raise RuntimeError(
                f"Review #{index} Date must be YYYY-MM-DD."
            ) from exc

        ticker = str(raw["Ticker"]).strip().upper()
        if not ticker:
            raise RuntimeError(f"Review #{index} Ticker must not be empty.")

        status = str(raw["Status"]).strip().upper()
        if status != "APPROVED":
            raise RuntimeError(
                f"Review #{index} Status must be APPROVED; got {status!r}."
            )

        note = str(raw["ResearchNote"]).strip()
        if not note:
            raise RuntimeError(
                f"Review #{index} ResearchNote must not be empty."
            )

        sources = raw["Sources"]
        if (
            not isinstance(sources, list)
            or not sources
            or any(not str(source).strip() for source in sources)
        ):
            raise RuntimeError(
                f"Review #{index} Sources must be a non-empty string list."
            )

        key = (review_date, ticker)
        if key in seen:
            raise RuntimeError(
                f"Duplicate research review key: {review_date} / {ticker}"
            )
        seen.add(key)

        normalized.append(
            {
                "Date": review_date,
                "Ticker": ticker,
                "Status": status,
                "ResearchNote": note,
                "Sources": [str(source).strip() for source in sources],
            }
        )

    return normalized


def _backup_path() -> Path:
    PRODUCTION_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    path = (
        PRODUCTION_BACKUP_DIR
        / f"AI_investing_observation.before-research-note-{timestamp}.xlsx"
    )
    if path.exists():
        raise RuntimeError(f"Backup path already exists: {path}")
    return path


def apply_reviews_to_production(
    reviews: list[dict[str, object]],
) -> tuple[list[int], Path]:
    if PRODUCTION_WORKBOOK_PATH.name != "AI_investing_observation.xlsx":
        raise RuntimeError("Unexpected production workbook filename.")
    if not PRODUCTION_WORKBOOK_PATH.is_file():
        raise FileNotFoundError(PRODUCTION_WORKBOOK_PATH)
    if PRODUCTION_TEMP_PATH.resolve() == PRODUCTION_WORKBOOK_PATH.resolve():
        raise RuntimeError("Research temp path must differ from production workbook.")

    if PRODUCTION_TEMP_PATH.exists():
        PRODUCTION_TEMP_PATH.unlink()

    shutil.copy2(PRODUCTION_WORKBOOK_PATH, PRODUCTION_TEMP_PATH)
    backup_path = _backup_path()

    rows: list[int] = []
    try:
        for review in reviews:
            rows.append(
                update_candidate_research_note(
                    PRODUCTION_TEMP_PATH,
                    date=review["Date"],
                    ticker=review["Ticker"],
                    research_note=review["ResearchNote"],
                    overwrite=False,
                    create_backup=False,
                )
            )

        shutil.copy2(PRODUCTION_WORKBOOK_PATH, backup_path)
        PRODUCTION_TEMP_PATH.replace(PRODUCTION_WORKBOOK_PATH)
        return rows, backup_path

    except Exception:
        if PRODUCTION_TEMP_PATH.exists():
            PRODUCTION_TEMP_PATH.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate/apply approved Candidate ResearchNote artifacts"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--validate",
        metavar="JSON",
        type=Path,
        help="Validate an approved research artifact only",
    )
    mode.add_argument(
        "--apply-production",
        metavar="JSON",
        type=Path,
        help="Apply an approved research artifact to production workbook",
    )
    parser.add_argument(
        "--confirm-production-write",
        action="store_true",
        help="Required second gate for --apply-production",
    )
    args = parser.parse_args()

    if args.confirm_production_write and not args.apply_production:
        parser.error(
            "--confirm-production-write is valid only with --apply-production"
        )
    if args.apply_production and not args.confirm_production_write:
        parser.error(
            "--apply-production requires --confirm-production-write"
        )

    artifact = args.validate or args.apply_production
    reviews = validate_reviews(load_reviews(artifact))

    print("APPROVED RESEARCH ARTIFACT")
    print("=" * 72)
    for review in reviews:
        print(
            f"{review['Date']}  {review['Ticker']:<8}  "
            f"{review['Status']}  Sources={len(review['Sources'])}"
        )
    print("=" * 72)

    if args.validate:
        print("PASS: research artifact validation completed")
        print("NO WORKBOOK WRITE WAS PERFORMED")
        return 0

    rows, backup_path = apply_reviews_to_production(reviews)
    print("\nPASS: RESEARCHNOTE PRODUCTION WRITE COMPLETED")
    print(f"Workbook : {PRODUCTION_WORKBOOK_PATH}")
    print(f"Backup   : {backup_path}")
    print(f"Rows     : {rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
