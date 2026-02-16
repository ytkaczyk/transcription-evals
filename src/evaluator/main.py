"""
Main entry point for the audio models evaluator.
"""
import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
# from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from transcribers.transcriber_factory import TranscriberFactory

# Ensure the src/evaluator directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RuntimeDirectories:
    """
    Holds the paths for the input, intermediate, and output directories.
    """
    inputs_dir: str
    intermediate_dir: str
    outputs_dir: str


@dataclass
class GlobalContext:
    """
    Holds the global state of the application.
    """
    args: argparse.Namespace
    config: dict
    directories: RuntimeDirectories


def _create_run_dirs(outputs_base_path: str, config_filename: str) -> tuple[str, str]:
    """
    Creates the run output directory structure.

    Args:
        outputs_base_path (str): The base output directory.
        config_filename (str): The name of the configuration file.

    Returns:
        tuple[str, str]: A tuple containing the paths to the intermediate and output directories.
    """
    # timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # run_outputs_dir_name = f"{config_filename}-{timestamp}"
    run_outputs_dir_name = f"{config_filename}"

    logger.info("Run Output Directory Name: %s", run_outputs_dir_name)

    run_outputs_path = os.path.join(outputs_base_path, run_outputs_dir_name)

    os.makedirs(run_outputs_path, exist_ok=True)

    # Create subdirectories
    intermediate_dir = os.path.join(run_outputs_path, "intermediate")
    outputs_dir = os.path.join(run_outputs_path, "outputs")

    os.makedirs(intermediate_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    logger.info("Created subdirectory: %s", intermediate_dir)
    logger.info("Created subdirectory: %s", outputs_dir)

    return intermediate_dir, outputs_dir


def setup_directories(config_path: str, config: dict) -> RuntimeDirectories:
    """
    Sets up the output directories based on the configuration file.

    Args:
        config_path (str): The path to the json configuration file.
        config (dict): The loaded configuration dictionary.

    Returns:
        RuntimeDirectories: An object containing the input, intermediate, and output directories.
    """
    try:
        # Get the directory of the configuration file
        config_dir = os.path.dirname(os.path.abspath(config_path))

        cwd = os.getcwd()
        logger.info("Current Directory: %s", cwd)
        logger.info("Config Directory: %s", config_dir)

        # Resolve input and output paths
        # Relative paths are relative to the location of the json file
        paths = config.get("paths", {})
        inputs_path_str = paths.get("inputs", "")
        outputs_path_str = paths.get("outputs", "")

        # Join with config_dir first, then normalize
        inputs_path = os.path.abspath(
            os.path.join(config_dir, inputs_path_str))
        outputs_path = os.path.abspath(
            os.path.join(config_dir, outputs_path_str))

        logger.info("Inputs Path: %s", inputs_path)
        logger.info("Outputs Path: %s", outputs_path)

        # Create output directory: <filename>-<yyyymmdd-hhmmss>
        config_filename = Path(config_path).stem

        intermediate_dir, outputs_dir = _create_run_dirs(
            outputs_path, config_filename)

        return RuntimeDirectories(
            inputs_dir=inputs_path,
            intermediate_dir=intermediate_dir,
            outputs_dir=outputs_dir
        )

    except Exception as e:
        logger.error("Error setting up directories: %s", e)
        raise


def _validate_safe_path(base_dir: str, file_path: str) -> str:
    """
    Validates that file_path is safe to use relative to base_dir.
    It returns the absolute path formed by joining base_dir and file_path.
    If the path resolves outside base_dir, raises ValueError.
    """
    # Use os.path.abspath to resolve .. components
    base_dir = os.path.abspath(base_dir)
    full_path = os.path.abspath(os.path.join(base_dir, file_path))

    # Check if full_path starts with base_dir
    # os.path.commonpath is safer than startswith for path comparison
    if os.path.commonpath([base_dir, full_path]) != base_dir:
        raise ValueError(f"Path traversal attempt detected: {file_path}")

    return full_path


def _generate_output_stem(model_name: str, label: str | None, audio_file: str) -> str:
    input_stem = Path(audio_file).stem
    if label:
        return f"{model_name}-{label}-{input_stem}"
    return f"{model_name}-{input_stem}"


def _transcribe_audio_file(transcriber, model_config: dict, input_item: dict, output_stem: str, global_context: GlobalContext) -> str:
    # Generate output file name and path and skip the process if the file exists and lazy_transcription is True
    transcript_filename = f"{output_stem}-transcript.json"
    transcript_path = _validate_safe_path(
        global_context.directories.intermediate_dir, transcript_filename)

    if global_context.args.lazy_transcription and os.path.exists(transcript_path):
        logger.info(
            "Lazy transcription: Output file %s already exists. Skipping.", transcript_filename)
        return transcript_path

    audio_file = input_item.get("audio")
    if not audio_file:
        raise ValueError("Input item missing required 'audio' field.")

    logger.info("Transcribing %s with %s (Label: %s) -> %s",
                audio_file, model_config.get("name"), model_config.get("label"), transcript_filename)

    try:
        # Validate paths to prevent traversal
        audio_full_path = _validate_safe_path(
            global_context.directories.inputs_dir, audio_file)

        # Check input
        if not os.path.exists(audio_full_path):
            raise FileNotFoundError(f"Input file not found: {audio_full_path}")

        # Transcribe
        transcript_result = transcriber.transcribe(
            audio_full_path, options=model_config.get("options", {}))

        # Save
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(asdict(transcript_result),
                      f, indent=2, ensure_ascii=False)

        return transcript_path

    except ValueError as ve:
        logger.error("Validation error for %s: %s", audio_file, ve)
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error transcribing %s: %s", audio_file, e)
        raise


def process_evaluations(global_context: GlobalContext):
    """
    Runs the evaluation loop: Model -> Input -> Transcribe -> Save.
    """
    models = global_context.config.get("models", [])
    inputs = global_context.config.get("inputs", [])

    for model_config in models:
        model_name = model_config.get("name")
        if not model_name:
            continue

        label = model_config.get("label", None)

        # Create transcriber for each model
        # We create it once per model config to handle it efficiently
        try:
            transcriber = TranscriberFactory.get_transcriber(
                model_name)
        except ValueError as e:
            logger.error(e)
            continue

        for input_item in inputs:
            audio_file = input_item.get("audio")
            if not audio_file:
                continue

            output_stem = _generate_output_stem(
                model_name, label, audio_file)

            transcript_path = _transcribe_audio_file(
                transcriber, model_config, input_item, output_stem, global_context)

            logger.info("Transcript saved to: %s", transcript_path)


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

        # file: snyk-ignore python/PT
        config_text = Path(args.config_file).read_text(encoding='utf-8')
        config = json.loads(config_text)

        dirs = setup_directories(args.config_file, config)
        logger.info("Directories set up: %s", dirs)

        global_context = GlobalContext(
            args=args,
            config=config,
            directories=dirs
        )

        process_evaluations(global_context)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception in main: %s", e)


if __name__ == "__main__":
    main()
