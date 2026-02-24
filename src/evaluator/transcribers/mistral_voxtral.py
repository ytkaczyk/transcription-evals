"""
Mistral Voxtral transcriber implementation.
"""
import os
import logging
from typing import List, Optional, Dict, Any, Iterable

from mistralai import Mistral

from .abstract_transcriber import AbstractTranscriber
from .types import TranscriptResult, ConversationItem

logger = logging.getLogger(__name__)


class MistralVoxtralTranscriber(AbstractTranscriber):
    """
    Transcriber implementation using the Mistral Voxtral transcription service.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Mistral API key is required. Set MISTRAL_API_KEY environment variable "
                "or pass it to the constructor."
            )

        self.client = Mistral(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "Voxtral"

    def _format_timestamp(self, start_time: float) -> str:
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        seconds = int(start_time % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _extract_duration(self, response: Any) -> float:
        usage = self._get_attr(response, "usage", None)
        if usage is not None:
            prompt_audio_seconds = self._get_attr(
                usage, "prompt_audio_seconds", None)
            if prompt_audio_seconds is not None:
                try:
                    return float(prompt_audio_seconds)
                except (TypeError, ValueError):
                    logger.warning("Unexpected duration type: %s",
                                   type(prompt_audio_seconds))
        return 0.0

    def _process_segments(self, segments: Iterable[Any]) -> List[ConversationItem]:
        items: List[ConversationItem] = []
        for segment in segments:
            start_time = self._get_attr(segment, "start", 0.0) or 0.0
            text = self._get_attr(segment, "text", "") or ""
            speaker = self._get_attr(segment, "speaker", None)
            if speaker is None:
                speaker = self._get_attr(segment, "speaker_id", None)
            person = f"Speaker {speaker}" if speaker is not None else "Unknown"

            items.append(ConversationItem(
                timestamp=self._format_timestamp(float(start_time)),
                person=person,
                content=text
            ))
        return items

    def _process_words(self, words: Iterable[Any]) -> List[ConversationItem]:
        words_list = list(words)
        if not words_list:
            return []

        start_time = self._get_attr(words_list[0], "start", 0.0) or 0.0
        word_values = []
        for word in words_list:
            token = self._get_attr(word, "word", None)
            if token is None:
                token = self._get_attr(word, "text", "")
            word_values.append(token or "")

        text = " ".join(value for value in word_values if value).strip()

        return [ConversationItem(
            timestamp=self._format_timestamp(float(start_time)),
            person="Unknown",
            content=text
        )]

    @staticmethod
    def _extract_raw_output(response: Any) -> Optional[Dict[str, Any]]:
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        if hasattr(response, "dict"):
            return response.dict()
        return None

    def transcribe_sync(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        """Synchronous transcription. Called directly from worker threads or via the base-class async wrapper."""
        try:
            with open(audio_file_path, "rb") as file:
                default_options: Dict[str, Any] = {
                    "model": "voxtral-mini-latest",
                    "diarize": True,
                    "timestamp_granularities": ["segment"],
                }

                if options:
                    default_options.update(options)

                if "language" in default_options and "timestamp_granularities" in default_options:
                    logger.warning(
                        "Voxtral does not support both 'language' and 'timestamp_granularities'; "
                        "dropping 'timestamp_granularities'."
                    )
                    default_options.pop("timestamp_granularities", None)

                response = self.client.audio.transcriptions.complete(
                    file={
                        "content": file,
                        "file_name": os.path.basename(audio_file_path),
                    },
                    **default_options
                )

            raw_output = self._extract_raw_output(response)

            conversation_items: List[ConversationItem] = []
            duration = self._extract_duration(response)

            segments = self._get_attr(response, "segments", None)
            words = self._get_attr(response, "words", None)
            text = self._get_attr(response, "text", None)
            if text is None:
                text = self._get_attr(response, "transcript", None)

            if segments:
                conversation_items = self._process_segments(segments)
            elif words:
                conversation_items = self._process_words(words)
            elif text:
                conversation_items = [ConversationItem(
                    timestamp="00:00:00",
                    person="Unknown",
                    content=text
                )]

            # pylint: disable=duplicate-code
            return TranscriptResult(
                name=self.name,
                conversation=conversation_items,
                duration=duration,
                raw_output=raw_output
            )

        except Exception as e:
            logger.error("Voxtral transcription failed: %s", e)
            raise
