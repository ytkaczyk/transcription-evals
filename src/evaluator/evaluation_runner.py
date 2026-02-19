"""
Evaluator module that handles the core logic of the audio model evaluation process.
"""
import asyncio
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import List

import jiwer
import jiwer.transforms
from report_generator import generate_excel_report
from transcribers.transcriber_factory import TranscriberFactory
from evaluation_runner_types import EvaluationContext, GlobalContext

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """
    Orchestrates the evaluation process for audio transcription models.
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, global_context: GlobalContext):
        self.global_context = global_context

    async def run(self):
        """
        Runs the evaluation loop: Model -> Input -> Transcribe -> Save.
        """
        models = self.global_context.config.get("models", [])
        inputs = self.global_context.config.get("inputs", [])

        for model_config in models:
            model_name = model_config.get("name")
            if not model_name:
                continue

            label = model_config.get("label", None)

            # Create transcriber for each model
            try:
                transcriber = TranscriberFactory.get_transcriber(model_name)
            except ValueError as e:
                logger.error(e)
                continue

            for input_item in inputs:
                audio_file = input_item.get("audio")
                if not audio_file:
                    continue

                output_stem = self._generate_output_stem(
                    model_name, label, audio_file
                )

                evaluation_context = EvaluationContext(
                    model=model_config,
                    input=input_item,
                    output_stem=output_stem,
                )

                transcript_path = await asyncio.to_thread(
                    self._transcribe_audio_file, transcriber, evaluation_context
                )

                evaluation_context.transcript_path = transcript_path

                logger.info(
                    "Transcript saved to: %s", evaluation_context.transcript_path
                )

                stats_path = await asyncio.to_thread(
                    self._compute_stats, evaluation_context
                )

                evaluation_context.stats_path = stats_path

        await asyncio.to_thread(
            generate_excel_report,
            config_path=self.global_context.args.config_file,
            outputs_dir=self.global_context.paths.outputs_dir,
            eval_dir=self.global_context.paths.eval_dir,
            template_path=self.global_context.paths.excel_report_template,
        )

    def _generate_output_stem(
        self, model_name: str, label: str | None, audio_file: str
    ) -> str:
        input_stem = Path(audio_file).stem
        if label:
            return f"{model_name}-{label}-{input_stem}"
        return f"{model_name}-{input_stem}"

    def _generate_stats_filename(self, output_stem: str) -> str:
        return f"{output_stem}-stats.json"

    def _generate_transcript_filename(self, output_stem: str) -> str:
        return f"{output_stem}-transcript.json"

    def _generate_single_string(self, text: List[List[str]]) -> str:
        return " ".join([" ".join(word) for word in text])

    def _transcribe_audio_file(
        self, transcriber, evaluation_context: EvaluationContext
    ) -> str:
        # Generate output file name and path and skip the process if the file exists and lazy_transcription is True
        output_stem = evaluation_context.output_stem
        model_config = evaluation_context.model
        input_item = evaluation_context.input

        transcript_filename = self._generate_transcript_filename(output_stem)
        transcript_path = self._validate_safe_path(
            self.global_context.paths.intermediate_dir, transcript_filename
        )

        if (
            self.global_context.args.lazy_transcription
            and os.path.exists(transcript_path)
        ):
            logger.info(
                "Lazy transcription: Output file %s already exists. Skipping.",
                transcript_filename,
            )
            return transcript_path

        audio_file = input_item.get("audio")
        if not audio_file:
            raise ValueError("Input item missing required 'audio' field.")

        logger.info(
            "Transcribing %s with %s (Label: %s) -> %s",
            audio_file,
            model_config.get("name"),
            model_config.get("label"),
            transcript_filename,
        )

        try:
            # Validate paths to prevent traversal
            audio_full_path = self._validate_safe_path(
                self.global_context.paths.inputs_dir, audio_file
            )

            # Check input
            if not os.path.exists(audio_full_path):
                raise FileNotFoundError(
                    f"Input file not found: {audio_full_path}")

            # Transcribe
            transcript_result = transcriber.transcribe(
                audio_full_path, options=model_config.get("options", {})
            )

            # Save
            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(asdict(transcript_result), f,
                          indent=2, ensure_ascii=False)

            return transcript_path

        except ValueError as ve:
            logger.error("Validation error for %s: %s", audio_file, ve)
            raise
        except Exception as e:
            logger.error("Error transcribing %s: %s", audio_file, e)
            raise

    def _get_text_from_transcript_json(self, file_path: str) -> str:
        """Reads a TranscriptResult JSON and returns the full text."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return " ".join(
                [item.get("content", "")
                 for item in data.get("conversation", [])]
            )

    def _load_reference_text(
        self, input_item: dict
    ) -> tuple[str | None, str | None]:
        """Loads the reference text from the input item. Returns text and filename."""
        ref_filename = input_item.get("transcript")
        if not ref_filename:
            logger.warning(
                "No reference transcript found for %s", input_item.get("audio")
            )
            return None, None

        try:
            ref_path = self._validate_safe_path(
                self.global_context.paths.inputs_dir, ref_filename
            )
            return self._get_text_from_transcript_json(ref_path), ref_filename
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to read reference transcript %s: %s", ref_filename, e
            )
            return None, ref_filename

    def _load_hypothesis_data(self, transcript_path: str) -> tuple[str, float]:
        """Loads hypothesis text and duration from the transcript file."""
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                hypothesis_data = json.load(f)

            hypothesis_text = " ".join(
                [item.get("content", "")
                 for item in hypothesis_data.get("conversation", [])]
            )
            hypothesis_duration = hypothesis_data.get("duration", 0.0)
            return hypothesis_text, hypothesis_duration
        except Exception as e:
            raise ValueError(
                f"Failed to read hypothesis transcript {transcript_path}: {e}"
            ) from e

    def _compute_stats(self, evaluation_context: EvaluationContext) -> str:
        """
        Computes WER and CER using JiWER and saves the result to <output_stem>-stats.json
        """
        if not evaluation_context.transcript_path:
            raise ValueError(
                "No transcript path provided for stats computation")

        # Load hypothesis
        hypothesis_text, hypothesis_duration = self._load_hypothesis_data(
            evaluation_context.transcript_path
        )

        # Load reference
        reference_text, ref_filename = self._load_reference_text(
            evaluation_context.input
        )
        if not reference_text:
            raise ValueError(
                f"Failed to load reference text from {evaluation_context.input}"
            )

        # Compute stats
        try:
            stats_path = self._validate_safe_path(
                self.global_context.paths.outputs_dir,
                self._generate_stats_filename(evaluation_context.output_stem),
            )

            word_output = jiwer.process_words(reference_text, hypothesis_text)

            character_output = jiwer.process_characters(
                reference_text, hypothesis_text)

            # This is similar to the standard wer_standardize_contiguous transformation, but also removes punctuation.
            # This is useful to get a more normalized WER/CER that is less sensitive to punctuation differences.
            wer_standardize_nopunctuation_contiguous = jiwer.transforms.Compose(
                [
                    jiwer.transforms.ToLowerCase(),
                    jiwer.transforms.ExpandCommonEnglishContractions(),
                    jiwer.transforms.RemoveKaldiNonWords(),
                    jiwer.transforms.RemoveWhiteSpace(replace_by_space=True),
                    jiwer.transforms.RemoveMultipleSpaces(),
                    jiwer.transforms.RemovePunctuation(),
                    jiwer.transforms.Strip(),
                    jiwer.transforms.ReduceToSingleSentence(),
                    jiwer.transforms.ReduceToListOfListOfWords(),
                ]
            )

            normalized_word_output = jiwer.process_words(
                reference_text,
                hypothesis_text,
                wer_standardize_nopunctuation_contiguous,
                wer_standardize_nopunctuation_contiguous,
            )

            normalized_character_output = jiwer.process_characters(
                reference_text,
                hypothesis_text,
                wer_standardize_nopunctuation_contiguous,
                wer_standardize_nopunctuation_contiguous,
            )

            stats = {
                "audio_file_name": os.path.basename(evaluation_context.input.get("audio", "")),
                "audio_file_duration": hypothesis_duration,
                "model_name": evaluation_context.model.get("name"),
                "model_label": evaluation_context.model.get("label"),
                "wer": word_output.wer,
                "mer": word_output.mer,
                "wil": word_output.wil,
                "cer": character_output.cer,
                "normalized_wer": normalized_word_output.wer,
                "normalized_mer": normalized_word_output.mer,
                "normalized_wil": normalized_word_output.wil,
                "normalized_cer": normalized_character_output.cer,
                "reference_file": ref_filename,
                "reference_text": reference_text,
                "normalized_reference_text": self._generate_single_string(
                    normalized_word_output.references
                ),
                "hypothesis_file": os.path.basename(
                    evaluation_context.transcript_path
                ),
                "hypothesis_text": hypothesis_text,
                "normalized_hypothesis_text": self._generate_single_string(
                    normalized_word_output.hypotheses
                ),
            }

            with open(stats_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)

            logger.info("Stats saved to: %s", stats_path)
            return stats_path

        except Exception as e:
            logger.error(
                "Error computing stats for %s: %s",
                evaluation_context.transcript_path,
                e,
            )
            raise

    def _validate_safe_path(self, base_dir: str, file_path: str) -> str:
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
