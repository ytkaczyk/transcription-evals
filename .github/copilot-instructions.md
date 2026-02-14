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