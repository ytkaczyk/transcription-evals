"""
Message classes for the transcription evaluator UI.
"""
from textual.message import Message


class TranscriptionProgressUpdate(Message):
    """Message posted when transcription progress changes for a model."""

    def __init__(
        self,
        model_name: str,
        model_label: str | None,
        status: str,
        audio_filename: str,
        completed: bool = False,
    ) -> None:
        """
        Initialize a progress update message.

        Args:
            model_name: Name of the model being evaluated.
            model_label: Optional label for the model (used in output filenames).
            status: Current status (e.g., "Transcribing" or "Processing").
            audio_filename: Name of the audio file currently being processed.
            completed: Whether this update completes the current step (increments progress).
        """
        super().__init__()
        self.model_name = model_name
        self.model_label = model_label
        self.status = status
        self.audio_filename = audio_filename
        self.completed = completed
