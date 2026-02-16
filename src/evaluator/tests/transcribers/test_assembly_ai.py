# file: snyk-ignore python/HardcodedNonCryptoSecret/test
# deepcode-ignore-file
"""
Unit tests for AssemblyAITranscriber.
"""
from unittest.mock import patch, MagicMock
import pytest
import assemblyai as aai

from transcribers.assembly_ai import AssemblyAITranscriber
from transcribers.types import TranscriptResult


class TestAssemblyAITranscriber:
    """
    Test suite for AssemblyAITranscriber.
    """

    @pytest.fixture
    def mock_env_api_key(self, monkeypatch):
        """Sets the ASSEMBLYAI_API_KEY environment variable."""
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test_env_key")

    @pytest.fixture
    def mock_aai_transcriber_cls(self):
        """Mocks the assemblyai.Transcriber class."""
        with patch("transcribers.assembly_ai.aai.Transcriber") as mock:
            yield mock

    @pytest.fixture
    def mock_aai_settings(self):
        """Mocks the assemblyai.settings."""
        with patch("transcribers.assembly_ai.aai.settings") as mock:
            yield mock

    def test_init_raises_error_no_key(self, monkeypatch):
        """Test initialization fails without API key."""
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="AssemblyAI API key is required"):
            AssemblyAITranscriber(api_key=None)

    def test_init_with_env_key(self, mock_env_api_key, mock_aai_transcriber_cls, mock_aai_settings):
        """Test initialization with environment variable."""
        # pylint: disable=unused-argument
        transcriber = AssemblyAITranscriber()
        assert transcriber.api_key == "test_env_key"
        # aai.settings.api_key is set during initialization
        assert aai.settings.api_key == "test_env_key"
        mock_aai_transcriber_cls.assert_called_once()
        # assert transcriber.prompt is None  <-- Removed

    def test_init_with_explicit_key(self, mock_aai_transcriber_cls, mock_aai_settings):
        """Test initialization with explicit API key."""
        # pylint: disable=unused-argument
        transcriber = AssemblyAITranscriber(
            api_key="explicit_key")
        assert transcriber.api_key == "explicit_key"
        assert aai.settings.api_key == "explicit_key"
        # assert transcriber.prompt == "test prompt" <-- Removed prompt from init check

    def test_name_property(self, mock_env_api_key, mock_aai_transcriber_cls):
        # pylint: disable=unused-argument
        """Test the name property."""
        transcriber = AssemblyAITranscriber()
        assert transcriber.name == "AssemblyAI"

    @patch("transcribers.assembly_ai.aai.TranscriptionConfig")
    def test_transcribe_success(self, mock_config_cls, mock_env_api_key, mock_aai_transcriber_cls):
        """Test successful transcription with options."""
        # pylint: disable=unused-argument
        transcriber = AssemblyAITranscriber()
        mock_transcriber_instance = mock_aai_transcriber_cls.return_value

        # Mock result
        mock_transcript = MagicMock()
        mock_transcript.status = aai.TranscriptStatus.completed
        mock_transcript.audio_duration = 10.5

        # Mocks for conversation items (utterances)
        # Utterance start is in milliseconds
        u1 = MagicMock(start=1000, speaker="A", text="Hello")
        u2 = MagicMock(start=65000, speaker="B", text="World")  # 1 min 5 sec

        mock_transcript.utterances = [u1, u2]
        mock_transcriber_instance.transcribe.return_value = mock_transcript

        transcriber.transcribe(
            "test.mp3", options={"prompt": "custom prompt"})

        # Verify config creation
        mock_config_cls.assert_called_once_with(
            speech_models=["universal-3-pro"],
            speaker_labels=True,
            prompt="custom prompt"
        )

        # Verify transcribe call
        mock_transcriber_instance.transcribe.assert_called_once()
        args, kwargs = mock_transcriber_instance.transcribe.call_args
        assert args[0] == "test.mp3"
        assert kwargs["config"] == mock_config_cls.return_value

    @patch("transcribers.assembly_ai.aai.TranscriptionConfig")
    def test_transcribe_default_prompt(self, mock_config_cls, mock_env_api_key, mock_aai_transcriber_cls):
        """Test transcription uses default prompt when none provided."""
        # pylint: disable=unused-argument
        transcriber = AssemblyAITranscriber()
        mock_transcriber_instance = mock_aai_transcriber_cls.return_value

        # Mock result
        mock_transcript = MagicMock()
        mock_transcript.status = aai.TranscriptStatus.completed
        mock_transcript.audio_duration = 10.0

        # Mocks for conversation items (utterances)
        u1 = MagicMock(start=1000, speaker="A", text="Hello")

        mock_transcript.utterances = [u1]
        mock_transcriber_instance.transcribe.return_value = mock_transcript

        # Call transcribe with empty options
        result = transcriber.transcribe("test.mp3", options={})

        # Verify config creation with default prompt
        mock_config_cls.assert_called_once_with(
            speech_models=["universal-3-pro"],
            speaker_labels=True,
            prompt="Transcribe this audio, Transcribe verbatim."
        )

        # Verify result format
        assert isinstance(result, TranscriptResult)
        assert result.name == "AssemblyAI"
        assert result.duration == 10.0
        assert len(result.conversation) == 1

        assert result.conversation[0].timestamp == "00:00:01"
        assert result.conversation[0].person == "Speaker A"
        assert result.conversation[0].content == "Hello"

    def test_transcribe_error(self, mock_env_api_key, mock_aai_transcriber_cls):
        """Test transcription failure."""
        # pylint: disable=unused-argument
        transcriber = AssemblyAITranscriber()
        mock_transcriber_instance = mock_aai_transcriber_cls.return_value

        mock_transcript = MagicMock()
        mock_transcript.status = aai.TranscriptStatus.error
        mock_transcript.error = "Mock Error"

        mock_transcriber_instance.transcribe.return_value = mock_transcript

        with pytest.raises(RuntimeError, match="Transcription failed: Mock Error"):
            transcriber.transcribe("test.mp3")

    def test_format_timestamp(self, mock_env_api_key, mock_aai_transcriber_cls):
        """Test timestamp formatting."""
        # pylint: disable=unused-argument, protected-access
        transcriber = AssemblyAITranscriber()
        # 3661000 ms = 3661 s = 1h 1m 1s
        assert transcriber._format_timestamp(3661000) == "01:01:01"

    @patch("transcribers.assembly_ai.aai.TranscriptionConfig")
    def test_transcribe_with_options(self, mock_config_cls, mock_env_api_key, mock_aai_transcriber_cls):
        """Test transcribe with custom options."""
        # pylint: disable=unused-argument
        transcriber = AssemblyAITranscriber()
        mock_transcriber_instance = mock_aai_transcriber_cls.return_value

        mock_transcript = MagicMock()
        mock_transcript.status = aai.TranscriptStatus.completed
        mock_transcript.audio_duration = 10.0
        mock_transcript.utterances = []
        mock_transcript.text = "Test"

        mock_transcriber_instance.transcribe.return_value = mock_transcript

        custom_options = {"speech_models": ["best"], "language_code": "es"}
        transcriber.transcribe("test.mp3", options=custom_options)

        # Verify config creation
        mock_config_cls.assert_called_once()
        call_kwargs = mock_config_cls.call_args[1]

        assert call_kwargs['speech_models'] == ["best"]
        assert call_kwargs['language_code'] == "es"
        assert call_kwargs['speaker_labels'] is True
