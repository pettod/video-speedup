from __future__ import annotations
from typing import Any

INPUT_VIDEO = "input.mp4"
OUTPUT_VIDEO = f"speedup_{INPUT_VIDEO}"

SEGMENTS: list[dict[str, Any]] = [
    {
        "start_time": 0,
        "end_time": 10.5,
        "speedup_factor": 1.1,
    },
    {
        "start_time": 10.5,
        "end_time": 35,
        "speedup_factor": 1.17,
    },
    {
        "start_time": 35,
        "end_time": 65,
        "speedup_factor": 5.0,
    },
    {
        "start_time": 65,
        "end_time": None,
        "speedup_factor": 1.17,
    },
]
