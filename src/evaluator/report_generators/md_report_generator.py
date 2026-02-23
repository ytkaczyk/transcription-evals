"""
Module for generating Markdown reports from evaluation outputs.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional, cast

import pandas as pd

from utils.audio_metadata_extractor import AudioMetadataExtractor

logger = logging.getLogger(__name__)


class MdReportGenerator:
    """Generates Markdown reports from evaluation outputs."""

    async def generate(
        self,
        config_path: str,
        outputs_dir: str,
        eval_dir: str,
    ) -> None:
        """
        Generates a Markdown report from JSON output files.

        Args:
            config_path: Path to the configuration file used for the evaluation.
            outputs_dir: Directory containing the JSON output files.
            eval_dir: Directory where the evaluation report should be saved.
        """
        config_path_obj = Path(config_path)
        output_path_obj = Path(outputs_dir)
        eval_path_obj = Path(eval_dir)

        # Enumerate JSON files
        json_files = sorted(output_path_obj.glob("*.json"))
        if not json_files:
            logger.warning(
                f"No JSON output files found in {outputs_dir}. Cannot generate report.")
            return

        data: List[Dict] = []

        # Define column order
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

        # Read all JSON files
        for json_file in json_files:
            try:
                item = await asyncio.to_thread(self._read_json_file, json_file)
                if item:
                    row = {col: item.get(col) for col in columns}
                    data.append(row)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON file: {json_file}")
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")

        if not data:
            logger.warning(
                "No data loaded from JSON files. Cannot generate report.")
            return

        df = pd.DataFrame(data, columns=columns)

        # Determine report filename
        report_filename = f"{config_path_obj.stem}-report.md"
        report_path = eval_path_obj / report_filename

        try:
            # Load config
            config = await asyncio.to_thread(self._read_json_file, config_path_obj)

            # Resolve inputs_dir relative to config file location
            inputs_dir_raw = config.get("paths", {}).get(
                "inputs", "") if config else ""
            if inputs_dir_raw:
                inputs_dir_path = Path(inputs_dir_raw)
                # If relative path, resolve it relative to config file's directory
                if not inputs_dir_path.is_absolute():
                    inputs_dir_resolved = str(
                        config_path_obj.parent / inputs_dir_path)
                else:
                    inputs_dir_resolved = inputs_dir_raw
            else:
                inputs_dir_resolved = ""

            # Build report sections
            report_content = self._build_report(
                config_path=str(config_path_obj),
                df=df,
                inputs_dir=inputs_dir_resolved
            )

            # Write report
            await asyncio.to_thread(
                self._write_report,
                report_path,
                report_content
            )
            logger.info(
                f"Successfully generated Markdown report: {report_path}")

        except Exception as e:
            logger.error(f"Failed to generate Markdown report: {e}")

    @staticmethod
    def _read_json_file(json_file: Path) -> dict | None:
        """Read and return JSON file contents."""
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _write_report(report_path: Path, content: str) -> None:
        """Write report content to file."""
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _build_report(
        self,
        config_path: str,
        df: pd.DataFrame,
        inputs_dir: str
    ) -> str:
        """Build the complete Markdown report content."""
        sections = []

        # Header
        sections.append("# Transcription Evals\n")
        sections.append(f"* **Config file**: `{config_path}`\n")

        # Inputs section
        sections.append("## Inputs\n")
        sections.append(self._build_inputs_table(df, inputs_dir))

        # Evals section - one per model
        sections.append("\n## Evals\n")
        model_groups = df.groupby(['model_name', 'model_label'], dropna=False)
        for group_key, group_df in model_groups:
            # Cast to appropriate types - group_key is a tuple (model_name, model_label)
            model_name_val, model_label_val = group_key  # type: ignore[misc]
            model_name_str = str(
                model_name_val) if model_name_val is not None else "Unknown"
            # Convert to string and check for pandas NA/NaN values
            model_label_temp = str(
                model_label_val) if model_label_val is not None else ""
            model_label_str = (
                model_label_temp
                if model_label_temp and model_label_temp.lower() != "nan"
                else None
            )
            sections.append(self._build_model_eval_table(
                model_name_str, model_label_str, group_df))

        # Summary section
        sections.append("\n## Summary\n")
        sections.append(self._build_summary_table(df))

        return "\n".join(sections)

    def _build_inputs_table(self, df: pd.DataFrame, inputs_dir: str) -> str:
        """Build the Inputs HTML table."""
        # Get unique audio files by selecting only the audio_file_name column.
        # We deduplicate on audio_file_name alone because:
        # 1. audio_file_name uniquely identifies each input audio file
        # 2. audio_file_duration may differ slightly between models due to
        #    different extraction/processing methods, but the actual audio file is identical
        # 3. reference_file and reference_text are the same for a given audio file
        #    across all model evaluations
        unique_audio_df = df[['audio_file_name']].drop_duplicates()

        # Resolve inputs directory
        inputs_path = Path(inputs_dir) if inputs_dir else None

        rows = []
        # Convert to records for type-safe iteration
        # to_dict(orient='records') returns a list of dictionaries, one per row
        records: List[Any] = unique_audio_df.to_dict(
            orient='records')  # type: ignore[attr-defined]
        for record in records:
            # Extract audio filename from record
            audio_file = str(record['audio_file_name'])

            # Get reference_file and reference_text from the first row with this audio_file
            # (they should be identical across all models for the same audio file)
            audio_rows = df[df['audio_file_name'] == audio_file]
            if len(audio_rows) > 0:
                reference_file = str(audio_rows.iloc[0]['reference_file'])
                reference_text_val = audio_rows.iloc[0]['reference_text']
                reference_text = str(reference_text_val) if pd.notna(
                    reference_text_val) else ""
            else:
                reference_file = ""
                reference_text = ""

            # Get audio metadata (including duration from the audio file)
            metadata = AudioMetadataExtractor.get_audio_metadata(
                inputs_path / audio_file if inputs_path else None)

            # Format duration as HH:MM:SS (extracted from audio metadata)
            duration_str = AudioMetadataExtractor.format_duration(
                cast(float, metadata['duration']))

            # Count words in reference text
            word_count = len(reference_text.split()) if reference_text else 0

            rows.append(
                f"    <tr>\n"
                f"      <td>{audio_file}</td>\n"
                f"      <td>{metadata['encoding']}</td>\n"
                f"      <td>{metadata['sampling_rate']}</td>\n"
                f"      <td>{metadata['channels']}</td>\n"
                f"      <td>{duration_str}</td>\n"
                f"      <td>{reference_file}</td>\n"
                f"      <td>{word_count} words</td>\n"
                f"    </tr>"
            )

        table = (
            "<table>\n"
            "  <thead>\n"
            "    <tr>\n"
            "      <th colspan=\"5\">Audio</th>\n"
            "      <th colspan=\"2\">Transcript</th>\n"
            "    </tr>\n"
            "    <tr>\n"
            "      <th>File</th>\n"
            "      <th>Encoding</th>\n"
            "      <th>Sampling</th>\n"
            "      <th>Channels</th>\n"
            "      <th>Duration</th>\n"
            "      <th>File</th>\n"
            "      <th>Length</th>\n"
            "    </tr>\n"
            "  </thead>\n"
            "  <tbody>\n"
            + "\n".join(rows) + "\n"
            "  </tbody>\n"
            "</table>"
        )

        return table

    def _build_model_eval_table(
        self,
        model_name: str,
        model_label: Optional[str],
        df: pd.DataFrame
    ) -> str:
        """Build the per-model Evals HTML table."""
        # Create header with model label if present
        if model_label:
            header = f"### {model_name} ({model_label})\n"
        else:
            header = f"### {model_name}\n"

        # Build table rows
        rows = []
        # Convert to records for type-safe iteration
        for record in df.to_dict('records'):
            rows.append(
                f"    <tr>\n"
                f"      <td>{str(record['audio_file_name'])}</td>\n"
                f"      <td>{float(record['wer']):.1%}</td>\n"
                f"      <td>{float(record['mer']):.1%}</td>\n"
                f"      <td>{float(record['wil']):.1%}</td>\n"
                f"      <td>{float(record['cer']):.1%}</td>\n"
                f"      <td>{float(record['normalized_wer']):.1%}</td>\n"
                f"      <td>{float(record['normalized_mer']):.1%}</td>\n"
                f"      <td>{float(record['normalized_wil']):.1%}</td>\n"
                f"      <td>{float(record['normalized_cer']):.1%}</td>\n"
                f"    </tr>"
            )

        table = (
            "<table>\n"
            "  <thead>\n"
            "    <tr>\n"
            "      <th rowspan=\"2\">Audio File</th>\n"
            "      <th colspan=\"4\">WER</th>\n"
            "      <th colspan=\"4\">Normalized WER</th>\n"
            "    </tr>\n"
            "    <tr>\n"
            "      <th>WER</th>\n"
            "      <th>MER</th>\n"
            "      <th>WIL</th>\n"
            "      <th>CER</th>\n"
            "      <th>WER</th>\n"
            "      <th>MER</th>\n"
            "      <th>WIL</th>\n"
            "      <th>CER</th>\n"
            "    </tr>\n"
            "  </thead>\n"
            "  <tbody>\n"
            + "\n".join(rows) + "\n"
            "  </tbody>\n"
            "</table>\n"
        )

        return header + table

    def _build_summary_table(self, df: pd.DataFrame) -> str:
        """Build the Summary HTML table with aggregated statistics."""
        # Group by model
        grouped = df.groupby(['model_name', 'model_label'], dropna=False)

        # Calculate statistics for WER and Normalized WER
        stats = grouped.agg({
            'wer': ['mean', 'min', 'max', 'std'],
            'normalized_wer': ['mean', 'min', 'max', 'std']
        }).reset_index()

        # Build table rows
        rows = []
        # Iterate through rows using index
        for idx in stats.index:
            model_name = str(stats.loc[idx, 'model_name'])
            model_label_val = stats.loc[idx, 'model_label']
            model_label = str(model_label_val) if pd.notna(
                model_label_val) else ""

            # Extract statistics values using cast for pandas Scalar type
            wer_mean = cast(float, stats.loc[idx, ('wer', 'mean')])
            wer_min = cast(float, stats.loc[idx, ('wer', 'min')])
            wer_max = cast(float, stats.loc[idx, ('wer', 'max')])
            wer_std = cast(float, stats.loc[idx, ('wer', 'std')])
            norm_wer_mean = cast(
                float, stats.loc[idx, ('normalized_wer', 'mean')])
            norm_wer_min = cast(
                float, stats.loc[idx, ('normalized_wer', 'min')])
            norm_wer_max = cast(
                float, stats.loc[idx, ('normalized_wer', 'max')])
            norm_wer_std = cast(
                float, stats.loc[idx, ('normalized_wer', 'std')])

            rows.append(
                f"    <tr>\n"
                f"      <td>{model_name}</td>\n"
                f"      <td>{model_label}</td>\n"
                f"      <td>{wer_mean:.1%}</td>\n"
                f"      <td>{wer_min:.1%}</td>\n"
                f"      <td>{wer_max:.1%}</td>\n"
                f"      <td>{wer_std:.1%}</td>\n"
                f"      <td>{norm_wer_mean:.1%}</td>\n"
                f"      <td>{norm_wer_min:.1%}</td>\n"
                f"      <td>{norm_wer_max:.1%}</td>\n"
                f"      <td>{norm_wer_std:.1%}</td>\n"
                f"    </tr>"
            )

        table = (
            "<table>\n"
            "  <thead>\n"
            "    <tr>\n"
            "      <th rowspan=\"2\">Model</th>\n"
            "      <th rowspan=\"2\">Label</th>\n"
            "      <th colspan=\"4\">WER</th>\n"
            "      <th colspan=\"4\">Normalized WER</th>\n"
            "    </tr>\n"
            "    <tr>\n"
            "      <th>avg</th>\n"
            "      <th>min</th>\n"
            "      <th>max</th>\n"
            "      <th>std</th>\n"
            "      <th>avg</th>\n"
            "      <th>min</th>\n"
            "      <th>max</th>\n"
            "      <th>std</th>\n"
            "    </tr>\n"
            "  </thead>\n"
            "  <tbody>\n"
            + "\n".join(rows) + "\n"
            "  </tbody>\n"
            "</table>"
        )

        return table


async def generate_md_report(
    config_path: str,
    outputs_dir: str,
    eval_dir: str,
) -> None:
    """
    Generates a Markdown report from JSON output files.

    Args:
        config_path: Path to the configuration file used for the evaluation.
        outputs_dir: Directory containing the JSON output files.
        eval_dir: Directory where the evaluation report should be saved.
    """
    generator = MdReportGenerator()
    await generator.generate(config_path, outputs_dir, eval_dir)
