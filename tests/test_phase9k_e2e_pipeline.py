import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import ai_research_summary_builder
import candidate_report_builder
import daily_research_pipeline
import daily_research_snapshot
import factor_ranking
import research_candidate_selector
import research_dataset_validator
import research_explanation_engine
import research_pipeline_logger
import research_report_builder
import research_report_composer
import research_schema
import risk_factor_merge
import signal_engine
import universe_factor_runner
import universe_risk_runner


class Phase9KEndToEndPipelineTests(unittest.TestCase):
    def test_real_universe150_pipeline_generates_compatible_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = root / "results"
            logs = root / "logs"
            paths = {
                "factor_raw": results / "universe150_factor_raw.csv",
                "ranking": results / "universe150_factor_ranking.csv",
                "top_report": results / "universe150_research_report.csv",
                "signal": results / "universe150_signal.csv",
                "risk_raw": results / "universe150_risk_raw.csv",
                "research_raw": results / "universe150_research_raw.csv",
                "validation": results / "universe150_research_validation.csv",
                "candidates": results / "universe150_research_candidates.csv",
                "candidate_report": results / "universe150_candidate_report.csv",
                "snapshot": results / "universe150_daily_research_snapshot.csv",
                "explanation": results / "universe150_research_explanation.csv",
                "ai_summary": results / "universe150_ai_research_summary.csv",
                "markdown": results / "universe150_research_report.md",
                "pipeline_status": results / "daily_research_pipeline_status.csv",
            }

            steps = {
                "UniverseFactorRunner": lambda: universe_factor_runner.run_universe_factors(
                    output_path=paths["factor_raw"]
                ),
                "FactorRanking": lambda: factor_ranking.run_factor_ranking(
                    paths["factor_raw"], paths["ranking"]
                ),
                "ResearchReportBuilder": lambda: research_report_builder.run_research_report(
                    paths["ranking"], paths["top_report"]
                ),
                "SignalEngine": lambda: signal_engine.run_signal_engine(
                    paths["ranking"], paths["signal"]
                ),
                "UniverseRiskRunner": lambda: universe_risk_runner.run_universe_risk(
                    output_path=paths["risk_raw"]
                ),
                "RiskFactorMerge": lambda: risk_factor_merge.run_risk_factor_merge(
                    paths["factor_raw"], paths["risk_raw"], paths["research_raw"]
                ),
                "ResearchDatasetValidator": lambda: research_dataset_validator.validate_research_dataset(
                    paths["research_raw"], paths["validation"]
                ),
                "ResearchCandidateSelector": lambda: research_candidate_selector.run_candidate_selector(
                    paths["research_raw"], paths["candidates"]
                ),
                "CandidateReportBuilder": lambda: candidate_report_builder.run_candidate_report(
                    paths["candidates"],
                    paths["candidate_report"],
                    generation_date="2026-08-08",
                ),
                "DailyResearchSnapshot": lambda: daily_research_snapshot.run_daily_snapshot(
                    paths["candidate_report"],
                    paths["snapshot"],
                    generation_date="2026-08-08",
                ),
                "ResearchExplanationEngine": lambda: research_explanation_engine.run_explanation_engine(
                    paths["snapshot"], paths["explanation"]
                ),
                "AIResearchSummaryBuilder": lambda: ai_research_summary_builder.run_ai_research_summary_builder(
                    paths["explanation"], paths["ai_summary"]
                ),
                "ResearchReportComposer": lambda: research_report_composer.generate_research_report(
                    paths["ai_summary"], paths["markdown"]
                ),
            }

            real_log_writer = research_pipeline_logger.save_pipeline_log

            def save_temp_log(status, run_date=None):
                return real_log_writer(status, run_date=run_date, log_dir=logs)

            with mock.patch.object(
                daily_research_pipeline.research_pipeline_logger,
                "save_pipeline_log",
                side_effect=save_temp_log,
            ):
                result = daily_research_pipeline.run_daily_research_pipeline(
                    output_path=paths["pipeline_status"],
                    run_date="2026-08-08",
                    step_functions=steps,
                )

            status = result["status"]
            self.assertEqual(status["Status"].tolist(), ["PASS"] * 13)
            for name, path in paths.items():
                with self.subTest(artifact=name):
                    self.assertTrue(path.is_file(), str(path))
                    self.assertTrue(path.is_relative_to(root))

            log_path = logs / "daily_research_pipeline_20260808.json"
            self.assertTrue(log_path.is_file())

            factor_raw = pd.read_csv(paths["factor_raw"])
            ranking = pd.read_csv(paths["ranking"])
            signals = pd.read_csv(paths["signal"])
            research_raw = pd.read_csv(paths["research_raw"])
            candidates = pd.read_csv(paths["candidates"])
            snapshot = pd.read_csv(paths["snapshot"])
            explanations = pd.read_csv(paths["explanation"])
            ai_summary = pd.read_csv(paths["ai_summary"])

            self.assertEqual(len(factor_raw), 150)
            self.assertEqual(len(ranking), 150)
            self.assertEqual(len(signals), 150)
            self.assertEqual(len(research_raw), 150)
            self.assertGreater(len(candidates), 0)

            for frame in (factor_raw, ranking, signals, research_raw, candidates):
                self.assertIn("Ticker", frame.columns)
            normalized_signals = research_schema.normalize_research_schema(signals)
            self.assertIn("Signal", normalized_signals.columns)
            for frame in (research_raw, candidates, snapshot, explanations, ai_summary):
                self.assertIn("Signal", frame.columns)
            for frame in (ranking, signals, research_raw, candidates, snapshot, explanations, ai_summary):
                self.assertIn("Rank", frame.columns)
                self.assertIn("CompositeScore", frame.columns)
            for frame in (snapshot, explanations, ai_summary):
                self.assertIn("ReportDate", frame.columns)

            markdown = paths["markdown"].read_text(encoding="utf-8")
            self.assertIn("# AI_investing Research Report", markdown)
            self.assertIn("## Research Candidates", markdown)
            self.assertIn("Composite Score:", markdown)
            self.assertIn("Signal:", markdown)
            self.assertIn("Research Tone:", markdown)
            self.assertIn("Research Summary:", markdown)
            self.assertIn("AI Research Summary:", markdown)


if __name__ == "__main__":
    unittest.main()
