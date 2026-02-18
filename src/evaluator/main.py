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
from evaluation_runner import EvaluationRunner
from evaluation_runner_types import GlobalContext, RuntimePaths

# Ensure the src/evaluator directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

    logger.info("Run Eval Directory Name: %s", eval_dir_name)

    run_eval_path = os.path.join(outputs_base_path, eval_dir_name)

    os.makedirs(run_eval_path, exist_ok=True)

    # Create subdirectories
    intermediate_dir = os.path.join(run_eval_path, "intermediate")
    outputs_dir = os.path.join(run_eval_path, "outputs")

    os.makedirs(intermediate_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    logger.info("Created subdirectory: %s", intermediate_dir)
    logger.info("Created subdirectory: %s", outputs_dir)

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

        logger.info("Current Directory: %s", os.getcwd())
        logger.info("Config Directory: %s", config_dir)

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

        logger.info("Inputs Path: %s", inputs_path)
        logger.info("Outputs Path: %s", outputs_path)
        if excel_report_template:
            logger.info("Excel Report Template: %s", excel_report_template)

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

        paths = setup_paths(args.config_file, config)
        logger.info("Paths set up: %s", paths)

        global_context = GlobalContext(
            args=args,
            config=config,
            paths=paths
        )

        evaluator = EvaluationRunner(global_context)
        evaluator.run()

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception in main: %s", e)


if __name__ == "__main__":
    main()
