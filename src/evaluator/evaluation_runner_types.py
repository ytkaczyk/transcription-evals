from dataclasses import dataclass


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
