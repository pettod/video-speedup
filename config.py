from __future__ import annotations
from typing import Any

INPUT_VIDEO = "video.mov"


OUTPUT_VIDEO = f"{INPUT_VIDEO.split('.')[0]}_processed.mp4"
AUDIO_VOLUME = 1.0
SEGMENTS: list[dict[str, Any]] = [
    {"end_time": None, "speedup_factor": 1.00, "mute": False},
]
