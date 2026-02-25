# file: snyk-ignore python/HardcodedNonCryptoSecret/test
"""
Unit tests for AWSTranscribeTranscriber.
"""
import json
from unittest.mock import patch, MagicMock
import pytest

from transcribers.aws_transcribe import AWSTranscribeTranscriber
from transcribers.types import TranscriptResult
from transcribers.transcriber_factory import TranscriberFactory

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VALID_INIT_ENV = {
    "AWS_ACCESS_KEY_ID": "test_key_id",
    "AWS_SECRET_ACCESS_KEY": "test_secret",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_S3_BUCKET": "test-bucket",
}

# Minimal AWS Transcribe output with two speakers
SAMPLE_TRANSCRIPT_JSON = {
    "results": {
        "transcripts": [{"transcript": "Hello there World"}],
        "items": [
            {
                "type": "pronunciation",
                "start_time": "1.0",
                "end_time": "1.4",
                "alternatives": [{"content": "Hello", "confidence": "0.99"}],
            },
            {
                "type": "pronunciation",
                "start_time": "1.5",
                "end_time": "1.8",
                "alternatives": [{"content": "there", "confidence": "0.98"}],
            },
            {
                "type": "punctuation",
                "alternatives": [{"content": ","}],
            },
            {
                "type": "pronunciation",
                "start_time": "5.0",
                "end_time": "5.6",
                "alternatives": [{"content": "World", "confidence": "0.97"}],
            },
        ],
        "speaker_labels": {
            "speakers": 2,
            "segments": [
                {
                    "speaker_label": "spk_0",
                    "start_time": "1.0",
                    "end_time": "1.8",
                    "items": [
                        {"start_time": "1.0", "end_time": "1.4"},
                        {"start_time": "1.5", "end_time": "1.8"},
                    ],
                },
                {
                    "speaker_label": "spk_1",
                    "start_time": "5.0",
                    "end_time": "5.6",
                    "items": [
                        {"start_time": "5.0", "end_time": "5.6"},
                    ],
                },
            ],
        },
    }
}


def _make_urlopen_mock(transcript_json: dict) -> MagicMock:
    """Return a mock that can be used as 'with urllib.request.urlopen(...) as r'."""
    raw = json.dumps(transcript_json).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = raw
    cm.__exit__.return_value = False
    return cm


def _make_boto3_clients() -> tuple:
    """Return (mock_s3_client, mock_transcribe_client, mock_boto3_client_fn)."""
    mock_s3 = MagicMock()
    mock_transcribe = MagicMock()

    def _client_factory(service, **kwargs):
        if service == "s3":
            return mock_s3
        if service == "transcribe":
            return mock_transcribe
        raise ValueError(f"Unexpected service: {service}")

    mock_boto3 = MagicMock(side_effect=_client_factory)
    return mock_s3, mock_transcribe, mock_boto3


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestAWSTranscribeTranscriber:
    """Test suite for AWSTranscribeTranscriber."""

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set all required AWS environment variables."""
        for key, value in VALID_INIT_ENV.items():
            monkeypatch.setenv(key, value)

    @pytest.fixture
    def mock_boto3(self):
        """Patch boto3.client used inside aws_transcribe module."""
        mock_s3, mock_transcribe, mock_boto3_fn = _make_boto3_clients()
        with patch("transcribers.aws_transcribe.boto3.client", side_effect=mock_boto3_fn):
            yield mock_s3, mock_transcribe

    # ------------------------------------------------------------------
    # Initialization tests
    # ------------------------------------------------------------------

    def test_init_raises_without_access_key_id(self, monkeypatch):
        """Missing AWS_ACCESS_KEY_ID raises ValueError."""
        for key, value in VALID_INIT_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID")
        with pytest.raises(ValueError, match="AWS access key ID is required"):
            AWSTranscribeTranscriber()

    def test_init_raises_without_secret_access_key(self, monkeypatch):
        """Missing AWS_SECRET_ACCESS_KEY raises ValueError."""
        for key, value in VALID_INIT_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY")
        with pytest.raises(ValueError, match="AWS secret access key is required"):
            AWSTranscribeTranscriber()

    def test_init_raises_without_region(self, monkeypatch):
        """Missing AWS_DEFAULT_REGION raises ValueError."""
        for key, value in VALID_INIT_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("AWS_DEFAULT_REGION")
        with pytest.raises(ValueError, match="AWS region is required"):
            AWSTranscribeTranscriber()

    def test_init_raises_without_s3_bucket(self, monkeypatch):
        """Missing AWS_S3_BUCKET raises ValueError."""
        for key, value in VALID_INIT_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("AWS_S3_BUCKET")
        with pytest.raises(ValueError, match="AWS S3 bucket is required"):
            AWSTranscribeTranscriber()

    def test_init_with_env_vars(self, mock_env, mock_boto3):
        """Transcriber initializes correctly from environment variables."""
        transcriber = AWSTranscribeTranscriber()
        assert transcriber.aws_access_key_id == "test_key_id"
        assert transcriber.aws_secret_access_key == "test_secret"
        assert transcriber.aws_region == "us-east-1"
        assert transcriber.s3_bucket == "test-bucket"

    def test_init_with_explicit_params(self, mock_boto3):
        """Transcriber initializes correctly from explicit constructor arguments."""
        transcriber = AWSTranscribeTranscriber(
            aws_access_key_id="key",
            aws_secret_access_key="secret",
            aws_region="eu-west-1",
            s3_bucket="my-bucket",
        )
        assert transcriber.aws_access_key_id == "key"
        assert transcriber.aws_region == "eu-west-1"
        assert transcriber.s3_bucket == "my-bucket"

    # ------------------------------------------------------------------
    # name property
    # ------------------------------------------------------------------

    def test_name_property(self, mock_env, mock_boto3):
        """name returns 'AWS Transcribe'."""
        transcriber = AWSTranscribeTranscriber()
        assert transcriber.name == "AWS Transcribe"

    # ------------------------------------------------------------------
    # _format_timestamp
    # ------------------------------------------------------------------

    def test_format_timestamp_zero(self, mock_env, mock_boto3):
        """0.0 seconds formats to 00:00:00."""
        # pylint: disable=protected-access
        t = AWSTranscribeTranscriber()
        assert t._format_timestamp(0.0) == "00:00:00"

    def test_format_timestamp_complex(self, mock_env, mock_boto3):
        """3661 seconds (1h 1m 1s) formats to 01:01:01."""
        # pylint: disable=protected-access
        t = AWSTranscribeTranscriber()
        assert t._format_timestamp(3661.0) == "01:01:01"

    # ------------------------------------------------------------------
    # Successful transcription
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    @patch("transcribers.aws_transcribe.urllib.request.urlopen")
    async def test_transcribe_success_with_speakers(
        self, mock_urlopen, mock_uuid, mock_env, mock_boto3
    ):
        """Full transcription pipeline: upload → start → poll → download → cleanup."""
        mock_s3, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "abc123"

        # Waiter mock (get_transcription_job used for polling)
        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "https://s3.amazonaws.com/output.json"},
            }
        }

        mock_urlopen.return_value = _make_urlopen_mock(SAMPLE_TRANSCRIPT_JSON)

        transcriber = AWSTranscribeTranscriber()
        result = await transcriber.transcribe("audio.mp3")

        # Result shape
        assert isinstance(result, TranscriptResult)
        assert result.name == "AWS Transcribe"
        assert len(result.conversation) == 2

        # First speaker group (spk_0): "Hello there,"
        item0 = result.conversation[0]
        assert item0.timestamp == "00:00:01"
        assert item0.person == "Speaker 0"
        assert "Hello" in item0.content
        assert "there," in item0.content   # punctuation attached to last word

        # Second speaker group (spk_1): "World"
        item1 = result.conversation[1]
        assert item1.timestamp == "00:00:05"
        assert item1.person == "Speaker 1"
        assert item1.content == "World"

        # raw_output is set
        assert result.raw_output == SAMPLE_TRANSCRIPT_JSON

        # S3 upload called with correct args
        mock_s3.upload_file.assert_called_once_with(
            "audio.mp3",
            "test-bucket",
            "transcription-evals/transcription-eval-abc123/audio.mp3",
        )

        # Transcribe job started with IdentifyLanguage (no language override)
        start_call_kwargs = mock_transcribe.start_transcription_job.call_args[1]
        assert start_call_kwargs["TranscriptionJobName"] == "transcription-eval-abc123"
        assert start_call_kwargs["IdentifyLanguage"] is True
        assert start_call_kwargs["Settings"]["ShowSpeakerLabels"] is True
        assert start_call_kwargs["Settings"]["MaxSpeakerLabels"] == 10

        # Cleanup: S3 delete and job delete both called
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="transcription-evals/transcription-eval-abc123/audio.mp3",
        )
        mock_transcribe.delete_transcription_job.assert_called_once_with(
            TranscriptionJobName="transcription-eval-abc123"
        )

    # ------------------------------------------------------------------
    # Language code override
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    @patch("transcribers.aws_transcribe.urllib.request.urlopen")
    async def test_transcribe_with_language_code(
        self, mock_urlopen, mock_uuid, mock_env, mock_boto3
    ):
        """Passing language_code in options sends LanguageCode instead of IdentifyLanguage."""
        _, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "def456"

        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "https://s3.amazonaws.com/out.json"},
            }
        }
        mock_urlopen.return_value = _make_urlopen_mock(SAMPLE_TRANSCRIPT_JSON)

        transcriber = AWSTranscribeTranscriber()
        await transcriber.transcribe("audio.mp3", options={"language_code": "en-US"})

        start_kwargs = mock_transcribe.start_transcription_job.call_args[1]
        assert start_kwargs["LanguageCode"] == "en-US"
        assert "IdentifyLanguage" not in start_kwargs

    # ------------------------------------------------------------------
    # No speaker labels fallback
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    @patch("transcribers.aws_transcribe.urllib.request.urlopen")
    async def test_transcribe_no_speaker_labels(
        self, mock_urlopen, mock_uuid, mock_env, mock_boto3
    ):
        """When speaker_labels are absent, all words grouped as 'Unknown'."""
        _, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "ghi789"

        transcript_no_speakers = {
            "results": {
                "transcripts": [{"transcript": "Hello World"}],
                "items": [
                    {
                        "type": "pronunciation",
                        "start_time": "0.0",
                        "end_time": "0.5",
                        "alternatives": [{"content": "Hello"}],
                    },
                    {
                        "type": "pronunciation",
                        "start_time": "0.6",
                        "end_time": "1.0",
                        "alternatives": [{"content": "World"}],
                    },
                ],
            }
        }

        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "https://s3.amazonaws.com/out.json"},
            }
        }
        mock_urlopen.return_value = _make_urlopen_mock(transcript_no_speakers)

        transcriber = AWSTranscribeTranscriber()
        result = await transcriber.transcribe("audio.mp3")

        assert len(result.conversation) == 1
        assert result.conversation[0].person == "Unknown"
        assert result.conversation[0].timestamp == "00:00:00"
        assert "Hello" in result.conversation[0].content
        assert "World" in result.conversation[0].content

    # ------------------------------------------------------------------
    # Empty items fallback
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    @patch("transcribers.aws_transcribe.urllib.request.urlopen")
    async def test_transcribe_empty_items_falls_back_to_plain_text(
        self, mock_urlopen, mock_uuid, mock_env, mock_boto3
    ):
        """When items list is empty, falls back to the plain-text transcript."""
        _, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "jkl000"

        transcript_empty_items = {
            "results": {
                "transcripts": [{"transcript": "This is a fallback text"}],
                "items": [],
            }
        }

        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "https://s3.amazonaws.com/out.json"},
            }
        }
        mock_urlopen.return_value = _make_urlopen_mock(transcript_empty_items)

        transcriber = AWSTranscribeTranscriber()
        result = await transcriber.transcribe("audio.mp3")

        assert len(result.conversation) == 1
        assert result.conversation[0].person == "Unknown"
        assert result.conversation[0].timestamp == "00:00:00"
        assert result.conversation[0].content == "This is a fallback text"

    # ------------------------------------------------------------------
    # Job failure
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    async def test_transcribe_raises_on_job_failure(
        self, mock_uuid, mock_env, mock_boto3
    ):
        """A FAILED job status raises RuntimeError with the failure reason."""
        _, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "fail001"

        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "FAILED",
                "FailureReason": "Unsupported media format.",
            }
        }

        transcriber = AWSTranscribeTranscriber()
        with pytest.raises(RuntimeError, match="Unsupported media format"):
            await transcriber.transcribe("bad_audio.xyz")

    # ------------------------------------------------------------------
    # Cleanup always runs
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    async def test_cleanup_runs_even_on_failure(
        self, mock_uuid, mock_env, mock_boto3
    ):
        """S3 object and Transcribe job are deleted even when parsing raises."""
        mock_s3, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "cln002"

        # Job reports FAILED → RuntimeError raised inside transcribe_sync
        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "FAILED",
                "FailureReason": "Internal error.",
            }
        }

        transcriber = AWSTranscribeTranscriber()
        with pytest.raises(RuntimeError):
            await transcriber.transcribe("audio.mp3")

        # S3 upload was called, so the object should be cleaned up
        mock_s3.delete_object.assert_called_once()
        # Job was started, so it should be cleaned up
        mock_transcribe.delete_transcription_job.assert_called_once()

    # ------------------------------------------------------------------
    # Cleanup handles its own errors gracefully
    # ------------------------------------------------------------------

    @patch("transcribers.aws_transcribe.uuid.uuid4")
    @patch("transcribers.aws_transcribe.urllib.request.urlopen")
    async def test_cleanup_errors_do_not_surface(
        self, mock_urlopen, mock_uuid, mock_env, mock_boto3
    ):
        """Exceptions during cleanup are swallowed; the original result still returns."""
        mock_s3, mock_transcribe = mock_boto3
        mock_uuid.return_value.hex = "clnerr3"

        mock_transcribe.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "https://s3.amazonaws.com/out.json"},
            }
        }
        mock_urlopen.return_value = _make_urlopen_mock(SAMPLE_TRANSCRIPT_JSON)

        # Make cleanup calls fail
        mock_s3.delete_object.side_effect = Exception("S3 delete error")
        mock_transcribe.delete_transcription_job.side_effect = Exception(
            "Job delete error")

        transcriber = AWSTranscribeTranscriber()
        # Should not raise despite cleanup failures
        result = await transcriber.transcribe("audio.mp3")

        assert isinstance(result, TranscriptResult)
        assert result.name == "AWS Transcribe"

    # ------------------------------------------------------------------
    # Factory registration
    # ------------------------------------------------------------------

    def test_registered_in_factory(self, mock_env, mock_boto3):
        """AWSTranscribe is discoverable via the TranscriberFactory."""
        assert "AWSTranscribe" in TranscriberFactory.list_transcribers()
