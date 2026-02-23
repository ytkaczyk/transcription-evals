"""
Result panel component for displaying evaluation results and report status.
"""
import argparse
import os
from pathlib import Path
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from app_types import RuntimePaths


class ResultsPanel:
    """Rich-only panel for displaying evaluation results and report file status."""

    def __init__(
        self,
        summary_markdown: str | None,
        args: argparse.Namespace,
        paths: RuntimePaths,
    ) -> None:
        """
        Initialize the ResultsPanel.

        Args:
            summary_markdown: Optional markdown string containing the results summary.
            args: Command-line arguments containing config_file path.
            paths: RuntimePaths object containing directory information.
        """
        self.summary_markdown = summary_markdown
        self.args = args
        self.paths = paths

    def _get_report_paths(self) -> tuple[str, str | None]:
        """Build the expected report paths for the current run."""
        report_stem = f"{Path(self.args.config_file).stem}-report"
        md_report_path = os.path.join(self.paths.eval_dir, f"{report_stem}.md")
        xlsx_report_path = None
        if self.paths.excel_report_template:
            xlsx_report_path = os.path.join(
                self.paths.eval_dir, f"{report_stem}.xlsx"
            )
        return md_report_path, xlsx_report_path

    def build(self) -> Panel:
        """Build the Results panel with summary markdown and report paths."""
        content_parts: list = []

        if self.summary_markdown:
            summary_text = self.summary_markdown.strip()
            if not summary_text:
                summary_text = "Results summary unavailable."

            # Create content with markdown summary
            content_parts.append(Markdown(summary_text))

        # Get report paths and check existence
        md_report_path, xlsx_report_path = self._get_report_paths()
        md_exists = os.path.exists(md_report_path)
        xlsx_exists = (
            bool(xlsx_report_path and os.path.exists(xlsx_report_path))
        )

        # Add reports table
        reports_table = Table.grid(padding=(0, 2))
        reports_table.add_column(style="bold magenta", min_width=20)
        reports_table.add_column(style="blue")

        md_status = "✅" if md_exists else "❌"
        reports_table.add_row("Markdown report", f"{md_status} {md_report_path}")

        if xlsx_report_path:
            xlsx_status = "✅" if xlsx_exists else "❌"
            reports_table.add_row(
                "Excel report", f"{xlsx_status} {xlsx_report_path}"
            )
        else:
            reports_table.add_row(
                "Excel report", "❌ Not generated (no template)"
            )

        content_parts.append(reports_table)

        return Panel(
            Group(*content_parts),
            border_style="blue",
            title="[bold magenta]Results[/bold magenta]",
        )
