#!/usr/bin/env python3
"""Render one safe, date-selected DocOga Short with MotionStudio and expose upload metadata.

The words come from the date-seeded rotation in `scripts/generate_short_video.py`
(`script_for_date`). The picture comes from `tools/motionstudio.py`, through the
one bridge in `tools/shorts_reel.py` — Inter on #061A33, springs, the yellow
underline, the grain. Nothing else may render a Short that this lane uploads
(docs/BRAND_STYLE.md: "every piece of content follows this or it doesn't ship").
"""

import json
import os
import re
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
import deepdive_links  # noqa: E402
import deepdive_promo  # noqa: E402  — the latest episode, when the parent is not out yet  — which Deep-Dive this Short trails, and its watch link
import shorts_sound  # noqa: E402  — the soundtrack report, for the run summary
import series_week  # noqa: E402  — the week's five-part series, for the description line


HASHTAGS = "#Shorts #TenantTips #NigeriaRent"
FOLLOW = ("Daily tips on Telegram: https://t.me/docogadaily · Facebook: https://facebook.com/docoga.com.ng")


def headlines(script):
    """The tip slides' on-screen headlines (hook and disclaimer left out), Sentence case."""
    out = []
    for slide in (script.get("slides") or [])[1:]:
        if not slide.get("say"):
            continue
        text = " ".join(str(slide.get("text") or "").split())
        if text:
            lowered = text[:1] + text[1:].lower()
            out.append(re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), lowered))
    return out


def describe(script, link=None):
    """The YouTube description for a rotation topic.

    The parent Deep-Dive link comes first — the first two lines are what the Shorts player
    shows under "...more", and the whole point of a Short is to send the viewer to the
    nine-minute episode it was cut from (first stats snapshot, 14 Oct 2026: Shorts at 108
    views, the long-forms at 0–2). Then the words YouTube search can read (17 Oct 2026
    research: the description is indexed, the pixels of the burned-in captions are not): the
    spoken hook sentence and the tip headlines, so "rent receipt" / "agency fee" / "notice to
    quit" sit in text. Three hashtags — YouTube shows the first three above the title; more
    than fifteen and it ignores them all — and the places the daily tips live."""
    slides = script.get("slides") or []
    hook = " ".join(str((slides[0] if slides else {}).get("say") or "").split())
    tips = headlines(script)
    body = []
    if hook:
        body.append(hook)
    series = script.get("series") if isinstance(script.get("series"), dict) else None
    if series:
        # One prose line the search index and the binge-watcher both read: which part this is,
        # what tomorrow's is called (tools/series_week.py, 23 Oct 2026).
        body.append(series_week.sentence(series, series.get("next_title", "")))
    if tips:
        body.append("In this Short:\n" + "\n".join("• " + t for t in tips))
    body.append(
        "Practical document-keeping tips for Nigerian tenants and landlords. "
        "General information only; rules vary by state and agreement. "
        "This is not legal advice. More free document tools: "
        "https://docoga.com.ng"
    )
    body.append(FOLLOW)
    # The series hashtag first: YouTube shows the first three above the title, and the hashtag
    # page is one more place the five parts sit together (23 Oct 2026).
    body.append((series_week.hashtag(series) + " " + HASHTAGS) if series else HASHTAGS)
    return deepdive_links.description_block(link) + "\n\n".join(body)


SHORTS_LEDGER = Path(__file__).resolve().parents[1] / "logs" / "youtube_published.json"


def series_outputs(script, run_date, ledger=SHORTS_LEDGER):
    """What the other lanes need to carry the chain (23 Oct 2026): the frame line for Threads and
    Telegram, the Threads topic tag, the playlist plan for yt_boost, and the comment lines that
    link this week's earlier parts (read from the publish ledger — only what really went out)."""
    series = script.get("series") if isinstance(script.get("series"), dict) else None
    if not series:
        return {"series_json": "", "series_line": "", "series_topic": "", "series_chain": ""}
    try:
        rows = json.loads(Path(ledger).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    previous = series_week.previous_parts(series, run_date, rows if isinstance(rows, list) else [])
    return {
        "series_json": json.dumps({k: series[k] for k in ("slug", "name", "part", "total", "week_start")}),
        "series_line": series_week.line(series),
        "series_topic": series_week.topic_tag(series),
        "series_chain": "\n".join(series_week.chain_lines(series, previous)),
    }


def write_outputs(outputs):
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


def main():
    run_date = datetime.now(ZoneInfo("Africa/Lagos")).date()
    # RUN_FOR_DATE: the resumer finishing a Short that was owed (the narrator's bucket
    # was empty at 18:00) renders *that* day's rotation topic, published today.
    for_date = os.environ.get("RUN_FOR_DATE", "").strip()
    if for_date:
        run_date = datetime.fromisoformat(for_date).date()
        print(f"rendering the rotation topic for {run_date} (RUN_FOR_DATE)")
    script = shorts_reel.topic_for(run_date)
    output_path = shorts_reel.default_output_path(run_date, prefix="docoga_short")
    try:
        video = Path(shorts_reel.render_topic(script, output_path, tag="yt",
                                              platform="YouTube Shorts"))
    except shorts_sound.VoiceUnavailable as exc:
        # Not an error: no voice → no Short (SHORTS_VOICE=required). The reason names
        # when the narrator's bucket refills; narrator_resume.yml publishes it then.
        import gemini_quota
        when = gemini_quota.lagos(exc.resumes_at) if exc.resumes_at else "the next reset"
        write_outputs({"paused": "yes", "voice_reason": exc.reason, "voice_resumes_at": when,
                       "topic": script["title"], "title": shorts_reel.title_for(script)})
        print(f"⏸ no voice, no Short: {exc.reason}")
        print(f"::warning title=Short paused — narrator unavailable::{exc.reason}. "
              "The resumer (narrator_resume.yml) publishes it once the bucket refills.")
        return 6

    if video.suffix.lower() != ".mp4" or not video.is_file() or video.stat().st_size < 10_000:
        raise RuntimeError(f"Video generation did not produce a usable MP4: {video}")

    parent = script.get("parent")
    link = deepdive_links.parent_link(parent) if parent and parent != "brain" else None
    if not link:
        # No published parent (a brain Short, or an episode still in the queue): the Short trails
        # the latest watchable Deep-Dive instead (tools/deepdive_promo.py, 17 Oct 2026) — every
        # Short is a trailer for *some* episode, in its description and its first comment.
        link = deepdive_promo.latest_link()
        if link:
            print(f"::notice title=Trailing the latest Deep-Dive::{script['title']} has no published "
                  f"parent; the description and comment point at '{link[0]}'.")
    if script.get("parent") and not link:
        print(f"::notice title=Parent Deep-Dive not published yet::{script['title']} trails "
              f"'{script['parent']}', which is not in logs/youtube_longform.json yet — the "
              "description carries no episode link this time; it appears automatically once "
              "the Deep-Dive lane publishes it.")

    chain = series_outputs(script, run_date)
    outputs = {
        **chain,
        "video_path": str(video),
        # The settled hook card beside the master (MotionStudio writes it; frame 0 is the same
        # picture): YouTube's custom thumbnail, Telegram's cover, and what TikTok shows by default.
        "cover_path": str(shorts_reel.cover_for(video)) if shorts_reel.cover_for(video).is_file() else "",
        "soundtrack": shorts_sound.summary_line(video),
        "title": shorts_reel.title_for(script),
        # The rotation topic without the #Shorts suffix — this is what the
        # publish ledger records, so the ledger reads as plain English.
        "topic": script["title"],
        "description": describe(script, link),
        "tags": "docoga,nigeria,tenant tips,landlord tips,shorts",
        # The channel's first comment under the Short (tools/yt_boost.py posts it once the
        # Short is public — the token holds youtube.force-ssl since 17 Oct 2026); the run
        # summary still shows the line so the owner can pin it from the app in one tap.
        "pinned_comment": "\n".join(x for x in (deepdive_links.pinned_comment(link), chain["series_chain"]) if x),
        "parent_url": link[1] if link else "",
        "parent_title": link[0] if link else "",
        "narrator": gemini_quota_status(),
    }
    write_outputs(outputs)
    print(f"Prepared {outputs['title']} ({video.stat().st_size} bytes)")
    return 0


def gemini_quota_status():
    try:
        import gemini_quota
        return gemini_quota.status_line()
    except Exception as exc:  # the summary must never fail the publish
        return "narrator bucket: unknown (%s)" % exc


if __name__ == "__main__":
    sys.exit(main())
