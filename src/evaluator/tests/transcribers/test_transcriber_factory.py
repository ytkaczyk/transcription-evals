# file: snyk-ignore python/HardcodedNonCryptoSecret/test
"""
Unit tests for TranscriberFactory.
"""
from typing import Dict, Any, Optional
import pytest
from transcribers.transcriber_factory import TranscriberFactory
from transcribers.abstract_transcriber import AbstractTranscriber
from transcribers.types import TranscriptResult


class MockTranscriber(AbstractTranscriber):
    """
    Mock transcriber for testing factory registration.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "Mock Transcriber"

    def transcribe_sync(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        # pylint: disable=unused-argument
        return TranscriptResult(name=self.name, conversation=[])


class TestTranscriberFactory:
    """
    Test suite for TranscriberFactory.
    """

    def test_register_and_get_transcriber(self):
        """
        Test that we can register a transcriber class and retrieve an instance of it.
        """
        factory_key = "MockTest"
        TranscriberFactory.register(factory_key, MockTranscriber)

        # Retrieve the instance
        instance = TranscriberFactory.get_transcriber(factory_key)
        assert isinstance(instance, MockTranscriber)
        assert instance.name == "Mock Transcriber"

    def test_get_transcriber_with_args(self):
        """
        Test that we can pass arguments to the transcriber constructor.
        """
        factory_key = "MockTestWithArgs"
        TranscriberFactory.register(factory_key, MockTranscriber)

        secret_key = "super_secret"
        instance = TranscriberFactory.get_transcriber(
            factory_key, api_key=secret_key)
        assert isinstance(instance, MockTranscriber)
        assert instance.api_key == secret_key

    def test_get_unregistered_transcriber(self):
        """
        Test that requesting an unregistered transcriber raises ValueError.
        """
        with pytest.raises(ValueError) as excinfo:
            TranscriberFactory.get_transcriber("NonExistentTranscriber")

        assert "is not registered" in str(excinfo.value)

    def test_list_transcribers(self):
        """
        Test that listing transcribers returns registered keys.
        """
        factory_key = "MockListTest"
        TranscriberFactory.register(factory_key, MockTranscriber)

        names = TranscriberFactory.list_transcribers()
        assert factory_key in names
        # Check that standard ones are also there (since they are registered on import in __init__)
        assert "Deepgram" in names
        assert "AssemblyAI" in names
