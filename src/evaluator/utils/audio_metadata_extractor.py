"""
Module for extracting information from audio files.
"""
import logging
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd
from mutagen._file import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.mp4 import MP4

logger = logging.getLogger(__name__)


class AudioMetadataExtractor:
    """Extracts metadata and information from audio files."""

    @staticmethod
    def get_audio_metadata(audio_path: Optional[Path]) -> Dict[str, Union[str, float]]:
        """
        Extract audio file metadata using mutagen.

        Args:
            audio_path: Path to the audio file, or None

        Returns:
            Dictionary with encoding, sampling_rate, and channels
        """
        if not audio_path or not audio_path.exists():
            return {
                'encoding': 'N/A',
                'sampling_rate': 'N/A',
                'channels': 'N/A',
                'duration': 0.0
            }

        try:
            audio = MutagenFile(audio_path)

            if audio is None:
                return {
                    'encoding': 'Unknown',
                    'sampling_rate': 'Unknown',
                    'channels': 'Unknown',
                    'duration': 0.0
                }

            # Extract metadata based on file type
            if isinstance(audio, MP3):
                encoding = 'MP3'
                sample_rate = getattr(audio.info, 'sample_rate', 0)
                channels = getattr(audio.info, 'channels', 0)
            elif isinstance(audio, WAVE):
                encoding = 'WAV'
                sample_rate = getattr(audio.info, 'sample_rate', 0)
                channels = getattr(audio.info, 'channels', 0)
            elif isinstance(audio, MP4):
                encoding = 'M4A/AAC'
                sample_rate = getattr(audio.info, 'sample_rate', 0)
                channels = getattr(audio.info, 'channels', 0)
            else:
                encoding = 'Unknown'
                sample_rate = getattr(audio.info, 'sample_rate', 0)
                channels = getattr(audio.info, 'channels', 0)

            # Extract duration in seconds
            duration = float(getattr(audio.info, 'length', 0.0))

            # Format sampling rate
            if sample_rate >= 1000:
                sampling_str = f"{sample_rate // 1000} kHz"
            else:
                sampling_str = f"{sample_rate} Hz"

            # Format channels
            if channels == 1:
                channels_str = "1 (mono)"
            elif channels == 2:
                channels_str = "2 (stereo)"
            else:
                channels_str = str(channels)

            return {
                'encoding': encoding,
                'sampling_rate': sampling_str,
                'channels': channels_str,
                'duration': duration
            }

        except Exception as e:
            logger.warning(
                f"Failed to extract metadata from {audio_path}: {e}")
            return {
                'encoding': 'Error',
                'sampling_rate': 'Error',
                'channels': 'Error',
                'duration': 0.0
            }

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to HH:MM:SS.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string as HH:MM:SS
        """
        if pd.isna(seconds):
            return "00:00:00"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
