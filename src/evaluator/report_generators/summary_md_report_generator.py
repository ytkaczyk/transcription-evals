"""
Module for generating summary Markdown reports from evaluation outputs.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, cast

import pandas as pd

from utils.audio_metadata_extractor import AudioMetadataExtractor

logger = logging.getLogger(__name__)


class SummaryMdReportGenerator:
    """Generates summary Markdown report content from evaluation outputs."""

    async def generate(
        self,
        config_path: str,
        outputs_dir: str,
    ) -> str:
        """
        Generates a summary Markdown report from JSON output files.

        Args:
            config_path: Path to the configuration file used for the evaluation.
            outputs_dir: Directory containing the JSON output files.

        Returns:
            Summary Markdown report content as a string.
        """
        config_path_obj = Path(config_path)
        output_path_obj = Path(outputs_dir)

        json_files = sorted(output_path_obj.glob("*.json"))
        if not json_files:
            logger.warning(
                "No JSON output files found in %s. Cannot generate summary report.",
                outputs_dir,
            )
            return ""

        data: List[Dict[str, Any]] = []

        columns = [
            "reference_file",
            "model_name",
            "model_label",
            "wer",
            "mer",
            "wil",
            "cer",
            "normalized_wer",
            "normalized_mer",
            "normalized_wil",
            "normalized_cer",
            "audio_file_name",
            "audio_file_duration",
            "reference_text",
        ]

        for json_file in json_files:
            try:
                item = await asyncio.to_thread(self._read_json_file, json_file)
                if item:
                    row = {col: item.get(col) for col in columns}
                    data.append(row)
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON file: %s", json_file)
            except Exception as exc:
                logger.error("Error reading %s: %s", json_file, exc)

        if not data:
            logger.warning(
                "No data loaded from JSON files. Cannot generate summary report."
            )
            return ""

        df = pd.DataFrame(data, columns=columns)

        try:
            config = await asyncio.to_thread(self._read_json_file, config_path_obj)
        except Exception as exc:
            logger.error("Failed to read config file %s: %s", config_path, exc)
            config = None

        inputs_dir_raw = config.get("paths", {}).get(
            "inputs", "") if config else ""
        if inputs_dir_raw:
            inputs_dir_path = Path(inputs_dir_raw)
            if not inputs_dir_path.is_absolute():
                inputs_dir_resolved = str(
                    config_path_obj.parent / inputs_dir_path)
            else:
                inputs_dir_resolved = inputs_dir_raw
        else:
            inputs_dir_resolved = ""

        return self._build_report(df=df, inputs_dir=inputs_dir_resolved)

    @staticmethod
    def _read_json_file(json_file: Path) -> dict | None:
        """Read and return JSON file contents."""
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_report(self, df: pd.DataFrame, inputs_dir: str) -> str:
        """Build the summary Markdown report content."""
        inputs_table = self._build_inputs_table(df, inputs_dir)
        summary_table = self._build_summary_table(df)
        # Minimize newlines to reduce excessive vertical spacing in Rich rendering
        return f"## Inputs\n{inputs_table}\n\n## Result Summary\n{summary_table}"

    def _build_inputs_table(self, df: pd.DataFrame, inputs_dir: str) -> str:
        """Build the Inputs Markdown table."""
        unique_audio = df[["audio_file_name",
                           "reference_text"]].drop_duplicates()

        inputs_path = Path(inputs_dir) if inputs_dir else None

        rows = []
        records = cast(Any, unique_audio.to_dict)("records")
        for record in records:
            audio_file = str(record["audio_file_name"])
            reference_text_val = record["reference_text"]
            reference_text = (
                str(reference_text_val) if pd.notna(reference_text_val) else ""
            )

            metadata = AudioMetadataExtractor.get_audio_metadata(
                inputs_path / audio_file if inputs_path else None
            )
            duration_str = AudioMetadataExtractor.format_duration(
                cast(float, metadata["duration"])
            )
            word_count = len(reference_text.split()) if reference_text else 0

            rows.append(
                "| {audio_file} | {encoding} | {sampling} | {channels} | {duration} | {words} words |".format(
                    audio_file=audio_file,
                    encoding=metadata["encoding"],
                    sampling=metadata["sampling_rate"],
                    channels=metadata["channels"],
                    duration=duration_str,
                    words=word_count,
                )
            )

        table = (
            "| **Audio File** | **Audio encoding** | **Audio Sampling** | **Channels** | **Duration** | **Transcript length** |\n"
            "|:-----------|:---------------:|-----------------:|:---------------:|-----------------:|-----------------:|\n"
            + "\n".join(rows)
        )

        return table

    def _build_summary_table(self, df: pd.DataFrame) -> str:
        """Build the Result Summary Markdown table."""
        grouped = df.groupby(["model_name", "model_label"], dropna=False)

        stats = grouped.agg(
            {
                "wer": ["mean", "min", "max", "std"],
                "normalized_wer": ["mean", "min", "max", "std"],
            }
        ).reset_index()

        rows = []
        for idx in stats.index:
            model_name = str(stats.loc[idx, "model_name"])
            model_label_val = stats.loc[idx, "model_label"]
            model_label = str(model_label_val) if pd.notna(
                model_label_val) else ""

            wer_mean = self._format_percent(stats.loc[idx, ("wer", "mean")])
            wer_min = self._format_percent(stats.loc[idx, ("wer", "min")])
            wer_max = self._format_percent(stats.loc[idx, ("wer", "max")])
            wer_std = self._format_percent(stats.loc[idx, ("wer", "std")])
            norm_wer_mean = self._format_percent(
                stats.loc[idx, ("normalized_wer", "mean")]
            )
            norm_wer_min = self._format_percent(
                stats.loc[idx, ("normalized_wer", "min")]
            )
            norm_wer_max = self._format_percent(
                stats.loc[idx, ("normalized_wer", "max")]
            )
            norm_wer_std = self._format_percent(
                stats.loc[idx, ("normalized_wer", "std")]
            )

            rows.append(
                "| {model_name} | {model_label} | {wer_mean} | {wer_min} | {wer_max} | {wer_std} | {norm_wer_mean} | {norm_wer_min} | {norm_wer_max} | {norm_wer_std} |".format(
                    model_name=model_name,
                    model_label=model_label,
                    wer_mean=wer_mean,
                    wer_min=wer_min,
                    wer_max=wer_max,
                    wer_std=wer_std,
                    norm_wer_mean=norm_wer_mean,
                    norm_wer_min=norm_wer_min,
                    norm_wer_max=norm_wer_max,
                    norm_wer_std=norm_wer_std,
                )
            )

        table = (
            "| Model | Label | WER avg | WER min | WER max | WER std | Norm<br/>WER avg | Norm<br/>WER min | Norm<br/>WER max | Norm<br/>WER std |\n"
            "|:-----|:-----|--------:|--------:|--------:|--------:|--------:|:-------------:|:-------------:|:-------------:|\n"
            + "\n".join(rows)
        )

        return table

    @staticmethod
    def _format_percent(value: Any) -> str:
        """Format a numeric value as a percentage or return N/A."""
        if value is None or pd.isna(value):
            return "N/A"
        return f"{cast(float, value):.1%}"


async def generate_summary_md_report(
    config_path: str,
    outputs_dir: str,
) -> str:
    """
    Generates a summary Markdown report from JSON output files.

    Args:
        config_path: Path to the configuration file used for the evaluation.
        outputs_dir: Directory containing the JSON output files.

    Returns:
        Summary Markdown report content as a string.
    """
    generator = SummaryMdReportGenerator()
    return await generator.generate(config_path, outputs_dir)
