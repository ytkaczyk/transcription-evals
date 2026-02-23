"""
Deepgram transcriber implementation.
"""
import os
import logging
from typing import List, Optional, Dict, Any

from deepgram import DeepgramClient
# Using lazy import to avoid circular dependency issues if any,
# although Deepgram types are self-contained
from deepgram.types import ListenV1Response

from .abstract_transcriber import AbstractTranscriber
from .types import TranscriptResult, ConversationItem

logger = logging.getLogger(__name__)


class DeepgramTranscriber(AbstractTranscriber):
    """
    Transcriber implementation using Deepgram API.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Deepgram API key is required. Set DEEPGRAM_API_KEY environment variable "
                "or pass it to the constructor."
            )

        self.client = DeepgramClient(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "Deepgram"

    def _format_timestamp(self, start_time: float) -> str:
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        seconds = int(start_time % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _process_utterances(self, utterances) -> List[ConversationItem]:
        items = []
        for utterance in utterances:
            start_time = utterance.start or 0.0
            speaker = f"Speaker {utterance.speaker}" if utterance.speaker is not None else "Unknown"
            text = utterance.transcript or ""
            timestamp_str = self._format_timestamp(start_time)

            items.append(ConversationItem(
                timestamp=timestamp_str,
                person=speaker,
                content=text
            ))
        return items

    def _process_channels(self, channels) -> List[ConversationItem]:
        items = []
        for channel in channels:
            for alternative in channel.alternatives:
                if alternative.transcript:
                    start_time = 0.0
                    if alternative.words:
                        start_time = alternative.words[0].start or 0.0

                    timestamp_str = self._format_timestamp(start_time)

                    items.append(ConversationItem(
                        timestamp=timestamp_str,
                        person="Unknown",
                        content=alternative.transcript
                    ))
        return items

    def transcribe_sync(self, audio_file_path: str, options: Optional[Dict[str, Any]] = None) -> TranscriptResult:
        """Synchronous transcription. Called directly from worker threads or via the base-class async wrapper."""
        try:
            with open(audio_file_path, "rb") as file:
                buffer_data = file.read()

            default_options = {
                "model": "nova-3",
                "smart_format": True,
                "diarize": True,
                "punctuate": True,
                "utterances": True,
            }

            if options:
                default_options.update(options)

            response = self.client.listen.v1.media.transcribe_file(  # pylint: disable=no-member
                request=buffer_data,
                **default_options
            )

            raw_output = response.model_dump(mode='json') if hasattr(
                response, "model_dump") else None

            conversation_items: List[ConversationItem] = []
            duration = 0.0

            # The SDK types this as Union[ListenV1Response, ListenV1AcceptedResponse]
            # We assume ListenV1Response when no callback is used.
            if isinstance(response, ListenV1Response):
                if response.metadata and response.metadata.duration is not None:
                    duration = response.metadata.duration
                results = response.results
                if results:
                    if results.utterances:
                        conversation_items = self._process_utterances(
                            results.utterances
                        )
                    elif results.channels:
                        conversation_items = self._process_channels(
                            results.channels
                        )
            else:
                logger.warning(
                    "Deepgram returned unexpected response type: %s",
                    type(response)
                )

            return TranscriptResult(
                name=self.name,
                conversation=conversation_items,
                duration=duration,
                raw_output=raw_output
            )

        except Exception as e:
            logger.error("Deepgram transcription failed: %s", e)
            raise
