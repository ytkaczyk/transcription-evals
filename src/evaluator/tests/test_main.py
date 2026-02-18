"""
Unit tests for the main module.
"""
from main import setup_paths
from evaluation_runner_types import RuntimePaths


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

    # We mock os.path.abspath to behave predictably relative to tmp_path for the config dir
    # But setup_paths uses os.path.dirname(os.path.abspath(config_path))

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
