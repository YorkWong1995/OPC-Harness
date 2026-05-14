"""测试轻量影响分析。"""

from src.opc.knowledge.impact_analyzer import ImpactAnalyzer


def test_impact_analyzer_reports_related_files_and_tests(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "config.py").write_text("VALUE = 1\n", encoding="utf-8")
    (src_dir / "app.py").write_text("from src import config\n\ndef run():\n    return config.VALUE\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_config.py").write_text("import config\n", encoding="utf-8")

    result = ImpactAnalyzer(tmp_path).analyze(["src/config.py"])

    assert result.target_files == ["src/config.py"]
    assert "src/app.py" in result.related_files
    assert "src/app.py" in result.possible_callers
    assert "tests/test_config.py" in result.related_tests
    assert "python -m pytest tests/test_config.py" in result.validation_commands
    assert any("dependent file" in risk for risk in result.risk_points)
