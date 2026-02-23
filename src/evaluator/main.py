"""
Main entry point for the audio models evaluator.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pyfiglet import figlet_format
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import RichLog, Static
from textual import work
from evaluation_runner import EvaluationRunner
from app_types import AppContext, RuntimePaths
from report_generators.summary_md_report_generator import generate_summary_md_report
from ui.transcription_progress_panel import TranscriptionProgressPanel
from ui.results_panel import ResultsPanel
from ui.messages import TranscriptionProgressUpdate

# Ensure the src/evaluator directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Custom theme to style markdown headings
custom_theme = Theme({
    "markdown.h2": "bold magenta"
})

console = Console(theme=custom_theme)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _create_run_dirs(outputs_base_path: str, config_filename: str) -> tuple[str, str, str]:
    """
    Creates the run output directory structure.

    Args:
        outputs_base_path (str): The base output directory.
        config_filename (str): The name of the configuration file.

    Returns:
        tuple[str, str, str]: A tuple containing the paths to the intermediate and output directories, and the eval directory path.
    """
    # timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # run_outputs_dir_name = f"{config_filename}-{timestamp}"
    eval_dir_name = f"{config_filename}"

    logger.debug("Run Eval Directory Name: %s", eval_dir_name)

    run_eval_path = os.path.join(outputs_base_path, eval_dir_name)

    os.makedirs(run_eval_path, exist_ok=True)

    # Create subdirectories
    intermediate_dir = os.path.join(run_eval_path, "intermediate")
    outputs_dir = os.path.join(run_eval_path, "outputs")

    os.makedirs(intermediate_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    logger.debug("Created subdirectory: %s", intermediate_dir)
    logger.debug("Created subdirectory: %s", outputs_dir)

    return intermediate_dir, outputs_dir, run_eval_path


def _resolve_config_path(base_dir: str, rel_path: str) -> str:
    """Helper to resolve a path relative to the config directory."""
    if not rel_path:
        return ""
    return os.path.abspath(os.path.join(base_dir, rel_path))


def setup_paths(config_path: str, config: dict) -> RuntimePaths:
    """
    Sets up the output directories based on the configuration file.

    Args:
        config_path (str): The path to the json configuration file.
        config (dict): The loaded configuration dictionary.

    Returns:
        RuntimePaths: An object containing the input, intermediate, and output directories.
    """
    try:
        # Get the directory of the configuration file
        config_dir = os.path.dirname(os.path.abspath(config_path))

        logger.debug("Current Directory: %s", os.getcwd())
        logger.debug("Config Directory: %s", config_dir)

        # Resolve input and output paths relative to the location of the json file
        paths_config = config.get("paths", {})

        inputs_path = _resolve_config_path(
            config_dir, paths_config.get("inputs", ""))
        outputs_path = _resolve_config_path(
            config_dir, paths_config.get("outputs", ""))

        excel_report_template = None
        template_rel_path = paths_config.get("excel-report-template")
        if template_rel_path:
            excel_report_template = _resolve_config_path(
                config_dir, template_rel_path)

        logger.debug("Inputs Path: %s", inputs_path)
        logger.debug("Outputs Path: %s", outputs_path)
        if excel_report_template:
            logger.debug("Excel Report Template: %s", excel_report_template)

        # Create output directory: <filename>
        intermediate_dir, outputs_dir, eval_dir = _create_run_dirs(
            outputs_path, Path(config_path).stem)

        return RuntimePaths(
            inputs_dir=inputs_path,
            intermediate_dir=intermediate_dir,
            outputs_dir=outputs_dir,
            eval_dir=eval_dir,
            excel_report_template=excel_report_template
        )

    except Exception as e:
        logger.error("Error setting up directories: %s", e)
        raise


def _build_banner_renderable(args: argparse.Namespace) -> Panel:
    art = figlet_format("Transcription\n    Evals", font="standard")
    title_text = Text(art, style="bold blue")
    title_text.append(
        "  Audio Model Transcription Evaluations\n", style="bold magenta")

    config_abs = os.path.abspath(args.config_file)
    lazy_status = "✅ [bold green]Enabled[/bold green]" if args.lazy_transcription else "[bold yellow]Disabled[/bold yellow]"

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold magenta")
    info_table.add_column(style="blue")
    info_table.add_row("Config file", config_abs)
    info_table.add_row("Lazy transcription", lazy_status)

    content = Group(title_text, info_table)
    return Panel(content, border_style="magenta",
                 title="[bold hot_pink]Transcription Evals[/bold hot_pink]")


def _build_directories_panel(paths: RuntimePaths) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold magenta", min_width=20)
    table.add_column(style="blue")
    table.add_row("Inputs", paths.inputs_dir)
    table.add_row("Eval root", paths.eval_dir)
    table.add_row("Intermediate", paths.intermediate_dir)
    table.add_row("Outputs", paths.outputs_dir)
    if paths.excel_report_template:
        table.add_row("Excel template", paths.excel_report_template)
    return Panel(table, border_style="blue",
                 title="[bold magenta]Directories[/bold magenta]")


def _setup_logging(config_file: Path) -> None:
    """
    Configures file logging for the current run.

    Creates a 'logs' directory beside the config file and writes a DEBUG-level
    log file named '<config_file_stem>-<yyyymmdd-hhmmss>.log'. The existing
    console handler (set up by basicConfig) is kept at INFO level.

    Args:
        config_file (Path): Path to the JSON configuration file.
    """
    config_path = config_file
    logs_dir = Path(config_path.parent, "logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_filename = f"{config_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    log_filepath = logs_dir / log_filename

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    # Strip console StreamHandlers — Textual owns the terminal from here on
    root_logger.handlers = [
        h for h in root_logger.handlers
        if not isinstance(h, logging.StreamHandler)
    ]
    root_logger.addHandler(file_handler)

    logger.debug("File logging initialised: %s", log_filepath)


class RichLogHandler(logging.Handler):
    """Forwards log records to the Textual RichLog widget."""

    def __init__(self, app: "EvaluatorApp") -> None:
        super().__init__()
        self.app = app
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        try:
            log_widget = self.app.query_one("#log-panel", RichLog)
            self.app.call_from_thread(log_widget.write, msg)
        except Exception:  # pylint: disable=broad-exception-caught
            pass


class EvaluatorApp(App):
    """Textual TUI for the audio model evaluator."""

    CSS = """
    #log-panel {
        dock: bottom;
        height: 7;
        border-top: solid blue;
        background: $surface;
    }
    #main-content {
        height: 1fr;
    }
    """

    def __init__(
        self,
        args: argparse.Namespace,
        config: dict,
        paths: RuntimePaths,
    ) -> None:
        super().__init__()
        self._args = args
        self._config = config
        self._paths = paths
        self._summary_markdown: str | None = None

    def compose(self) -> ComposeResult:
        """Build the widget layout: scrollable main area + fixed log panel."""
        with VerticalScroll(id="main-content"):
            yield Static(_build_banner_renderable(self._args))
            yield Static(_build_directories_panel(self._paths))
            yield TranscriptionProgressPanel(
                inputs=self._config.get("inputs", []),
                models=self._config.get("models", []),
            )
            yield Static(
                ResultsPanel(None, self._args, self._paths).build(),
                id="results-panel",
            )
        yield RichLog(id="log-panel", auto_scroll=True, markup=True)

    def on_ready(self) -> None:
        """Wire up the log handler and start the evaluation worker."""
        logging.getLogger().addHandler(RichLogHandler(self))
        self._run_evaluation()

    def on_transcription_progress_update(
        self, message: TranscriptionProgressUpdate
    ) -> None:
        """Route progress update messages to the progress panel."""
        try:
            progress_widget = self.query_one(TranscriptionProgressPanel)
            progress_widget.post_message(message)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def get_summary_markdown(self) -> str | None:
        """Retrieve the generated summary markdown after evaluation completes."""
        return self._summary_markdown

    def get_safe_summary_markdown(self) -> str:
        """Get the summary markdown, or a safe default if it's not available."""
        return self.get_summary_markdown() or "**__Summary markdown is not available.__**"

    @work
    async def _run_evaluation(self) -> None:
        """Run EvaluationRunner in an async Textual worker; exit when done."""
        try:
            app_context = AppContext(
                args=self._args, config=self._config, paths=self._paths, app=self
            )
            await EvaluationRunner(app_context).run()
            self._summary_markdown = await generate_summary_md_report(
                self._args.config_file,
                self._paths.outputs_dir,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Evaluation failed: %s", exc)
        finally:
            self.exit()


def main():
    """
    Main function to run the evaluator.
    """
    try:
        load_dotenv()

        parser = argparse.ArgumentParser(
            description="Evaluate audio models based on a configuration file.")
        parser.add_argument(
            "config_file", help="Path to the JSON configuration file")
        parser.add_argument(
            "--lazy-transcription", action="store_true", default=False,
            help="Skip transcription if the output file already exists")
        args = parser.parse_args()

        if not os.path.isfile(args.config_file):
            logger.error("Configuration file not found: %s", args.config_file)
            sys.exit(1)

        _setup_logging(Path(args.config_file))

        # file: snyk-ignore python/PT
        config_text = Path(args.config_file).read_text(encoding='utf-8')
        config = json.loads(config_text)

        paths = setup_paths(args.config_file, config)
        logger.debug("Paths set up: %s", paths)

        console.print(_build_banner_renderable(args))
        console.print(_build_directories_panel(paths))

        app = EvaluatorApp(args, config, paths)
        app.run()

        # Print results after TUI exits
        console.print(ResultsPanel(
            app.get_safe_summary_markdown(), args, paths).build())

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception in main: %s", e)


if __name__ == "__main__":
    main()
