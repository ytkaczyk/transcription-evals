"""
Footer log panel component for real-time log output.
"""
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import RichLog


class FooterLogPanel(Container):
    """Docked footer panel that hosts the RichLog widget."""

    DEFAULT_CSS = """
    FooterLogPanel {
        dock: bottom;
        height: 7;
        border-top: solid ansi_blue;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the footer with a RichLog widget."""
        yield RichLog(id="log-panel", auto_scroll=True, markup=True)
