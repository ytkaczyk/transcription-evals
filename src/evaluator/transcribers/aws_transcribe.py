"""
AWS Transcribe Standard transcription implementation.
"""
import os
import json
import time
import uuid
import logging
import urllib.request
from typing import List, Optional, Dict, Any

import boto3

from .abstract_transcriber import AbstractTranscriber
from .types import TranscriptResult, ConversationItem

logger = logging.getLogger(__name__)


class AWSTranscribeTranscriber(AbstractTranscriber):
    """
    Transcriber implementation using AWS Transcribe Standard transcription service.

    Requires the following environment variables (or constructor arguments):
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
        - AWS_DEFAULT_REGION
        - AWS_S3_BUCKET  (S3 bucket used to stage audio files before transcription)

    The transcription workflow:
        1. Upload the audio file to S3.
        2. Start an AWS Transcribe Standard job with speaker diarization enabled.
        3. Poll until the job completes (or fails).
        4. Download and parse the transcript JSON.
        5. Clean up the S3 object and the Transcribe job.
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        s3_bucket: Optional[str] = None,
    ):
        self.aws_access_key_id = aws_access_key_id or os.getenv(
            "AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY")
        self.aws_region = aws_region or os.getenv("AWS_DEFAULT_REGION")
        self.s3_bucket = s3_bucket or os.getenv("AWS_S3_BUCKET")

        if not self.aws_access_key_id:
            raise ValueError(
                "AWS access key ID is required. Set AWS_ACCESS_KEY_ID environment variable "
                "or pass it to the constructor."
            )
        if not self.aws_secret_access_key:
            raise ValueError(
                "AWS secret access key is required. Set AWS_SECRET_ACCESS_KEY environment variable "
                "or pass it to the constructor."
            )
        if not self.aws_region:
            raise ValueError(
                "AWS region is required. Set AWS_DEFAULT_REGION environment variable "
                "or pass it to the constructor."
            )
        if not self.s3_bucket:
            raise ValueError(
                "AWS S3 bucket is required. Set AWS_S3_BUCKET environment variable "
                "or pass it to the constructor."
            )

        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region,
        )
        self.transcribe_client = boto3.client(
            "transcribe",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region,
        )

    @property
    def name(self) -> str:
        return "AWS Transcribe"

    def _format_timestamp(self, start_time: float) -> str:
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        seconds = int(start_time % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _build_speaker_lookup(
        self, speaker_labels_data: Optional[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Build a start_time → speaker_label mapping from the speaker_labels block."""
        lookup: Dict[str, str] = {}
        if not speaker_labels_data:
            return lookup
        for segment in speaker_labels_data.get("segments", []):
            label = segment.get("speaker_label", "Unknown")
            for seg_item in segment.get("items", []):
                if "start_time" in seg_item:
                    lookup[seg_item["start_time"]] = label
        return lookup

    def _resolve_speaker_display(
        self,
        speaker_lookup: Dict[str, str],
        start_time_str: str,
        has_speaker_labels: bool,
    ) -> str:
        """Return a human-readable speaker label such as 'Speaker 0'."""
        if not has_speaker_labels:
            return "Unknown"
        raw = speaker_lookup.get(start_time_str, "spk_0")
        return f"Speaker {raw.split('_')[-1]}" if "_" in raw else raw

    def _poll_until_complete(self, job_name: str) -> Dict[str, Any]:
        """Poll AWS Transcribe until the job reaches COMPLETED or FAILED."""
        while True:
            response = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            job = response["TranscriptionJob"]
            status = job["TranscriptionJobStatus"]

            if status == "COMPLETED":
                return job
            if status == "FAILED":
                failure_reason = job.get("FailureReason", "Unknown reason")
                error_msg = f"AWS Transcribe job failed: {failure_reason}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.debug("Job %s status: %s. Waiting…", job_name, status)
            time.sleep(5)

    def _download_transcript_json(self, transcript_uri: str) -> Dict[str, Any]:
        """Fetch and decode the transcript JSON from the given URI."""
        logger.info("Downloading transcript from: %s", transcript_uri)
        with urllib.request.urlopen(transcript_uri) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_transcript(self, transcript_json: Dict[str, Any]) -> List[ConversationItem]:
        """
        Parse the AWS Transcribe JSON output into a list of ConversationItems.

        Consecutive pronunciation items from the same speaker are merged into a
        single ConversationItem. Punctuation items are appended to the preceding
        word without an additional space.
        """
        results = transcript_json.get("results", {})
        items = results.get("items", [])
        if not items:
            return []

        speaker_lookup = self._build_speaker_lookup(
            results.get("speaker_labels"))
        has_speakers = bool(speaker_lookup)

        conversation: List[ConversationItem] = []
        cur_speaker: Optional[str] = None
        cur_start: Optional[float] = None
        cur_words: List[str] = []

        for item in items:
            item_type = item.get("type")
            content = item.get("alternatives", [{}])[0].get("content", "")

            if item_type == "punctuation":
                if cur_words:
                    cur_words[-1] += content
                continue

            if item_type != "pronunciation":
                continue

            start_str = item.get("start_time", "0")
            speaker = self._resolve_speaker_display(
                speaker_lookup, start_str, has_speakers)

            if speaker != cur_speaker:
                if cur_words and cur_speaker is not None:
                    conversation.append(ConversationItem(
                        timestamp=self._format_timestamp(cur_start or 0.0),
                        person=cur_speaker,
                        content=" ".join(cur_words),
                    ))
                cur_speaker = speaker
                cur_start = float(start_str) if start_str else 0.0
                cur_words = [content]
            else:
                cur_words.append(content)

        if cur_words and cur_speaker is not None:
            conversation.append(ConversationItem(
                timestamp=self._format_timestamp(cur_start or 0.0),
                person=cur_speaker,
                content=" ".join(cur_words),
            ))

        return conversation

    def transcribe_sync(
        self, audio_file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> TranscriptResult:
        """Synchronous transcription. Called from worker threads or via the base-class async wrapper."""
        job_name = f"transcription-eval-{uuid.uuid4().hex}"
        s3_key = f"transcription-evals/{job_name}/{os.path.basename(audio_file_path)}"
        s3_uploaded = False
        job_started = False

        try:
            # 1. Upload audio to S3 --------------------------------------------------
            logger.info("Uploading audio to s3://%s/%s",
                        self.s3_bucket, s3_key)
            self.s3_client.upload_file(audio_file_path, self.s3_bucket, s3_key)
            s3_uploaded = True

            # 2. Start the transcription job -----------------------------------------
            job_params: Dict[str, Any] = {
                "TranscriptionJobName": job_name,
                "Media": {"MediaFileUri": f"s3://{self.s3_bucket}/{s3_key}"},
                "Settings": {"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10},
            }
            if options and "language_code" in options:
                job_params["LanguageCode"] = options["language_code"]
            else:
                job_params["IdentifyLanguage"] = True

            logger.info("Starting AWS Transcribe job: %s", job_name)
            self.transcribe_client.start_transcription_job(**job_params)
            job_started = True

            # 3 & 4. Poll, download, and parse ----------------------------------------
            job = self._poll_until_complete(job_name)
            transcript_json = self._download_transcript_json(
                job["Transcript"]["TranscriptFileUri"]
            )
            conversation_items = self._parse_transcript(transcript_json)

            # Fallback: if diarization produced nothing, use the plain text
            if not conversation_items:
                transcripts = transcript_json.get(
                    "results", {}).get("transcripts", [])
                full_text = " ".join(t.get("transcript", "")
                                     for t in transcripts).strip()
                if full_text:
                    conversation_items.append(ConversationItem(
                        timestamp="00:00:00", person="Unknown", content=full_text,
                    ))

            return TranscriptResult(
                name=self.name,
                conversation=conversation_items,
                raw_output=transcript_json,
            )

        except Exception as e:
            logger.error("Error during AWS Transcribe transcription: %s", e)
            raise

        finally:
            # 5. Cleanup: delete the S3 object and the Transcribe job -----------------
            if s3_uploaded:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.s3_bucket, Key=s3_key)
                    logger.info("Deleted S3 object: s3://%s/%s",
                                self.s3_bucket, s3_key)
                except Exception as cleanup_err:  # pylint: disable=broad-except
                    logger.warning(
                        "Failed to delete S3 object: %s", cleanup_err)

            if job_started:
                try:
                    self.transcribe_client.delete_transcription_job(
                        TranscriptionJobName=job_name
                    )
                    logger.info("Deleted AWS Transcribe job: %s", job_name)
                except Exception as cleanup_err:  # pylint: disable=broad-except
                    logger.warning(
                        "Failed to delete transcription job: %s", cleanup_err)
