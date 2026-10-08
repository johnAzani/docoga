#!/usr/bin/env python3
"""Render one safe, date-selected DocOga Short and expose upload metadata."""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_short_video as shorts  # noqa: E402


def main():
    run_date = datetime.now(ZoneInfo("Africa/Lagos")).date()
    script = shorts.script_for_date(run_date)
    output_path = shorts.OUTPUT_DIR / f"docoga_short_{run_date:%Y%m%d}.mp4"
    video_path, _ = shorts.generate_video(script=script, output_path=output_path)

    video = Path(video_path)
    if video.suffix.lower() != ".mp4" or not video.is_file() or video.stat().st_size < 10_000:
        raise RuntimeError(f"Video generation did not produce a usable MP4: {video}")

    outputs = {
        "video_path": str(video),
        "title": f"{script['title']} #Shorts",
        "description": (
            "Practical document-keeping tips for Nigerian tenants and landlords. "
            "General information only; rules vary by state and agreement. "
            "This is not legal advice. More free document tools: "
            "https://docoga.com.ng #Shorts"
        ),
        "tags": "docoga,nigeria,tenant tips,landlord tips,shorts",
    }

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            for key, value in outputs.items():
                output.write(f"{key}={value}\n")
    else:
        for key, value in outputs.items():
            print(f"{key}={value}")

    print(f"Prepared {outputs['title']} ({video.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
