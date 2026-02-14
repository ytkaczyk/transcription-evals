"""
Type definitions for transcriber results.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ConversationItem:
    """
    Represents a single item in a conversation (utterance).
    """
    timestamp: str  # Timestamp of the utterance, typically "HH:MM:SS"
    person: str     # Identification of the speaker (e.g., "Speaker 1")
    content: str    # The transcribed text content


@dataclass
class TranscriptResult:
    """
    Represents the full result of a transcription job.
    """
    # Name/Identifier of the transcription source (e.g. "sample1")
    name: str
    # List of utterances in the conversation
    conversation: List[ConversationItem]
    # Duration of the processed audio in seconds
    duration: float = 0.0
    # Raw output from the provider (JSON/Dict)
    raw_output: Optional[Dict[str, Any]] = field(default=None, repr=False)
