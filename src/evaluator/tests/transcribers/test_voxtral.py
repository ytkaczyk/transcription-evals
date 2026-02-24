# file: snyk-ignore python/HardcodedNonCryptoSecret/test
"""
Unit tests for MistralVoxtralTranscriber.
"""
# pylint: disable=unused-argument
from unittest.mock import patch, MagicMock, mock_open
import pytest

from transcribers.mistral_voxtral import MistralVoxtralTranscriber
from transcribers.types import TranscriptResult


class TestMistralVoxtralTranscriber:
    """
    Test suite for MistralVoxtralTranscriber.
    """

    @pytest.fixture
    def mock_env_api_key(self, monkeypatch):
        """Sets the MISTRAL_API_KEY environment variable."""
        monkeypatch.setenv("MISTRAL_API_KEY", "test_env_key")

    @pytest.fixture
    def mock_mistral_cls(self):
        """Mocks the mistralai.Mistral class."""
        with patch("transcribers.mistral_voxtral.Mistral") as mock:
            yield mock

    def test_init_raises_error_no_key(self, monkeypatch):
        """Test initialization fails without API key."""
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Mistral API key is required"):
            MistralVoxtralTranscriber(api_key=None)

    def test_init_with_env_key(self, mock_env_api_key, mock_mistral_cls):
        """Test initialization with environment variable."""
        transcriber = MistralVoxtralTranscriber()
        assert transcriber.api_key == "test_env_key"
        mock_mistral_cls.assert_called_once_with(api_key="test_env_key")

    def test_init_with_explicit_key(self, mock_mistral_cls):
        """Test initialization with explicit API key."""
        transcriber = MistralVoxtralTranscriber(api_key="explicit_key")
        assert transcriber.api_key == "explicit_key"
        mock_mistral_cls.assert_called_once_with(api_key="explicit_key")

    def test_name_property(self, mock_env_api_key, mock_mistral_cls):
        """Test the name property."""
        transcriber = MistralVoxtralTranscriber()
        assert transcriber.name == "Voxtral"

    @patch("transcribers.mistral_voxtral.open", new_callable=mock_open, read_data=b"audio_bytes")
    async def test_transcribe_success_segments(self, mock_file, mock_env_api_key, mock_mistral_cls):
        """Test successful transcription with segments and diarization."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_usage = MagicMock()
        mock_usage.prompt_audio_seconds = 12.0
        mock_response.usage = mock_usage
        mock_response.segments = [
            MagicMock(start=1.0, speaker=0, text="Hello"),
            MagicMock(start=5.5, speaker=None, speaker_id=None, text="World"),
        ]
        mock_response.words = None
        mock_response.text = None
        mock_client.audio.transcriptions.complete.return_value = mock_response
        mock_mistral_cls.return_value = mock_client

        transcriber = MistralVoxtralTranscriber()
        result = await transcriber.transcribe("test.mp3")

        assert isinstance(result, TranscriptResult)
        assert result.name == "Voxtral"
        assert result.duration == 12.0
        assert len(result.conversation) == 2

        first = result.conversation[0]
        assert first.timestamp == "00:00:01"
        assert first.person == "Speaker 0"
        assert first.content == "Hello"

        second = result.conversation[1]
        assert second.timestamp == "00:00:05"
        assert second.person == "Unknown"
        assert second.content == "World"

        call_kwargs = mock_client.audio.transcriptions.complete.call_args[1]
        assert call_kwargs["model"] == "voxtral-mini-latest"
        assert call_kwargs["diarize"] is True
        assert call_kwargs["timestamp_granularities"] == ["segment"]
        assert call_kwargs["file"]["file_name"] == "test.mp3"

    @patch("transcribers.mistral_voxtral.open", new_callable=mock_open, read_data=b"audio_bytes")
    async def test_transcribe_language_removes_timestamp_granularities(
        self, mock_file, mock_env_api_key, mock_mistral_cls
    ):
        """Test language option drops timestamp granularity per API constraint."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_usage = MagicMock()
        mock_usage.prompt_audio_seconds = 1.0
        mock_response.usage = mock_usage
        mock_response.segments = None
        mock_response.words = None
        mock_response.text = "Hello"
        mock_client.audio.transcriptions.complete.return_value = mock_response
        mock_mistral_cls.return_value = mock_client

        transcriber = MistralVoxtralTranscriber()
        await transcriber.transcribe("test.mp3", options={"language": "en"})

        call_kwargs = mock_client.audio.transcriptions.complete.call_args[1]
        assert call_kwargs["language"] == "en"
        assert "timestamp_granularities" not in call_kwargs

    @patch("transcribers.mistral_voxtral.open", new_callable=mock_open, read_data=b"audio_bytes")
    async def test_transcribe_fallback_text(self, mock_file, mock_env_api_key, mock_mistral_cls):
        """Test fallback to plain transcript text."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.duration = 3.0
        mock_response.segments = None
        mock_response.words = None
        mock_response.text = "Plain transcript"
        mock_client.audio.transcriptions.complete.return_value = mock_response
        mock_mistral_cls.return_value = mock_client

        transcriber = MistralVoxtralTranscriber()
        result = await transcriber.transcribe("test.mp3")

        assert len(result.conversation) == 1
        assert result.conversation[0].timestamp == "00:00:00"
        assert result.conversation[0].person == "Unknown"
        assert result.conversation[0].content == "Plain transcript"

    async def test_transcribe_api_error(self, mock_env_api_key, mock_mistral_cls):
        """Test API error propagation."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.complete.side_effect = Exception(
            "API Error")
        mock_mistral_cls.return_value = mock_client

        @patch("transcribers.mistral_voxtral.open", new_callable=mock_open, read_data=b"audio_bytes")
        async def test_transcribe_success_words(self, mock_file, mock_env_api_key, mock_mistral_cls):
            """Test successful transcription with words fallback when segments unavailable."""
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_usage = MagicMock()
            mock_usage.prompt_audio_seconds = 8.0
            mock_response.usage = mock_usage
            mock_response.segments = None
            mock_response.words = [
                MagicMock(start=0.5, end=1.5, text="Hello", speaker=0),
                MagicMock(start=2.0, end=3.0, text="World", speaker=1),
                MagicMock(start=3.5, end=4.5, text="Test", speaker=0),
            ]
            mock_response.text = None
            mock_client.audio.transcriptions.complete.return_value = mock_response
            mock_mistral_cls.return_value = mock_client

            transcriber = MistralVoxtralTranscriber()
            result = await transcriber.transcribe("test.mp3")

            assert isinstance(result, TranscriptResult)
            assert result.name == "Voxtral"
            assert result.duration == 8.0
            assert len(result.conversation) == 3

            first = result.conversation[0]
            assert first.timestamp == "00:00:00"
            assert first.person == "Speaker 0"
            assert first.content == "Hello"

            second = result.conversation[1]
            assert second.timestamp == "00:00:02"
            assert second.person == "Speaker 1"
            assert second.content == "World"

            third = result.conversation[2]
            assert third.timestamp == "00:00:03"
            assert third.person == "Speaker 0"
            assert third.content == "Test"

            call_kwargs = mock_client.audio.transcriptions.complete.call_args[1]
            assert call_kwargs["model"] == "voxtral-mini-latest"
            assert call_kwargs["diarize"] is True
            assert call_kwargs["timestamp_granularities"] == ["segment"]
