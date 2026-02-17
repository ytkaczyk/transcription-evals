from dataclasses import dataclass
import argparse

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


@dataclass
class EvaluationContext:
    """
    Holds the state for a single evaluation iteration.
    """
    model: dict
    input: dict
    output_stem: str
    transcript_path: str | None = None
    stats_path: str | None = None
