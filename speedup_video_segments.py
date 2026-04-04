#!/usr/bin/env python3
"""
Build an ffmpeg -filter_complex graph from a list of segment dicts and print
the full ffmpeg command (or optionally run it).

Input/output paths and segments default to ``INPUT_VIDEO``, ``OUTPUT_VIDEO``,
``SEGMENTS``, and ``AUDIO_VOLUME`` (final mix gain) in ``config.py``.

Each segment dict uses:
  end_time — seconds (float) where this segment ends on the source timeline; use
    ``null`` / ``None`` for the last segment to mean “through end of file”.
    Segments are ordered; the first starts at 0, each later one starts where the
    previous ended.
  speedup_factor — playback speed multiplier (e.g. 1.25, 4.0, 5.0)
  mute — optional bool (default False); if True, that segment’s audio is silent after processing.

Video: after trim, setpts=PTS/speedup_factor (same idea as your example).
Audio: atempo chain so the product equals speedup_factor (each atempo in (0.5, 2.0]).
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from config import AUDIO_VOLUME, INPUT_VIDEO, OUTPUT_VIDEO, SEGMENTS


def ffprobe_duration_seconds(path: Path) -> float:
    """Return container duration in seconds (float)."""
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(r.stdout.strip())


def atempo_chain(factor: float) -> list[float]:
    """
    Decompose speedup into ffmpeg atempo factors, each in (0.5, 2.0].
    Product of returned values equals `factor`.
    """
    if factor <= 0:
        raise ValueError(f"speedup_factor must be positive, got {factor}")
    parts: list[float] = []
    x = float(factor)
    while x > 2.0 + 1e-9:
        parts.append(2.0)
        x /= 2.0
    while x < 0.5 - 1e-9:
        parts.append(0.5)
        x /= 0.5
    parts.append(x)
    return parts


def normalize_segments(
    raw: list[dict[str, Any]], duration: float
) -> list[tuple[float, float, float, bool]]:
    """Return list of (start, end, speed, mute). Starts at 0; each segment ends at end_time."""
    out: list[tuple[float, float, float, bool]] = []
    cursor = 0.0
    for i, seg in enumerate(raw):
        try:
            speed = float(seg["speedup_factor"])
        except KeyError as e:
            raise KeyError(f"segment {i}: missing required key {e}") from e
        mute = bool(seg.get("mute", False))
        end_val = seg.get("end_time", None)
        if end_val is None:
            end = duration
        else:
            end = float(end_val)
            if end < cursor - 1e-9:
                raise ValueError(
                    f"segment {i}: end_time {end} is before current position "
                    f"{cursor:.6g}; end times must be non-decreasing."
                )
        start = max(0.0, min(cursor, duration))
        end = max(start, min(end, duration))
        if end <= start:
            continue
        out.append((start, end, speed, mute))
        cursor = end
    return out


def build_filter_complex(
    segments: list[tuple[float, float, float, bool]],
    n: int,
    *,
    audio_volume: float = 1.0,
) -> tuple[str, str]:
    """Build filter_complex and the final audio pad label to map (after concat, optional volume)."""
    if n < 1:
        raise ValueError("Need at least one non-empty segment.")

    v_labels = [f"v{i+1}" for i in range(n)]
    a_labels = [f"a{i+1}" for i in range(n)]
    v_out = [f"v{i+1}out" for i in range(n)]
    a_out = [f"a{i+1}out" for i in range(n)]

    parts: list[str] = []

    split_v = f"[0:v]split={n}" + "".join(f"[{lbl}]" for lbl in v_labels)
    split_a = f"[0:a]asplit={n}" + "".join(f"[{lbl}]" for lbl in a_labels)
    parts.append(split_v)
    parts.append(split_a)

    for (start, end, speed, mute), vin, ain, vout, aout in zip(
        segments, v_labels, a_labels, v_out, a_out
    ):
        # Video: trim → reset PTS → apply speed (setpts = PTS / speed)
        v_chain = (
            f"[{vin}]trim={start}:{end},setpts=PTS-STARTPTS,setpts=PTS/{speed}[{vout}]"
        )
        tempos = atempo_chain(speed)
        atempo_str = ",".join(f"atempo={t:g}" for t in tempos)
        if mute:
            a_chain = (
                f"[{ain}]atrim={start}:{end},asetpts=PTS-STARTPTS,{atempo_str},"
                f"volume=0[{aout}]"
            )
        else:
            a_chain = (
                f"[{ain}]atrim={start}:{end},asetpts=PTS-STARTPTS,{atempo_str}[{aout}]"
            )
        parts.append(v_chain)
        parts.append(a_chain)

    concat_inputs = "".join(f"[{vo}][{ao}]" for vo, ao in zip(v_out, a_out))
    parts.append(
        f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"
    )

    audio_label = "outa"
    if abs(float(audio_volume) - 1.0) > 1e-9:
        parts.append(f"[outa]volume={float(audio_volume):g}[outa_vol]")
        audio_label = "outa_vol"

    return ";".join(parts), audio_label


def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    segments: list[tuple[float, float, float, bool]],
    *,
    audio_volume: float = 1.0,
    extra_ffmpeg_args: list[str] | None = None,
) -> str:
    n = len(segments)
    fc, a_label = build_filter_complex(segments, n, audio_volume=audio_volume)
    extra = extra_ffmpeg_args or []
    cmd_parts = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-filter_complex",
        fc,
        "-map",
        "[outv]",
        "-map",
        f"[{a_label}]",
        *extra,
        str(output_path),
    ]
    return " ".join(shlex.quote(p) for p in cmd_parts)


def parse_segments_json(s: str) -> list[dict[str, Any]]:
    data = json.loads(s)
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of objects")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print ffmpeg command for speedup segments (filter_complex)."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path(INPUT_VIDEO),
        help="Input file path (default: INPUT_VIDEO in config.py).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(OUTPUT_VIDEO),
        help="Output file path (default: OUTPUT_VIDEO in config.py).",
    )
    parser.add_argument(
        "--segments-json",
        type=str,
        default=None,
        help="JSON array of segment dicts (overrides SEGMENTS in config.py).",
    )
    parser.add_argument(
        "--probe-input",
        type=Path,
        default=None,
        help=(
            "Run ffprobe on this file to get duration for end_time=None and clamping. "
            "If omitted, uses --input when it exists, else duration must be set via "
            "--duration."
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Override video duration in seconds (when input not probed).",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute ffmpeg instead of only printing the command.",
    )
    args = parser.parse_args()

    if args.segments_json:
        raw_segments = parse_segments_json(args.segments_json)
    else:
        raw_segments = SEGMENTS

    probe_path = args.probe_input or args.input
    duration: float
    if args.duration is not None:
        duration = args.duration
    elif probe_path.is_file():
        duration = ffprobe_duration_seconds(probe_path)
    else:
        print(
            "Error: need --duration, or an existing file at --input / --probe-input "
            "to resolve end_time=None and clamp segment ends.",
            file=sys.stderr,
        )
        return 1

    segs = normalize_segments(raw_segments, duration)
    if not segs:
        print("Error: no valid segments after normalization.", file=sys.stderr)
        return 1

    cmd_str = build_ffmpeg_command(
        args.input, args.output, segs, audio_volume=AUDIO_VOLUME
    )
    print(cmd_str)

    if args.run:
        # Rebuild argv without shell — execute directly
        n = len(segs)
        fc, a_label = build_filter_complex(segs, n, audio_volume=AUDIO_VOLUME)
        argv = [
            "ffmpeg",
            "-y",
            "-i",
            str(args.input),
            "-filter_complex",
            fc,
            "-map",
            "[outv]",
            "-map",
            f"[{a_label}]",
            str(args.output),
        ]
        print("--- running ---", file=sys.stderr)
        r = subprocess.run(argv)
        return r.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
