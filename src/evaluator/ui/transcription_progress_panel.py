"""
Custom widget for displaying transcription progress panel.
"""
import logging
from typing import Optional
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from textual.widget import Widget
from textual.widgets import Static

from ui.messages import TranscriptionProgressUpdate

logger = logging.getLogger(__name__)


class TranscriptionProgressPanel(Static):
    """
    Widget that displays real-time progress for transcription of audio files
    across multiple models.

    Displays one progress bar per model+label combination, showing the current
    filename being processed and the completion status.
    """

    def __init__(self, inputs: list, models: list, **kwargs) -> None:
        """
        Initialize the TranscriptionProgressPanel widget.

        Args:
            inputs: List of input items from the config (each with 'audio' key).
            models: List of model configs (each with 'name' and optional 'label' keys).
            **kwargs: Additional arguments passed to Static widget.
        """
        super().__init__(**kwargs)
        self.inputs = inputs
        self.models = models

        # Calculate total steps to track progress (2 steps per input: transcribe + process)
        self.total_inputs = len(inputs) * 2

        # Create a key for each model+label combination
        # Key format: "model_name" or "model_name (label)"
        self._progress_state: dict = {}
        for model_config in models:
            model_name = model_config.get("name", "Unknown")
            model_label = model_config.get("label")
            key = self._make_key(model_name, model_label)
            self._progress_state[key] = {
                "model_name": model_name,
                "model_label": model_label,
                "completed": 0,
                "current_file": "",
                "current_status": "Pending",
            }

    def _make_key(self, model_name: str, model_label: Optional[str]) -> str:
        """Create a unique key for a model+label combination."""
        if model_label:
            return f"{model_name} ({model_label})"
        return model_name

    def on_transcription_progress_update(
        self, message: TranscriptionProgressUpdate
    ) -> None:
        """Handle progress update messages from the EvaluationRunner."""
        key = self._make_key(message.model_name, message.model_label)

        if key not in self._progress_state:
            logger.warning(
                "Received progress update for unknown model: %s", key
            )
            return

        # Update state
        self._progress_state[key]["current_file"] = message.audio_filename
        self._progress_state[key]["current_status"] = message.status

        # Increment progress if step is completed
        if message.completed:
            self._progress_state[key]["completed"] += 1

        # Re-render the widget
        self.update(self._build_progress_table())

    def _build_progress_table(self) -> Table:
        """Build a Rich Table displaying all progress bars and status."""
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold magenta", min_width=25)  # Model name
        table.add_column(style="blue", width=30)  # Progress bar
        table.add_column()  # Current file + status

        for key, state in self._progress_state.items():
            model_name = key
            completed = state["completed"]
            total = self.total_inputs
            percent = 0 if total == 0 else (completed / total) * 100

            # Build progress visuals using simple bar
            bar_width = 20
            filled = int((completed / total) * bar_width) if total > 0 else 0
            bar = "█" * filled + "░" * (bar_width - filled)

            # Build the right side: status and filename
            status_text = state["current_status"]
            filename = state["current_file"]
            right_text = f"{status_text} {filename}" if filename else status_text

            # Add row: model | progress bar | status+file
            progress_display = f"[{bar}] {completed}/{total}"
            table.add_row(model_name, progress_display, right_text)

        return table

    def render(self) -> Table:
        """Render the progress table."""
        return self._build_progress_table()
