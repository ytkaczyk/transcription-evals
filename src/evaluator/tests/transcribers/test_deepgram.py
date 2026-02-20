# file: snyk-ignore python/HardcodedNonCryptoSecret/test
"""
Unit tests for DeepgramTranscriber.
"""
# pylint: disable=unused-argument
from unittest.mock import patch, MagicMock, mock_open
import pytest

from transcribers.deepgram import DeepgramTranscriber
from transcribers.types import TranscriptResult

# A dummy class to replace the imported ListenV1Response for isinstance checks


class DummyListenV1Response:
    """Dummy class for type checking."""
    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.metadata = MagicMock()
        self.results = MagicMock()


class TestDeepgramTranscriber:
    """
    Test suite for DeepgramTranscriber.
    """

    @pytest.fixture
    def mock_env_api_key(self, monkeypatch):
        """Sets the DEEPGRAM_API_KEY environment variable."""
        monkeypatch.setenv("DEEPGRAM_API_KEY", "test_env_key")

    @pytest.fixture
    def mock_deepgram_client_cls(self):
        """Mocks the DeepgramClient class."""
        with patch("transcribers.deepgram.DeepgramClient") as mock:
            yield mock

    @pytest.fixture
    def mock_listen_v1_response_cls(self):
        """Mocks the ListenV1Response class import in the module."""
        # Use new=DummyListenV1Response so isinstance checks pass (it needs a real class)
        with patch("transcribers.deepgram.ListenV1Response", new=DummyListenV1Response):
            yield

    def test_init_raises_error_no_key(self, monkeypatch):
        """Test initialization fails without API key."""
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Deepgram API key is required"):
            DeepgramTranscriber(api_key=None)

    def test_init_with_env_key(self, mock_env_api_key, mock_deepgram_client_cls):
        """Test initialization with environment variable."""
        # pylint: disable=unused-argument
        transcriber = DeepgramTranscriber()
        assert transcriber.api_key == "test_env_key"
        mock_deepgram_client_cls.assert_called_once_with(
            api_key="test_env_key")

    def test_init_with_explicit_key(self, mock_deepgram_client_cls):
        """Test initialization with explicit API key."""
        transcriber = DeepgramTranscriber(api_key="explicit_key")
        assert transcriber.api_key == "explicit_key"
        mock_deepgram_client_cls.assert_called_once_with(
            api_key="explicit_key")

    def test_name_property(self, mock_env_api_key, mock_deepgram_client_cls):
        """Test the name property."""
        transcriber = DeepgramTranscriber()
        assert transcriber.name == "Deepgram"

    @patch("transcribers.deepgram.open", new_callable=mock_open, read_data=b"audio_bytes")
    async def test_transcribe_success_utterances(self, mock_file, mock_env_api_key, mock_deepgram_client_cls):
        """Test successful transcription with utterance results."""
        # Setup
        transcriber = DeepgramTranscriber()

        # Mock response object (nova-3)
        mock_response = MagicMock()
        mock_response.metadata.duration = 10.5

        # Create utterance mocks
        u1 = MagicMock(start=1.0, speaker=0, transcript="Hello")
        u2 = MagicMock(start=5.5, speaker=1, transcript="World")

        # Setup results structure
        mock_response.results.utterances = [u1, u2]
        mock_response.results.channels = None

        with patch("transcribers.deepgram.ListenV1Response", new=DummyListenV1Response):
            real_mock_response = DummyListenV1Response()
            real_mock_response.metadata = mock_response.metadata
            real_mock_response.results = mock_response.results
            transcriber.client.listen.v1.media.transcribe_file = MagicMock(
                return_value=real_mock_response
            )

            result = await transcriber.transcribe("test.mp3")

        # Verify
        assert isinstance(result, TranscriptResult)
        assert result.name == "Deepgram"
        assert result.duration == 10.5
        assert len(result.conversation) == 2

        item1 = result.conversation[0]
        assert item1.timestamp == "00:00:01"
        assert item1.person == "Speaker 0"
        assert item1.content == "Hello"

        item2 = result.conversation[1]
        assert item2.timestamp == "00:00:05"
        assert item2.person == "Speaker 1"
        assert item2.content == "World"

        # Verify call arguments
        transcriber.client.listen.v1.media.transcribe_file.assert_called_once()
        call_kwargs = transcriber.client.listen.v1.media.transcribe_file.call_args[1]
        assert call_kwargs['request'] == b"audio_bytes"
        assert call_kwargs['model'] == "nova-3"
        assert call_kwargs['smart_format'] is True
        assert call_kwargs['diarize'] is True

    @patch("transcribers.deepgram.open", new_callable=mock_open, read_data=b"audio_bytes")
    async def test_transcribe_success_channels(self, mock_file, mock_env_api_key, mock_deepgram_client_cls):
        """Test successful transcription fallback to channels."""
        transcriber = DeepgramTranscriber()

        mock_response = MagicMock()
        mock_response.metadata.duration = 5.0
        mock_response.results.utterances = None

        # Channel setup
        word = MagicMock(start=2.0)
        alt = MagicMock(transcript="Fallback text", words=[word])
        channel = MagicMock(alternatives=[alt])
        mock_response.results.channels = [channel]

        with patch("transcribers.deepgram.ListenV1Response", new=DummyListenV1Response):
            real_mock_response = DummyListenV1Response()
            real_mock_response.metadata = mock_response.metadata
            real_mock_response.results = mock_response.results
            transcriber.client.listen.v1.media.transcribe_file = MagicMock(
                return_value=real_mock_response
            )

            result = await transcriber.transcribe("test.mp3")

        assert len(result.conversation) == 1
        assert result.conversation[0].content == "Fallback text"
        assert result.conversation[0].timestamp == "00:00:02"
        assert result.conversation[0].person == "Unknown"

    @patch("transcribers.deepgram.open", new_callable=mock_open, read_data=b"")
    async def test_transcribe_handles_none_values(self, mock_file, mock_env_api_key, mock_deepgram_client_cls):
        """Test logic robust against None values in external API response."""
        transcriber = DeepgramTranscriber()

        mock_response = MagicMock()
        mock_response.metadata.duration = None  # Check usage of `or 0.0`

        # Check usage of `or 0.0` and `or ""`
        u1 = MagicMock(start=None, speaker=None, transcript=None)
        mock_response.results.utterances = [u1]
        mock_response.results.channels = None

        with patch("transcribers.deepgram.ListenV1Response", new=DummyListenV1Response):
            real_mock_response = DummyListenV1Response()
            real_mock_response.metadata = mock_response.metadata
            real_mock_response.results = mock_response.results
            transcriber.client.listen.v1.media.transcribe_file = MagicMock(
                return_value=real_mock_response
            )

            result = await transcriber.transcribe("test.mp3")

        assert result.duration == 0.0
        assert len(result.conversation) == 1
        assert result.conversation[0].timestamp == "00:00:00"
        assert result.conversation[0].person == "Unknown"
        assert result.conversation[0].content == ""

    @patch("transcribers.deepgram.open", new_callable=mock_open, read_data=b"")
    async def test_transcribe_unexpected_response_type(self, mock_file, mock_env_api_key, mock_deepgram_client_cls, caplog):
        """Test handling of unexpected response type from SDK."""
        transcriber = DeepgramTranscriber()

        # Return something that is NOT an instance of ListenV1Response
        mock_response = MagicMock()

        # Use DummyListenV1Response to mock the class in the module
        with patch("transcribers.deepgram.ListenV1Response", new=DummyListenV1Response):
            # mock_response is a MagicMock, not instance of DummyListenV1Response
            transcriber.client.listen.v1.media.transcribe_file = MagicMock(
                return_value=mock_response
            )
            result = await transcriber.transcribe("test.mp3")

        assert len(result.conversation) == 0
        assert "Deepgram returned unexpected response type" in caplog.text

    @patch("transcribers.deepgram.open")
    async def test_transcribe_file_error(self, mock_open_func, mock_env_api_key, mock_deepgram_client_cls):
        """Test file reading error propagation."""
        mock_open_func.side_effect = IOError("File not found")
        transcriber = DeepgramTranscriber()

        with pytest.raises(IOError):
            await transcriber.transcribe("nonexistent.mp3")

    async def test_transcribe_api_error(self, mock_env_api_key, mock_deepgram_client_cls):
        """Test API error propagation."""
        with patch("transcribers.deepgram.open", new_callable=mock_open, read_data=b"data"):
            transcriber = DeepgramTranscriber()
            transcriber.client.listen.v1.media.transcribe_file = MagicMock(
                side_effect=Exception("API Error")
            )

            with pytest.raises(Exception, match="API Error"):
                await transcriber.transcribe("test.mp3")

    @patch("transcribers.deepgram.open", new_callable=mock_open, read_data=b"audio_bytes")
    async def test_transcribe_with_options(self, mock_file, mock_env_api_key, mock_deepgram_client_cls):
        """Test transcribe with custom options."""
        transcriber = DeepgramTranscriber()

        mock_response = MagicMock()
        mock_response.metadata.duration = 10.0
        mock_response.results.utterances = []
        mock_response.results.channels = []

        with patch("transcribers.deepgram.ListenV1Response", new=DummyListenV1Response):
            real_mock_response = DummyListenV1Response()
            real_mock_response.metadata = mock_response.metadata
            real_mock_response.results = mock_response.results
            transcriber.client.listen.v1.media.transcribe_file = MagicMock(
                return_value=real_mock_response
            )

            custom_options = {"model": "nova-2", "language": "es"}
            await transcriber.transcribe("test.mp3", options=custom_options)

        # Verify call arguments
        transcriber.client.listen.v1.media.transcribe_file.assert_called_once()
        call_kwargs = transcriber.client.listen.v1.media.transcribe_file.call_args[1]
        assert call_kwargs['model'] == "nova-2"
        assert call_kwargs['language'] == "es"
        # Default should remain if not overridden
        assert call_kwargs['smart_format'] is True
