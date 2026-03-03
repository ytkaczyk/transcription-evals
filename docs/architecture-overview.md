# Architecture Overview

## Purpose

Transcription Evals is a Python-based framework for evaluating audio
transcription models (STT/ASR). It runs experiments defined in JSON
configuration files, sends audio to transcription providers, normalizes
results, computes error metrics, and emits structured reports.

## High-Level Flow

```
Configuration JSON
        |
        v
+-------------------------------+
|   main.py  (CLI + TUI)        |
|   EvaluatorApp (Textual)      |
+-------------------------------+
        |
        v
+-------------------------------+
|     EvaluationRunner          |
|  (asyncio.gather per model)   |
+-------------------------------+
     |                |
     v                v
Lazy Check      TranscriberFactory
(skip if         .get_transcriber()
 cached)              |
     |                v
     |      +-------------------+
     |      |  AbstractTranscriber
     |      |  (one per model,  |
     |      |   runs in thread) |
     |      +-------------------+
     |         Deepgram | AssemblyAI
     |         AWSTranscribe | Voxtral
     |                |
     +----------------+
              |
              v
     TranscriptResult  (JSON cached to intermediate/)
              |
              v
     jiwer metrics  →  stats JSON  (outputs/)
              |
     +--------+--------+
     |        |        |
     v        v        v
 Excel      Md       SummaryMd
 Report    Report    Report (TUI)
```

## Core Components

### CLI + TUI Entry Point

- Entry point: `src/evaluator/main.py`
- `main()` loads `.env` via `python-dotenv`, parses CLI arguments, initializes
  logging, and launches `EvaluatorApp`
- `EvaluatorApp` is a [Textual](https://textual.textualize.io/) `App` subclass
  that renders the full terminal UI during the run
- After `EvaluatorApp` exits, `main()` prints the final results summary to the
  console (primary terminal buffer) so it remains visible after the TUI closes

#### Dual-render pattern

Rich renderables (banner, directory listing, results) are displayed in two
places:

1. **Primary buffer** — `console.print(renderable)` before and after
   `EvaluatorApp.run()` so the output persists once Textual exits
2. **Textual `Static` widget** — the same renderable is mounted inside
   `EvaluatorApp.compose()` so it is visible while the TUI is running

#### Logging

- `_setup_logging()` creates a file handler at `logs/<config-stem>-<timestamp>.log`
- All `StreamHandler` instances are stripped from the root logger before
  Textual starts to prevent garbled terminal output
- Log records are forwarded to the `RichLog` widget via `RichLogHandler`, a
  custom `logging.Handler` that calls
  `app.call_from_thread(log_widget.write, msg)` — safe from both the event-loop
  thread and `asyncio.to_thread` worker threads

### Evaluation Runner

- File: `src/evaluator/evaluation_runner.py`
- `run()` is an async method; it launches one `asyncio.to_thread` task per
  configured model and waits for all of them via `asyncio.gather()`

#### Concurrency model

| Dimension | Strategy |
|---|---|
| Across models | Parallel — each model runs in its own thread pool worker |
| Within a model | Sequential — inputs are processed one at a time to avoid Windows IocpProactor contention |

#### Per-input processing steps

1. Check lazy flag + existence of cached intermediate JSON
2. Post `TranscriptionProgressUpdate("Transcribing")` to TUI
3. Call `transcriber.transcribe_sync(audio_path, options)`
4. Serialize `TranscriptResult` as JSON to `intermediate/`
5. Post `TranscriptionProgressUpdate("Processing")`
6. Load hypothesis + reference transcripts, run `jiwer`, write stats JSON to `outputs/`
7. Post `TranscriptionProgressUpdate(completed=True)`

#### Path safety

`_validate_safe_path(base_dir, file_path)` checks that the resolved path shares
a common prefix with `base_dir` using `os.path.commonpath`, blocking path
traversal attempts.

### Type System

| Class | File | Purpose |
|---|---|---|
| `RuntimePaths` | `app_types.py` | `inputs_dir`, `intermediate_dir`, `outputs_dir`, `eval_dir`, `excel_report_template` |
| `AppContext` | `app_types.py` | `args`, `config`, `paths: RuntimePaths`, `app: App \| None` |
| `EvaluationContext` | `evaluation_runner_types.py` | Per-iteration state: `model`, `input`, `output_stem`, `transcript_path`, `stats_path` |

### Transcriber Abstraction

- Base class: `src/evaluator/transcribers/abstract_transcriber.py`
- Required overrides:
  - `name -> str` (property)
  - `transcribe_sync(audio_file_path, options) -> TranscriptResult`
- Provided for free: `async transcribe(...)` — wraps `transcribe_sync` in
  `asyncio.to_thread`

#### TranscriberFactory

`src/evaluator/transcribers/transcriber_factory.py` implements a static
registry:

| Method | Description |
|---|---|
| `register(name, cls)` | Associate a string key with a transcriber class |
| `get_transcriber(name, **kwargs)` | Instantiate by key; raises `ValueError` if not found |
| `list_transcribers()` | Return all registered keys |

Registrations are wired in `src/evaluator/transcribers/__init__.py`:

| Registry key | Class | Required env vars |
|---|---|---|
| `"Deepgram"` | `DeepgramTranscriber` | `DEEPGRAM_API_KEY` |
| `"AssemblyAI"` | `AssemblyAITranscriber` | `ASSEMBLYAI_API_KEY` |
| `"AWSTranscribe"` | `AWSTranscribeTranscriber` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_S3_BUCKET` |
| `"Voxtral"` | `MistralVoxtralTranscriber` | `MISTRAL_API_KEY` |

#### Output types

```python
@dataclass
class ConversationItem:
    timestamp: str   # "HH:MM:SS"
    person: str
    content: str

@dataclass
class TranscriptResult:
    name: str
    conversation: List[ConversationItem]
    duration: float = 0.0
    raw_output: Optional[Dict[str, Any]] = None
```

#### Provider details

**Deepgram** — default options `model=nova-3`, `smart_format`, `diarize`,
`punctuate`, `utterances`; strict `isinstance(response, ListenV1Response)` check
before attribute access.

**AssemblyAI** — default `speech_models=["universal-3-pro"]`,
`speaker_labels=True`, configurable `prompt`; falls back to a single
`ConversationItem(timestamp="00:00:00", person="Unknown")` if no utterance
diarization is returned.

**AWSTranscribe** — workflow: upload MP3 to S3 → start Transcribe job → poll
every 5 s → download transcript JSON → delete S3 object and Transcribe job.

**Voxtral (Mistral)** — default `model=voxtral-mini-latest`, `diarize=True`,
`timestamp_granularities=["segment"]`; detects `language` +
`timestamp_granularities` incompatibility and silently drops the latter with a
warning.

### Normalization + Metrics

Transcripts are normalized before metric computation:
- lowercase
- expand contractions
- remove punctuation
- strip leading/trailing whitespace

Eight metrics are computed per (model, input) pair using
[jiwer](https://github.com/jitsi/jiwer) and stored in a stats JSON file under
`outputs/`:

| Metric | Raw | Normalized |
|---|---|---|
| Word Error Rate | `wer` | `normalized_wer` |
| Match Error Rate | `mer` | `normalized_mer` |
| Word Information Lost | `wil` | `normalized_wil` |
| Character Error Rate | `cer` | `normalized_cer` |

Stats files also record `audio_file_name`, `audio_file_duration`, `model_name`,
`model_label`, `reference_text`, `hypothesis_text`, and their normalized forms.

### Report Generation

Three generators live in `src/evaluator/report_generators/`:

| Class | Output | Trigger |
|---|---|---|
| `ExcelReportGenerator` | `<config-stem>-report.xlsx` in `eval_dir` | Only when `excel-report-template` path is configured; copies template then writes a "Data" sheet via `openpyxl` |
| `MdReportGenerator` | `<config-stem>-report.md` in `eval_dir` | Always; detailed per-input breakdown including audio metadata |
| `SummaryMdReportGenerator` | In-memory string | Always; two summary tables ("Inputs" and "Result Summary") displayed in the `ResultsPanel` widget and printed to console after exit |

### UI Architecture

Six UI components are defined in `src/evaluator/ui/`:

| Class | File | Type | Responsibility |
|---|---|---|---|
| `BannerPanel` | `banner_panel.py` | Rich renderable | ASCII art (pyfiglet), config path, lazy-transcription status |
| `DirectoriesPanel` | `directories_panel.py` | Rich renderable | Displays all `RuntimePaths` fields |
| `ResultsPanel` | `results_panel.py` | Rich renderable | Summary markdown + report file status (✅/❌) |
| `TranscriptionProgressPanel` | `transcription_progress_panel.py` | Textual `Container` | Per-model grid: model name \| `ProgressBar` \| status label; total = `len(inputs) × 2` steps |
| `FooterLogPanel` | `footer_log_panel.py` | Textual `Container` | Docked at bottom (height 7), contains `RichLog#log-panel` |
| `TranscriptionProgressUpdate` | `messages.py` | Textual `Message` | Carries `model_name`, `model_label`, `status`, `audio_filename`, `completed` |

Progress updates flow from `EvaluationRunner` worker threads to
`TranscriptionProgressPanel` via `app.call_from_thread(app.post_message, msg)`.
The panel handles `on_transcription_progress_update()` and advances the
appropriate `ProgressBar` by looking up widget references stored in
`_progress_state`.

### Utils

`src/evaluator/utils/audio_metadata_extractor.py` — `AudioMetadataExtractor`

Uses [mutagen](https://mutagen.readthedocs.io/) to extract `encoding`,
`sampling_rate`, `channels`, and `duration` from MP3, WAV, and M4A files.
Used by `MdReportGenerator` and `SummaryMdReportGenerator` to enrich report
tables with audio file metadata.

### Preprocessors

Located in `src/preprocessors/`. Stand-alone utilities for dataset preparation:

- `podcast_transcript_to_json.py` — converts raw podcast transcripts to the
  JSON format expected by the evaluator
- `reencode_mp3_16k_mono.py` — resamples and converts audio files to 16 kHz
  mono MP3 for consistent model input

## Data Artifacts

| Artifact | Location |
|---|---|
| Input audio files | `experiments/datasets/<dataset>/inputs/` |
| Ground-truth transcripts (JSON) | `experiments/datasets/<dataset>/inputs/` (alongside audio) |
| Cached intermediate transcripts | `experiments/evals/<dataset>/intermediate/` |
| Per-model/input stats (JSON) | `experiments/evals/<dataset>/outputs/` |
| Detailed Markdown report | `experiments/evals/<dataset>/` |
| Excel report | `experiments/evals/<dataset>/` |

## Configuration Model

Experiment configuration is a JSON file with three top-level keys:

```json
{
  "inputs": [
    { "audio": "sample.mp3", "transcript": "sample.json" }
  ],
  "models": [
    {
      "name": "Deepgram",
      "label": "nova-3-enhanced",
      "options": { "model": "nova-3-enhanced" }
    },
    {
      "name": "Deepgram",
      "label": "nova-3",
      "options": { "model": "nova-3" }
    }
  ],
  "paths": {
    "inputs": "../datasets/podcasts/inputs",
    "outputs": "./evals/podcasts",
    "excel-report-template": "../../templates/report-template.xlsx"
  }
}
```

- **`inputs`** — list of `{ audio, transcript }` pairs; paths are relative to
  the `paths.inputs` directory
- **`models[].name`** — registry key passed to `TranscriberFactory.get_transcriber()`
- **`models[].label`** — optional; allows running the same provider multiple
  times with different options; the label is appended to intermediate and stats
  file names (`<Name>-<Label>-<sample-stem>`)
- **`models[].options`** — passed verbatim to `transcribe_sync()` as the
  `options` argument
- **`paths.excel-report-template`** — optional; omitting it skips Excel report
  generation entirely

## Execution Model

Run from `src/evaluator` with `uv`:

```bash
cd src/evaluator
uv run main.py <path_to_config.json>
uv run main.py <path_to_config.json> --lazy-transcription
```

`--lazy-transcription` skips the transcription API call for any input whose
intermediate JSON already exists on disk, reusing the cached result instead.

## Dependencies

Key packages (Python ≥ 3.13 required):

| Package | Version | Purpose |
|---|---|---|
| `deepgram-sdk` | ≥ 5.3.2 | Deepgram transcription |
| `assemblyai` | ≥ 0.33.0 | AssemblyAI transcription |
| `mistralai` | ≥ 1.12.4 | Mistral Voxtral transcription |
| `boto3` | ≥ 1.42.55 | AWS S3 + Transcribe |
| `jiwer` | ≥ 4.0.0 | WER / MER / WIL / CER metrics |
| `pandas` | ≥ 3.0.1 | Report data frames |
| `openpyxl` | ≥ 3.1.5 | Excel report writing |
| `rich` | ≥ 14.3.3 | Terminal rendering |
| `textual` | ≥ 8.0.0 | TUI framework |
| `pyfiglet` | ≥ 1.0.4 | ASCII banner art |
| `mutagen` | ≥ 1.47.0 | Audio file metadata |
| `python-dotenv` | ≥ 1.2.1 | `.env` loading |

## Extensibility Points

### Add a new transcription provider

1. Create a new class in `src/evaluator/transcribers/`
2. Inherit from `AbstractTranscriber`
3. Implement `name -> str` and `transcribe_sync(audio_file_path, options) -> TranscriptResult`
4. Normalize output to `TranscriptResult` with `ConversationItem` entries
   (timestamps as `"HH:MM:SS"`)
5. Register in `src/evaluator/transcribers/__init__.py`:
   ```python
   TranscriberFactory.register("MyProvider", MyProviderTranscriber)
   ```
6. Add the required API key(s) to `.env` and document them in the README

### Add a new report format

1. Implement a generator class in `src/evaluator/report_generators/`
2. Add an async `generate()` method that reads from `outputs_dir` (stats JSON files)
3. Wire it into `EvaluationRunner.run()` alongside the existing generators
