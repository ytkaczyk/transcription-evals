"""
Custom widget for displaying transcription progress panel.
"""
import logging
from typing import Optional
from textual.widgets import Static, ProgressBar
from textual.containers import Container, Grid

from ui.messages import TranscriptionProgressUpdate

logger = logging.getLogger(__name__)


class TranscriptionProgressPanel(Container):
    """
    Widget that displays real-time progress for transcription of audio files
    across multiple models.

    Displays one progress bar per model+label combination, showing the current
    filename being processed and the completion status.
    """

    BORDER_TITLE = "[bold ansi_magenta]Progress[/bold ansi_magenta]"

    DEFAULT_CSS = """
    TranscriptionProgressPanel {
        border: solid ansi_blue;
        border-title-align: center;
        margin:1 0;
    }
    TranscriptionProgressPanel Grid {
        grid-size: 3;
        grid-columns: auto auto 1fr;
        grid-rows: 1;
        padding: 0 1;
    }
    TranscriptionProgressPanel .model-label {
        content-align: left middle;
        color: ansi_magenta;
        padding-right: 2;
    }
    TranscriptionProgressPanel ProgressBar {
        width: 100%;
    }
    TranscriptionProgressPanel .status-label {
        content-align: left middle;
        padding-left: 2;
        color: ansi_magenta;
    }
    """

    def __init__(self, inputs: list, models: list, **kwargs) -> None:
        """
        Initialize the TranscriptionProgressPanel widget.

        Args:
            inputs: List of input items from the config (each with 'audio' key).
            models: List of model configs (each with 'name' and optional 'label' keys).
            **kwargs: Additional arguments passed to Container widget.
        """
        super().__init__(**kwargs)
        self.inputs = inputs
        self.models = models

        # Calculate total steps to track progress (2 steps per input: transcribe + process)
        self.total_inputs = len(inputs) * 2

        # Set the panel height based on the number of models
        self.styles.height = len(models) + 2

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
                "progressbar_widget": None,  # Will be set in compose()
                "status_widget": None,  # Will be set in compose()
            }

    def _make_key(self, model_name: str, model_label: Optional[str]) -> str:
        """Create a unique key for a model+label combination."""
        if model_label:
            return f"{model_name} ({model_label})"
        return model_name

    def compose(self):
        """Compose the widget with progress bars for each model."""
        # Collect all widgets first
        widgets = []

        for key, state in self._progress_state.items():
            # Create widgets for this model
            model_label_widget = Static(
                # f"[bold ansi_magenta]{key}[/bold ansi_magenta]",
                key,
                classes="model-label"
            )
            progress_bar = ProgressBar(
                total=self.total_inputs,
                show_percentage=True,
                show_eta=False,
            )
            status_widget = Static("Pending", classes="status-label")

            # Store widget references for updates
            state["progressbar_widget"] = progress_bar
            state["status_widget"] = status_widget

            # Add to widgets list
            widgets.extend([model_label_widget, progress_bar, status_widget])

        # Create grid with all widgets
        yield Grid(*widgets)

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

        state = self._progress_state[key]

        # Update progress bar if step is completed
        if message.completed:
            progress_bar = state["progressbar_widget"]
            if progress_bar:
                progress_bar.advance(1)

        # Update status text with blue formatting for status
        status_widget = state["status_widget"]
        if status_widget:
            status_text = f"[ansi_blue]{message.status}[/ansi_blue]"
            if message.audio_filename:
                status_text += f"[white] {message.audio_filename}[/white]"
            status_widget.update(status_text)
