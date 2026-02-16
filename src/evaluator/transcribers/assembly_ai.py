"""
AssemblyAI transcriber implementation.
"""
import os
import logging
from typing import List, Optional, Dict, Any

import assemblyai as aai

from .abstract_transcriber import AbstractTranscriber
from .types import TranscriptResult, ConversationItem

logger = logging.getLogger(__name__)


class AssemblyAITranscriber(AbstractTranscriber):
    """
    Transcriber implementation using AssemblyAI API.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AssemblyAI transcriber.

        Args:
            api_key (Optional[str]): The AssemblyAI API key. If not provided, it will be read from the environment variable ASSEMBLYAI_API_KEY.
        """
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            # We don't raise error immediately to allow instantiation if key is not needed immediately or mocking?
            # Deepgram implementation raises ValueError if key is missing.
            raise ValueError(
                "AssemblyAI API key is required. Set ASSEMBLYAI_API_KEY environment variable "
                "or pass it to the constructor."
            )

        aai.settings.api_key = self.api_key
        self.transcriber = aai.Transcriber()

    @property
    def name(self) -> str:
        return "AssemblyAI"

    def _format_timestamp(self, start_time_ms: int) -> str:
        """
        Formats milliseconds into HH:MM:SS string.
        """
        seconds_total = start_time_ms / 1000
        hours = int(seconds_total // 3600)
        minutes = int((seconds_total % 3600) // 60)
        seconds = int(seconds_total % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def transcribe(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        try:
            # Configure transcription with V3 model and speaker labels as default
            config_params = {
                "speech_models": ["universal-3-pro"],
                "speaker_labels": True,
            }

            # Merge options from the config file, allowing them to override defaults
            if options:
                config_params.update(options)

            # Set default prompt if not provided in options
            if "prompt" not in config_params:
                config_params["prompt"] = "Transcribe this audio, Transcribe verbatim"

            config = aai.TranscriptionConfig(**config_params)

            # Transcribe the file
            transcript = self.transcriber.transcribe(
                audio_file_path, config=config)

            if transcript.status == aai.TranscriptStatus.error:
                error_msg = f"Transcription failed: {transcript.error}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            conversation_items: List[ConversationItem] = []

            # Process utterances for speaker diarization
            if transcript.utterances:
                for utterance in transcript.utterances:
                    conversation_items.append(ConversationItem(
                        timestamp=self._format_timestamp(utterance.start),
                        person=f"Speaker {utterance.speaker}",
                        content=utterance.text
                    ))

            # If no utterances were found but transcript exists (e.g. short audio or diarization fell back)
            # We can fallback to the main text, but without timestamps per sentence effectively.
            # However, AbstractTranscriber expects TranscriptResult.
            # If transcript.utterances is empty but text is present, we might add one item.
            if not conversation_items and transcript.text:
                conversation_items.append(ConversationItem(
                    timestamp="00:00:00",
                    person="Unknown",
                    content=transcript.text
                ))

            return TranscriptResult(
                name=self.name,
                conversation=conversation_items,
                duration=transcript.audio_duration or 0.0,
                raw_output=transcript.json_response
            )

        except Exception as e:
            logger.error("Error during AssemblyAI transcription: %s", e)
            raise
