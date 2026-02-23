"""
Abstract transcriber module.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from .types import TranscriptResult


class AbstractTranscriber(ABC):
    """
    Abstract class that will be used to transcribe audio files. Each model will have its own implementation of this class.

    The transcribe method will take in an audio file and return the transcript as a string. This will allow us to easily compare the outputs of different models.
    The output format `TranscriptResult` will be a dataclass that contains the transcript and any additional information that may be useful for evaluation (e.g. confidence scores, timestamps, etc.).
    This abstract class will serve as a blueprint for all transcriber implementations, ensuring consistency and facilitating evaluation across different models.

    Subclasses must implement `transcribe_sync`, which performs the transcription synchronously.
    The `transcribe` method is provided as a non-abstract async wrapper that offloads `transcribe_sync`
    to a worker thread via `asyncio.to_thread`, keeping the event loop free.
    """

    @abstractmethod
    def transcribe_sync(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        """
        Transcribes the audio file synchronously and returns the result.

        Subclasses must implement this method. It will be called either directly (from a worker thread)
        or via the default `transcribe` async wrapper.

        Args:
            audio_file_path (str): The path to the audio file.
            options (Optional[Dict[str, Any]]): A dictionary of options to configure the transcription.

        Returns:
            TranscriptResult: The result of the transcription including conversation details.
        """

    async def transcribe(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        """
        Async wrapper around `transcribe_sync`. Offloads sync transcription to a worker thread
        so the event loop is not blocked.
        """
        return await asyncio.to_thread(self.transcribe_sync, audio_file_path, options)

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the transcriber.
        """
