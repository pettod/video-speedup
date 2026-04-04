from __future__ import annotations
from typing import Any

INPUT_VIDEO = "input.mp4"
OUTPUT_VIDEO = f"speedup_{INPUT_VIDEO}"

# Each segment: end_time (seconds on the source timeline where this segment ends
SEGMENTS: list[dict[str, Any]] = [
    {"end_time": 10.5, "speedup_factor": 1.1},
    {"end_time": 35, "speedup_factor": 1.17},
    {"end_time": 65, "speedup_factor": 5.0},
    {"end_time": None, "speedup_factor": 1.17},
]
