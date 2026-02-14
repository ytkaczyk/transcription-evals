"""
Abstract transcriber module.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from .types import TranscriptResult


class AbstractTranscriber(ABC):
    """
    Abstract class that will be used to transcribe audio files. Each model will have its own implementation of this class.

    The transcribe method will take in an audio file and return the transcript as a string. This will allow us to easily compare the outputs of different models.
    The output format `TranscriptResult` will be a dataclass that contains the transcript and any additional information that may be useful for evaluation (e.g. confidence scores, timestamps, etc.).
    This abstract class will serve as a blueprint for all transcriber implementations, ensuring consistency and facilitating evaluation across different models.
    """

    @abstractmethod
    def transcribe(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        """
        Transcribes the audio file and returns the result in the specified format.

        Args:
            audio_file_path (str): The path to the audio file.
            options (Optional[Dict[str, Any]]): A dictionary of options to configure the transcription.

        Returns:
            TranscriptResult: The result of the transcription including conversation details.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the transcriber.
        """
