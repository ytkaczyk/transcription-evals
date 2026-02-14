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
# from transcribers.deepgram import DeepgramTranscriber

# Ensure the src/evaluator directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _create_run_dirs(output_base_path: str, config_filename: str) -> tuple[str, str]:
    """
    Creates the run output directory structure.

    Args:
        output_base_path (str): The base output directory.
        config_filename (str): The name of the configuration file.

    Returns:
        tuple[str, str]: A tuple containing the paths to the intermediate and output directories.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_output_dir_name = f"{config_filename}-{timestamp}"

    logger.info("Run Output Directory Name: %s", run_output_dir_name)

    run_output_path = os.path.join(output_base_path, run_output_dir_name)

    os.makedirs(run_output_path, exist_ok=True)

    # Create subdirectories
    intermediate_dir = os.path.join(run_output_path, "intermediate")
    output_dir = os.path.join(run_output_path, "output")

    os.makedirs(intermediate_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Created subdirectory: %s", intermediate_dir)
    logger.info("Created subdirectory: %s", output_dir)

    return intermediate_dir, output_dir


def setup_directories(config_path: str):
    """
    Sets up the output directories based on the configuration file.

    Args:
        config_path (str): The path to the json configuration file.

    Returns:
        dict: A dictionary containing the input, intermediate, and output directories.
    """
    try:
        # Get the directory of the configuration file
        config_dir = os.path.dirname(os.path.abspath(config_path))

        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        cwd = os.getcwd()
        logger.info("Current Directory: %s", cwd)
        logger.info("Config Directory: %s", config_dir)

        # Resolve input and output paths
        # Relative paths are relative to the location of the json file
        paths = config.get("paths", {})
        input_path_str = paths.get("input", "")
        output_path_str = paths.get("output", "")

        # Join with config_dir first, then normalize
        input_path = os.path.abspath(os.path.join(config_dir, input_path_str))
        output_path = os.path.abspath(
            os.path.join(config_dir, output_path_str))

        logger.info("Input Path: %s", input_path)
        logger.info("Output Path: %s", output_path)

        # Create output directory: <filename>-<yyyymmdd-hhmmss>
        config_filename = Path(config_path).stem

        intermediate_dir, output_dir = _create_run_dirs(
            output_path, config_filename)

        return {
            "input_dir": input_path,
            "intermediate_dir": intermediate_dir,
            "output_dir": output_dir
        }

    except Exception as e:
        logger.error("Error setting up directories: %s", e)
        raise


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
        args = parser.parse_args()

        dirs = setup_directories(args.config_file)
        logger.info("Directories set up: %s", dirs)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception in main: %s", e)


if __name__ == "__main__":
    main()
