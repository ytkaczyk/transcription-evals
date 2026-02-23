# Audio Models Evaluator - Copilot Instructions

## Project Overview
This project evaluates audio transcription models (STT/ASR). It is a Python-based application managed with `uv`.

## Architecture & patterns
- **Transcriber Interface**: All transcribers MUST inherit from `AbstractTranscriber` (in `src/evaluator/transcribers/abstract_transcriber.py`).
- **Data Standardization**: 
  - Output MUST be normalized to `TranscriptResult` containing a list of `ConversationItem` objects.
  - Defined in `src/evaluator/transcribers/types.py`.
  - Timestamps should be formatted as "HH:MM:SS".
- **Module Structure**: 
  - `src/evaluator/transcribers/` is a package. Expose new transcribers in `__init__.py`.

## specific coding standards
- **Dependency Management**: use `uv` for all package operations.
  - Run scripts: `uv run path/to/script.py`
  - Add packages: `uv add <package>`
  - Add dev packages: `uv add --dev <package>`
- **Type Safety**:
  - Use explicit type hints (`List`, `Optional`, `Dict`).
  - When working with 3rd party SDKs (like Deepgram), strictly vet response types (e.g., use `isinstance` checks for Union types) to avoid runtime attribute errors.
- **Logging**: Use `logging.getLogger(__name__)` instead of `print` for application logs.
- **Error Handling**: 
  - Wrap external API calls in `try/except` blocks.
  - Log errors with `logger.error` before raising or returning empty results.
- **Configuration**: Use `python-dotenv` to load environment variables (API keys) from `.env`.

## Development workflow
- The main entry point is `src/evaluator/main.py`.
- Run the evaluator from `src/evaluator` directory: `cd src/evaluator; uv run main.py`.
- **Validation**: After generating code, ALWAYS run the verification script to check tests and linting:
  - Run: `uv run scripts/verify.py`
  - Fix any issues revealed by the verification script before proceeding.


## UI patterns (Textual + Rich)

The application uses **Textual** for the TUI (built on Rich). The following patterns are established and must be followed for all new panels, progress bars, and widgets.

### Dual-render pattern for persistent output
Textual runs in the terminal's **alternate screen buffer**. When the app exits, the primary buffer is restored. To make content visible **both during the run and after exit**:

1. **Print to primary buffer** via `console.print(renderable)` *before* `EvaluatorApp(...).run()` — this output persists after Textual exits.
2. **Mount the same renderable as a `Static` widget** inside `compose()` — this makes it visible while the app is running.

```python
# In main() — prints to primary buffer (survives app exit)
console.print(_build_banner_renderable(args))
console.print(_build_directories_panel(paths))
EvaluatorApp(args, config, paths).run()

# In EvaluatorApp.compose() — shown while app runs
with VerticalScroll(id="main-content"):
    yield Static(_build_banner_renderable(self._args))
    yield Static(_build_directories_panel(self._paths))
yield RichLog(id="log-panel", auto_scroll=True, markup=True)
```

This is the **correct pattern for all future panels and progress bars** that should remain visible after the run.

### Log panel
- `RichLog` widget docked to the bottom (7 lines, `dock: bottom`)
- Log records forwarded via `RichLogHandler(logging.Handler)` using `app.call_from_thread(log_widget.write, msg)` — safe from both the event loop thread and `asyncio.to_thread` pool threads
- All `StreamHandler` instances are stripped from the root logger inside `_setup_logging()` before Textual starts, to prevent garbled output

### Worker pattern
- `EvaluationRunner.run()` is `async` — blocking I/O calls are wrapped with `asyncio.to_thread()` to keep the event loop free
- The Textual worker uses `@work` (asyncio coroutine worker, not `thread=True`) and calls `self.exit()` in a `finally` block to always return the shell prompt

### Color theme
- Borders/paths: `blue`
- Labels/panel titles: `bold magenta`
- Panel title accents: `bold hot_pink`
- Banner art: `bold blue`
- Subtitle: `bold magenta`
- Lazy transcription enabled: `bold green` / disabled: `bold yellow`

### Textual/Rich CSS & Styling Gotchas
- **CSS class name**: Must be named `DEFAULT_CSS` (not `CSS`) for Textual to recognize and apply the stylesheet.
- **Panel height**: Cannot be set to `auto` — must be computed dynamically based on content. In `__init__`, calculate height: `self.styles.height = len(models) + 2` (where +2 accounts for border/padding). This ensures the container properly constrains child widgets.
- **Grid column sizing**: Use `grid-columns: auto auto 1fr;` pattern — `auto` for fixed-width columns (model name, progress bar), then `1fr` for the final column to fill remaining space.
- **Color mapping**: Rich color names do **not** reliably map to Textual colors. Use `ansi_<color>` format **everywhere** (CSS rules AND Rich markup) for guaranteed proper rendering (e.g., `ansi_magenta`, `ansi_blue`, `ansi_green`). Use ansi colors in both CSS and in markup like `f"[ansi_blue]{text}[/ansi_blue]"`.
- **CSS class-based styling over inline markup**: Apply styling via CSS classes (`.model-label`, `.status-label`) rather than embedding Rich markup in widget content. Keep widget content plain and use CSS to define appearance. This separates concerns and makes styling consistent.
- **Widget references for updates**: Store widget references in state dicts to enable direct method calls like `.advance()` and `.update()`. Example: `state["progressbar_widget"] = progress_bar` then later `progress_bar.advance(1)`.
- **Rich markup whitespace**: When combining colors in markup, include spaces inside markup tags for proper rendering: `f"[white] {filename}[/white]"` not `f"[white]{filename}[/white]"` + space.


## Example: Transcriber Implementation
```python
class MyServiceTranscriber(AbstractTranscriber):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MY_SERVICE_API_KEY")
        # Validate key presence immediately
        
    @property
    def name(self) -> str:
        return "My Service Name"

    def transcribe(self, audio_file_path: str) -> TranscriptResult:
        # Implementation details...
        # Map 3rd party response -> List[ConversationItem]
        return TranscriptResult(name=self.name, conversation=items)
```