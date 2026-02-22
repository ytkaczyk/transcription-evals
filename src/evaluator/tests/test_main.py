"""
Unit tests for the main module.
"""
import argparse
from main import setup_paths, EvaluatorApp
from app_types import RuntimePaths


def test_setup_paths_with_template(tmp_path):
    """Test setup_paths with excel-report-template."""
    config_file = tmp_path / "config.json"
    config_file.touch()

    config = {
        "paths": {
            "inputs": "inputs",
            "outputs": "outputs",
            "excel-report-template": "template.xlsx"
        }
    }

    paths = setup_paths(str(config_file), config)

    assert isinstance(paths, RuntimePaths)
    assert paths.excel_report_template is not None
    assert paths.excel_report_template.endswith("template.xlsx")
    assert "template.xlsx" in paths.excel_report_template
    assert paths.eval_dir.endswith("config")


def test_setup_paths_without_template(tmp_path):
    """Test setup_paths without excel-report-template."""
    config_file = tmp_path / "config.json"
    config_file.touch()

    config = {
        "paths": {
            "inputs": "inputs",
            "outputs": "outputs"
        }
    }

    paths = setup_paths(str(config_file), config)

    assert isinstance(paths, RuntimePaths)
    assert paths.excel_report_template is None
    assert paths.eval_dir.endswith("config")


def _make_evaluator_app(tmp_path) -> EvaluatorApp:
    """Helper to create a minimal EvaluatorApp instance for testing."""
    args = argparse.Namespace(config_file=str(tmp_path / "config.json"), lazy_transcription=False)
    config: dict = {"inputs": [], "models": [], "paths": {"inputs": "inputs", "outputs": "outputs"}}
    paths = RuntimePaths(
        inputs_dir=str(tmp_path / "inputs"),
        intermediate_dir=str(tmp_path / "intermediate"),
        outputs_dir=str(tmp_path / "outputs"),
        eval_dir=str(tmp_path),
    )
    return EvaluatorApp(args, config, paths)


def test_get_safe_summary_markdown_returns_fallback_when_not_set(tmp_path):
    """get_safe_summary_markdown returns markdown bold+underline text when summary is None."""
    app = _make_evaluator_app(tmp_path)
    result = app.get_safe_summary_markdown()
    assert result == "**__Summary markdown is not available.__**"


def test_get_safe_summary_markdown_returns_summary_when_set(tmp_path):
    """get_safe_summary_markdown returns the actual summary markdown when set."""
    app = _make_evaluator_app(tmp_path)
    app._summary_markdown = "# My Report\nsome content"  # pylint: disable=protected-access
    result = app.get_safe_summary_markdown()
    assert result == "# My Report\nsome content"
