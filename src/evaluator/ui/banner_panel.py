"""
Banner panel component for displaying evaluation header information.
"""
import argparse
import os
from pyfiglet import figlet_format
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class BannerPanel:
    """Rich-only panel for displaying the evaluation banner."""

    def __init__(self, args: argparse.Namespace) -> None:
        """
        Initialize the BannerPanel.

        Args:
            args: Command-line arguments containing config_file and flags.
        """
        self.args = args

    def build(self) -> Panel:
        """Build the banner panel renderable."""
        art = figlet_format("Transcription\n    Evals", font="standard")
        title_text = Text(art, style="bold blue")
        title_text.append(
            "  Audio Model Transcription Evaluations\n", style="bold magenta")

        config_abs = os.path.abspath(self.args.config_file)
        lazy_status = (
            "✅ [bold green]Enabled[/bold green]"
            if self.args.lazy_transcription
            else "[bold yellow]Disabled[/bold yellow]"
        )

        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="bold magenta")
        info_table.add_column(style="blue")
        info_table.add_row("Config file", config_abs)
        info_table.add_row("Lazy transcription", lazy_status)

        content = Group(title_text, info_table)
        return Panel(
            content,
            border_style="magenta",
            title="[bold hot_pink]Transcription Evals[/bold hot_pink]",
        )
