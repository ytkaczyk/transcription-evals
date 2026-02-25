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
+------------------+
| Evaluator Runner |
+------------------+
   |           |
   |           +------------------+
   |                              |
   v                              v
Lazy Transcript Check        Transcriber Providers
(cache intermediate JSON)    (Deepgram, AssemblyAI, etc.)
   |                              |
   +--------------+---------------+
                  v
        Normalization + WER
                  |
                  v
        Stats + Report Outputs
```

## Core Components

### CLI + TUI Entry Point

- Entry point: `src/evaluator/main.py`
- Provides a Rich/Textual-based terminal UI with progress and logs
- Loads environment variables and experiment configuration
- Invokes the evaluation runner

### Evaluation Runner

- File: `src/evaluator/evaluation_runner.py`
- Orchestrates the entire evaluation
- Resolves paths, loads inputs, and coordinates transcribers
- Applies lazy transcription checks to avoid rework

### Transcriber Abstraction

- Base class: `src/evaluator/transcribers/abstract_transcriber.py`
- Each provider implementation inherits from `AbstractTranscriber`
- Output normalized to `TranscriptResult` with `ConversationItem` entries
- Examples:
  - `src/evaluator/transcribers/deepgram.py`
  - `src/evaluator/transcribers/assembly_ai.py`

### Normalization + Metrics

- Standardizes transcript format and timestamps ("HH:MM:SS")
- Calculates Word Error Rate (WER) against ground truth
- Writes intermediate transcript JSON for re-use in later runs

### Report Generation

- Markdown and Excel reports are generated from stats outputs
- Report generators live in `src/evaluator/report_generators/`

### Preprocessors

- Located in `src/preprocessors/`
- Utilities to normalize datasets and audio input formats
- Examples:
  - `podcast_transcript_to_json.py`
  - `reencode_mp3_16k_mono.py`

## Data Artifacts

- Inputs: `experiments/datasets/<dataset>/inputs/`
- Ground truth transcripts: JSON alongside inputs
- Intermediate transcripts: `experiments/evals/<dataset>/intermediate/`
- Metrics outputs: `experiments/evals/<dataset>/outputs/`
- Reports: Excel and Markdown in outputs directory

## Configuration Model

- Experiment configuration is defined by a JSON file
- Key sections include:
  - `inputs`: audio/transcript pairs
  - `models`: transcription provider list + options
  - `paths`: inputs/outputs/report-template locations

## Execution Model

- Run from `src/evaluator` with `uv`:
  - `uv run main.py <path_to_config.json>`
- Optional `--lazy-transcription` flag reuses intermediate transcripts

## Extensibility Points

- Add a new provider:
  1. Create a new class in `src/evaluator/transcribers/`
  2. Inherit from `AbstractTranscriber`
  3. Normalize output to `TranscriptResult`
  4. Export in `src/evaluator/transcribers/__init__.py`

- Add a new report format:
  1. Implement a generator in `src/evaluator/report_generators/`
  2. Wire it into the evaluation runner output stage
