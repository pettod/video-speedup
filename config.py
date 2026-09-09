from __future__ import annotations
from typing import Any

INPUT_VIDEO = "video.mp4"
OUTPUT_VIDEO = f"{INPUT_VIDEO.split('.')[0]}_processed.mp4"

AUDIO_VOLUME = 1.0
SEGMENTS: list[dict[str, Any]] = [
    {"end_time": 0.6, "speedup_factor": 1.00, "mute": True},
    {"end_time": 10.5, "speedup_factor": 1.00, "mute": False},
    {"end_time": 35, "speedup_factor": 1.17, "mute": False},
    {"end_time": 65, "speedup_factor": 5.0, "mute": True},
    {"end_time": None, "speedup_factor": 1.17, "mute": False},
]
