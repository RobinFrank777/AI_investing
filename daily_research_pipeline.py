"""Orchestrate the fixed Universe150 daily research workflow."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd

import ai_research_summary_builder
import candidate_report_builder
import daily_research_snapshot
import factor_ranking
import research_candidate_selector
import research_dataset_validator
import research_explanation_engine
import research_report_builder
import research_report_composer
import risk_factor_merge
import research_pipeline_logger
import signal_engine
import universe_factor_runner
import universe_risk_runner


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "results" / "daily_research_pipeline_status.csv"
STATUS_COLUMNS = ("StepName", "Status", "Message", "RunDate")
STEP_NAMES = (
    "UniverseFactorRunner",
    "FactorRanking",
    "ResearchReportBuilder",
    "SignalEngine",
    "UniverseRiskRunner",
    "RiskFactorMerge",
    "ResearchDatasetValidator",
    "ResearchCandidateSelector",
    "CandidateReportBuilder",
    "DailyResearchSnapshot",
    "ResearchExplanationEngine",
    "AIResearchSummaryBuilder",
    "ResearchReportComposer",
)


def _default_step_functions():
    return {
        "UniverseFactorRunner": universe_factor_runner.run_universe_factors,
        "FactorRanking": factor_ranking.run_factor_ranking,
        "ResearchReportBuilder": research_report_builder.run_research_report,
        "SignalEngine": signal_engine.run_signal_engine,
        "UniverseRiskRunner": universe_risk_runner.run_universe_risk,
        "RiskFactorMerge": risk_factor_merge.run_risk_factor_merge,
        "ResearchDatasetValidator": (
            research_dataset_validator.validate_research_dataset
        ),
        "ResearchCandidateSelector": (
            research_candidate_selector.run_candidate_selector
        ),
        "CandidateReportBuilder": candidate_report_builder.run_candidate_report,
        "DailyResearchSnapshot": daily_research_snapshot.run_daily_snapshot,
        "ResearchExplanationEngine": (
            research_explanation_engine.run_explanation_engine
        ),
        "AIResearchSummaryBuilder": (
            ai_research_summary_builder.run_ai_research_summary_builder
        ),
        "ResearchReportComposer": research_report_composer.generate_research_report,
    }


def _run_date(value):
    if value is None:
        return date.today().isoformat()
    try:
        return pd.to_datetime(value, errors="raise").date().isoformat()
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("run_date must be a valid date") from error


def _save_status(status, output_path):
    path = DEFAULT_OUTPUT_PATH if output_path is None else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    status.loc[:, STATUS_COLUMNS].to_csv(path, index=False)
    return path


def _validation_failure(result):
    if not isinstance(result, pd.DataFrame):
        return "validator returned an invalid result"
    required = {"CheckItem", "Value", "Status"}
    if not required.issubset(result.columns):
        return "validator result is missing required fields"
    overall = result.loc[result["CheckItem"] == "OverallStatus"]
    if overall.empty:
        return "validator result is missing OverallStatus"
    value = str(overall.iloc[0]["Value"]).strip().upper()
    status = str(overall.iloc[0]["Status"]).strip().upper()
    if value == "FAILED" or status == "FAILED":
        return "research dataset validation failed"
    return None


def run_daily_research_pipeline(
    *, output_path=None, run_date=None, step_functions=None
):
    """Run the fixed workflow and return its status artifact."""
    functions = _default_step_functions()
    if step_functions is not None:
        if not isinstance(step_functions, dict):
            raise TypeError("step_functions must be a dictionary")
        unknown = sorted(set(step_functions) - set(STEP_NAMES))
        if unknown:
            raise ValueError("unknown pipeline steps: " + ", ".join(unknown))
        functions.update(step_functions)

    current_date = _run_date(run_date)
    rows = []
    blocked_by = None
    for step_name in STEP_NAMES:
        if blocked_by is not None:
            rows.append(
                {
                    "StepName": step_name,
                    "Status": "SKIPPED",
                    "Message": f"dependency failed: {blocked_by}",
                    "RunDate": current_date,
                }
            )
            continue
        try:
            result = functions[step_name]()
        except Exception as error:  # Pipeline boundary records step failures.
            message = str(error).strip() or error.__class__.__name__
            rows.append(
                {
                    "StepName": step_name,
                    "Status": "FAILED",
                    "Message": message,
                    "RunDate": current_date,
                }
            )
            blocked_by = step_name
        else:
            validation_error = (
                _validation_failure(result)
                if step_name == "ResearchDatasetValidator"
                else None
            )
            if validation_error is not None:
                rows.append(
                    {
                        "StepName": step_name,
                        "Status": "FAILED",
                        "Message": validation_error,
                        "RunDate": current_date,
                    }
                )
                blocked_by = step_name
            else:
                message = (
                    "completed" if result is not None else "completed with empty result"
                )
                rows.append(
                    {
                        "StepName": step_name,
                        "Status": "PASS",
                        "Message": message,
                        "RunDate": current_date,
                    }
                )

    status = pd.DataFrame(rows, columns=STATUS_COLUMNS)
    path = _save_status(status, output_path)
    research_pipeline_logger.save_pipeline_log(status, run_date=current_date)
    return {"status": status, "output_path": str(path)}


def main():
    try:
        result = run_daily_research_pipeline()
    except (ValueError, TypeError, OSError) as error:
        print(f"Daily research pipeline error: {error}", file=sys.stderr)
        return 1
    status = result["status"]
    print("AI_investing Daily Research Pipeline")
    print(f"PASS: {(status['Status'] == 'PASS').sum()}")
    print(f"FAILED: {(status['Status'] == 'FAILED').sum()}")
    print(f"SKIPPED: {(status['Status'] == 'SKIPPED').sum()}")
    print(f"Output: {result['output_path']}")
    return 0 if "FAILED" not in status["Status"].values else 1


if __name__ == "__main__":
    raise SystemExit(main())
