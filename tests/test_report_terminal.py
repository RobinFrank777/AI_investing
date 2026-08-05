from pathlib import Path

import report_terminal
from report_terminal import generate_terminal_report as build_terminal_report


def test_build_terminal_report_creates_expected_html(monkeypatch, tmp_path):
    output_path = tmp_path / "ai_terminal_report.html"
    monkeypatch.setattr(report_terminal, "OUTPUT_PATH", output_path)

    generated_path = build_terminal_report()

    assert generated_path == output_path
    assert Path(generated_path).exists()

    html = output_path.read_text(encoding="utf-8")
    assert "AI_investing Daily Research Terminal" in html
    assert "Top Opportunities" in html
    assert "Model Portfolio" in html
    assert "Order Review" in html
