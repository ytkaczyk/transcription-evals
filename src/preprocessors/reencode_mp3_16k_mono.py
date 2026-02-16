#!/usr/bin/env python3
"""
Re-encode an MP3 to ASR-friendly settings:
- Sample rate: 16 kHz
- Channels: Mono
- Codec: MP3 (libmp3lame)
- Bitrate: configurable, default 64 kbps

By default, writes to the same <filename>.mp3 and overwrites the source.
Use --out to avoid overwriting.

Usage:
  python reencode_mp3_16k_mono.py input.mp3
  python reencode_mp3_16k_mono.py input.mp3 --bitrate 64k
  python reencode_mp3_16k_mono.py input.mp3 --out output.mp3
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def require_ffmpeg() -> None:
    """Ensure ffmpeg is available."""
    if shutil.which("ffmpeg") is None:
        sys.stderr.write(
            "Error: ffmpeg not found in PATH. Please install FFmpeg.\n")
        sys.exit(1)


def reencode_to_mp3_16k_mono(src: Path, dst: Path, bitrate: str = "64k") -> None:
    """
    Re-encode using ffmpeg to 16 kHz mono MP3.

    Args:
        src: input MP3 path
        dst: output MP3 path
        bitrate: target audio bitrate, e.g., '64k', '48k'
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(src),
        "-vn",                 # no video
        "-ac", "1",            # mono
        "-ar", "16000",        # 16 kHz sample rate
        "-c:a", "libmp3lame",  # MP3 codec
        "-b:a", bitrate,       # audio bitrate
        "-map_metadata", "-1",  # strip metadata
        "-y",                  # overwrite output
        str(dst)
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"ffmpeg failed: {e}\n")
        sys.exit(e.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Re-encode MP3 to 16 kHz mono MP3 for ASR.")
    parser.add_argument("source", help="Path to the source MP3 file")
    parser.add_argument("--bitrate", default="64k",
                        help="Target bitrate, e.g., 64k or 48k (default: 64k)")
    parser.add_argument(
        "--out", help="Optional output path. If omitted, defaults to <filename>.16k.mono.mp3.")
    args = parser.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.exists() or not src.is_file():
        sys.stderr.write(f"Source file not found: {src}\n")
        sys.exit(1)

    # Default to overwrite the source file, as requested
    if args.out:
        dst = Path(args.out).expanduser().resolve()
    else:
        # If --out is omitted, derive output filename like filename.16k.mono.mp3
        dst = src.with_name(f"{src.stem}.16k.mono.mp3")

    require_ffmpeg()
    # If overwriting, write to a temporary sibling first, then replace atomically
    if dst == src:
        tmp = src.with_suffix(".tmp.reencode.mp3")
        reencode_to_mp3_16k_mono(src, tmp, bitrate=args.bitrate)
        try:
            tmp.replace(src)
        except Exception as ex:
            sys.stderr.write(f"Failed to replace original file: {ex}\n")
            sys.exit(1)
    else:
        reencode_to_mp3_16k_mono(src, dst, bitrate=args.bitrate)

    print(f"Wrote: {dst}")


if __name__ == "__main__":
    main()
