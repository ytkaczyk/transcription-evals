#!/usr/bin/env python3
"""
Transcript to JSON converter.

Parses a raw transcript that contains timestamps in the form [HH:MM:SS],
and generates a JSON file with structure:

{
  "name": "<filename_stem>",
  "conversation": [
    {"timestamp": "HH:MM:SS", "person": "unknown", "content": "..."},
    ...
  ]
}

Usage:
  python transcript_to_json.py <input_file.txt>
  # Optional flags:
  #   --person "Host"
  #   --encoding "utf-8"

Example:
  python podcast_transcript_to_json.py sample.txt
  -> produces sample.json
"""

import argparse
import json
import re
from pathlib import Path
import html

TIMESTAMP_PATTERN = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]")


def normalize_text(s: str) -> str:
    """Unescape HTML entities, normalize newlines, replace non-standard characters, and collapse whitespace."""
    if not s:
        return ""
    # Convert HTML entities (&nbsp;, &amp;, etc.)
    s = html.unescape(s)

    # Replace non-standard characters
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "..."
    }
    for old, new in replacements.items():
        s = s.replace(old, new)

    # Normalize newlines to spaces and collapse consecutive whitespace
    s = " ".join(s.replace("\r\n", "\n").replace("\r", "\n").split())
    return s.strip()


def parse_conversation(raw: str, default_person: str = "unknown"):
    """
    Parse the transcript into a list of entries with timestamp, person, and content.
    Expects timestamps formatted as [HH:MM:SS].
    """
    conversation = []
    if not raw or not raw.strip():
        return conversation

    # Find all timestamp matches with positions
    matches = list(TIMESTAMP_PATTERN.finditer(raw))
    if not matches:
        # No timestamps found; put entire content as a single entry with empty timestamp
        content = normalize_text(raw)
        if content:
            conversation.append({
                "timestamp": "00:00:00",
                "person": default_person,
                "content": content
            })
        return conversation

    # For each timestamp, capture the text until the next timestamp (or end of file)
    for i, m in enumerate(matches):
        timestamp = m.group(1)
        start_content = m.end()  # first char after the current timestamp
        end_content = matches[i + 1].start() if i + \
            1 < len(matches) else len(raw)
        segment = raw[start_content:end_content]
        content = normalize_text(segment)
        # Include even if empty to preserve positions, but you can skip empties if preferred
        conversation.append({
            "timestamp": timestamp,
            "person": default_person,
            "content": content
        })

    return conversation


def main():
    parser = argparse.ArgumentParser(
        description="Convert a timestamped transcript to JSON.")
    parser.add_argument(
        "input_file", help="Path to the raw transcript text file (e.g., <filename>.txt)")
    parser.add_argument("--person", default="unknown",
                        help='Default person label for all entries (default: "unknown")')
    parser.add_argument("--encoding", default="utf-8",
                        help='File encoding to read input (default: "utf-8")')
    args = parser.parse_args()

    # file: snyk-ignore python/PT
    in_path = Path(args.input_file)
    if not in_path.exists() or not in_path.is_file():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    stem = in_path.stem
    out_path = in_path.with_name(f"{stem}.json")

    with in_path.open("r", encoding=args.encoding) as f:
        raw = f.read()

    conversation = parse_conversation(raw, default_person=args.person)

    data = {
        "name": stem,
        "conversation": conversation
    }

    # Write JSON with UTF-8 and pretty formatting
    with out_path.open("w", encoding="utf-8") as f:
        # file: snyk-ignore python/PT
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
