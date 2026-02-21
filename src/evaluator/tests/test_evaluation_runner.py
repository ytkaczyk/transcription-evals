"""
Unit tests for the EvaluationRunner class.
"""
import os
from unittest.mock import MagicMock
# file: snyk-ignore python/HardcodedNonCryptoSecret/test
import pytest
from app_types import AppContext, RuntimePaths
from evaluation_runner import EvaluationRunner


@pytest.fixture
def mock_global_context():
    """Fixture for creating a mock AppContext."""
    paths = RuntimePaths(
        inputs_dir=os.path.abspath("inputs"),
        intermediate_dir=os.path.abspath("intermediate"),
        outputs_dir=os.path.abspath("outputs"),
        eval_dir=os.path.abspath("model-tests")
    )
    mock_args = MagicMock()
    mock_args.lazy_transcription = False
    mock_config = {"models": [], "inputs": []}
    return AppContext(args=mock_args, config=mock_config, paths=paths)


class TestEvaluationRunner:
    """Tests for the EvaluationRunner class."""
    # pylint: disable=protected-access, redefined-outer-name

    def test_generate_output_stem(self, mock_global_context):
        """Test _generate_output_stem method."""
        evaluation_runner = EvaluationRunner(mock_global_context)
        stem = evaluation_runner._generate_output_stem(  # pylint: disable=protected-access
            "model", "label", "audio.mp3")
        assert stem == "model-label-audio"

        stem = evaluation_runner._generate_output_stem(  # pylint: disable=protected-access
            "model", None, "audio.mp3")
        assert stem == "model-audio"

    def test_generate_stats_filename(self, mock_global_context):
        """Test _generate_stats_filename method."""
        evaluation_runner = EvaluationRunner(mock_global_context)
        filename = evaluation_runner._generate_stats_filename(  # pylint: disable=protected-access
            "stem")
        assert filename == "stem-stats.json"

    def test_generate_transcript_filename(self, mock_global_context):
        """Test _generate_transcript_filename method."""
        evaluation_runner = EvaluationRunner(mock_global_context)
        filename = evaluation_runner._generate_transcript_filename(  # pylint: disable=protected-access
            "stem")
        assert filename == "stem-transcript.json"

    def test_validate_safe_path_valid(self, mock_global_context):
        """Test _validate_safe_path with a valid path."""
        evaluation_runner = EvaluationRunner(mock_global_context)
        base = os.path.abspath("base")
        file_path = "subdir/file.txt"

        # Should return joined path
        expected = os.path.abspath(os.path.join(base, file_path))
        result = evaluation_runner._validate_safe_path(  # pylint: disable=protected-access
            base, file_path)
        assert result == expected

    def test_validate_safe_path_traversal(self, mock_global_context):
        """Test _validate_safe_path detects traversal attempts."""
        evaluation_runner = EvaluationRunner(mock_global_context)
        base = os.path.abspath("base")
        file_path = "../outside.txt"

        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            evaluation_runner._validate_safe_path(
                base, file_path)  # pylint: disable=protected-access
