#!/usr/bin/env python3
"""Render one safe, date-selected DocOga Short with MotionStudio and expose upload metadata.

The words come from the date-seeded rotation in `scripts/generate_short_video.py`
(`script_for_date`). The picture comes from `tools/motionstudio.py`, through the
one bridge in `tools/shorts_reel.py` — Inter on #061A33, springs, the yellow
underline, the grain. Nothing else may render a Short that this lane uploads
(docs/BRAND_STYLE.md: "every piece of content follows this or it doesn't ship").
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = SCRIPTS_DIR.parent / "tools"
for _p in (SCRIPTS_DIR, TOOLS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import shorts_reel  # noqa: E402  — MotionStudio bridge (the only renderer this lane knows)
import deepdive_links  # noqa: E402  — which Deep-Dive this Short trails, and its watch link


def describe(script, link=None):
    """The YouTube description for a rotation topic.

    The parent Deep-Dive link comes first — the first two lines are what the
    Shorts player shows under "...more", and the whole point of a Short is to
    send the viewer to the nine-minute episode it was cut from (first stats
    snapshot, 14 Oct 2026: Shorts at 108 views, the long-forms at 0–2)."""
    return (
        deepdive_links.description_block(link)
        + "Practical document-keeping tips for Nigerian tenants and landlords. "
        "General information only; rules vary by state and agreement. "
        "This is not legal advice. More free document tools: "
        "https://docoga.com.ng #Shorts"
    )


def main():
    run_date = datetime.now(ZoneInfo("Africa/Lagos")).date()
    script = shorts_reel.topic_for(run_date)
    output_path = shorts_reel.default_output_path(run_date, prefix="docoga_short")
    video = Path(shorts_reel.render_topic(script, output_path, tag="yt",
                                          platform="YouTube Shorts"))

    if video.suffix.lower() != ".mp4" or not video.is_file() or video.stat().st_size < 10_000:
        raise RuntimeError(f"Video generation did not produce a usable MP4: {video}")

    link = deepdive_links.parent_link(script.get("parent"))
    if script.get("parent") and not link:
        print(f"::notice title=Parent Deep-Dive not published yet::{script['title']} trails "
              f"'{script['parent']}', which is not in logs/youtube_longform.json yet — the "
              "description carries no episode link this time; it appears automatically once "
              "the Deep-Dive lane publishes it.")

    outputs = {
        "video_path": str(video),
        "title": f"{script['title']} #Shorts",
        # The rotation topic without the #Shorts suffix — this is what the
        # publish ledger records, so the ledger reads as plain English.
        "topic": script["title"],
        "description": describe(script, link),
        "tags": "docoga,nigeria,tenant tips,landlord tips,shorts",
        # Posting comments needs youtube.force-ssl, a scope the uploader token
        # does not hold; the run summary shows this line so the owner can pin it
        # from the YouTube app in one paste.
        "pinned_comment": deepdive_links.pinned_comment(link),
        "parent_url": link[1] if link else "",
    }

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            for key, value in outputs.items():
                if "\n" in str(value):
                    output.write(f"{key}<<DOCOGA_EOF\n{value}\nDOCOGA_EOF\n")
                else:
                    output.write(f"{key}={value}\n")
    else:
        for key, value in outputs.items():
            print(f"{key}={value}")

    print(f"Prepared {outputs['title']} ({video.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
