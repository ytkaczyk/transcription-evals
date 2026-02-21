from dataclasses import dataclass
import argparse


@dataclass
class RuntimePaths:
    """
    Holds the paths for the input, intermediate, and output directories.
    """
    inputs_dir: str
    intermediate_dir: str
    outputs_dir: str
    eval_dir: str
    excel_report_template: str | None = None


@dataclass
class AppContext:
    """
    Holds the global state of the application.
    """
    args: argparse.Namespace
    config: dict
    paths: RuntimePaths
