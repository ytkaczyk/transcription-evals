"""
Main entry point for the audio models evaluator.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from evaluator import Evaluator
from evaluator_types import GlobalContext, RuntimeDirectories

# Ensure the src/evaluator directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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

        evaluator = Evaluator(global_context)
        evaluator.run()

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception in main: %s", e)


if __name__ == "__main__":
    main()
