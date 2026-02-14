"""
This module contains the transcribers for the evaluator.
"""
from .abstract_transcriber import AbstractTranscriber
from .types import TranscriptResult, ConversationItem
from .assembly_ai import AssemblyAITranscriber
from .deepgram import DeepgramTranscriber
from .transcriber_factory import TranscriberFactory

# Register known transcribers
TranscriberFactory.register("Deepgram", DeepgramTranscriber)
TranscriberFactory.register("AssemblyAI", AssemblyAITranscriber)

__all__ = ["AbstractTranscriber", "TranscriptResult",
           "ConversationItem", "AssemblyAITranscriber", "DeepgramTranscriber", "TranscriberFactory"]
