"""
Directories panel component for displaying runtime paths.
"""
from rich.panel import Panel
from rich.table import Table
from app_types import RuntimePaths


class DirectoriesPanel:
    """Rich-only panel for displaying input/output directories."""

    def __init__(self, paths: RuntimePaths) -> None:
        """
        Initialize the DirectoriesPanel.

        Args:
            paths: RuntimePaths object containing directory information.
        """
        self.paths = paths

    def build(self) -> Panel:
        """Build the Directories panel with runtime paths."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold magenta", min_width=20)
        table.add_column(style="blue")
        table.add_row("Inputs", self.paths.inputs_dir)
        table.add_row("Eval root", self.paths.eval_dir)
        table.add_row("Intermediate", self.paths.intermediate_dir)
        table.add_row("Outputs", self.paths.outputs_dir)
        if self.paths.excel_report_template:
            table.add_row("Excel template", self.paths.excel_report_template)
        return Panel(
            table,
            border_style="blue",
            title="[bold magenta]Directories[/bold magenta]",
        )
