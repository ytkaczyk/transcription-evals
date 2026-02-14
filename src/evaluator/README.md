# Audio Models Evaluator

This project evaluates audio transcription models (STT/ASR).

## Setup

1. Install `uv`: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
2. Install dependencies:
   ```bash
   uv sync
   ```

## Running the Evaluator

The evaluator runs based on a configuration file that defines the inputs and models to test.

```bash
cd src/evaluator
uv run main.py <path_to_config.json>
```

Example:
```bash
uv run main.py ../../evals/podcasts.json
```

## Configuration File Format

The configuration file is a JSON file with the following structure:

```json
{
    "inputs": [
        {
            "sound": "sample-01.mp3",  // Audio file name
            "transcript": "sample-01.json"  // Ground truth transcript file name
        }
    ],
    "models": [
        {
            "name": "Deepgram",
            "options": [
                {
                    "model": "nova-3"
                }
            ]
        },
        {
            "name": "AssemblyAI"
        }
    ],
    "paths": {
        "input": "../datasets/podcasts/input",  // Base path for input files
        "output": "./results"  // Base path for output results
    }
}
```

## Transcript Format (Ground Truth)

The evaluator expects the ground truth transcript files (referenced in `inputs`) to follow this JSON structure:

```json
{
  "name": "transcript_identifier",
  "conversation": [
    {
      "timestamp": "HH:MM:SS",
      "person": "Speaker Name",
      "content": "Transcribed text content..."
    }
  ]
}
```

## Development

### Linting

Run Pylint:
```bash
uv run pylint --disable=C0301 <path/to/file.py>
```

Run Pyright:
```bash
uv run pyright .
```

### Testing

Run tests:
```bash
uv run pytest
```
