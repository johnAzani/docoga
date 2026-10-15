#!/usr/bin/env python3
"""
Decide (and optionally render) today's DocOga Reel for the Facebook Page
=========================================================================

One file answers three questions, in this order, because each is cheaper than
the next:

  1. **Is today a Reel day, and is the lane switched on?** (`--plan`)
  2. **Has this topic already been published to the Page inside the frame law?**
     — answered by the workflow through `tools/youtube_ledger.py`, on
     `logs/facebook_reels.json`, before anything is rendered.
  3. **Render the file.** (`--render`, ~2 minutes of CPU on a free runner)

`--plan` never renders, so a run on a non-Reel day costs seconds rather than
minutes. That is why the workflow calls the plan step first: deciding is cheap,
and a pipeline that only discovers it had nothing to do after rendering is a
pipeline that burns its free minutes on a skip.

The video itself is **the same render as the YouTube Short** — the words from
the date-seeded rotation in `scripts/generate_short_video.py`, the picture from
`tools/motionstudio.py` through the one bridge `tools/shorts_reel.py` (Inter on
#061A33, springs, yellow underline, grain — `docs/BRAND_STYLE.md` §5, no logo on
motion per `docs/DESIGN_SYSTEM.md` §1). One content source, one renderer, two
conversion points; a second reel generator would drift within a week.

The two lanes deliberately do **not** share days: Shorts run Tue/Fri
(`youtube_scheduled.yml`), Reels run Mon/Thu. Same weekday would mean the same
rotation index, i.e. the same topic on both platforms on the same day, which is
what the 30-day frame law in `docs/GROWTH_ENGINE.md` §4 forbids. Different day ⇒
different index ⇒ different topic, for free.

Modes (`REELS_MODE`, from the repository variable `FB_REELS`):

  ``probe``  (default) open and abandon a `video_reels` upload session on Reel
             days. Proves the Reels grant is live, publishes nothing, and is what
             the summary line reports until the owner switches the lane on.
  ``on``     render, then publish through the three-phase protocol.
  ``off``    nothing at all; the summary says so. It is a switch, not a mystery.

Exit codes — chosen so the job can tell "nothing to do" from "something broke":

  0  planned, or rendered, or correctly stood down (not a Reel day / mode off)
  3  `--render` was asked for and the render failed
  4  the mode or the rotation is configured in a way that cannot be honoured
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "scripts", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

LAGOS = timezone(timedelta(hours=1))

# Monday and Thursday. Not Tuesday/Friday, which is YouTube's slot — see the
# docstring. Not Wednesday, because the Wednesday slot is what a midweek
# manual `mode=reel` dispatch keeps free.
REEL_WEEKDAYS = (0, 3)

# Meta's Reels surface: 3-90 seconds. Our render is 6 slides of 3-4s ≈ 23s, which
# is inside the range and inside the 15-30s engagement sweet spot the 2026 spec
# guides converge on. Nothing here forces that length; it is asserted in tests so
# that a slide edit which pushes a reel past 90s fails here rather than silently
# publishing as a plain video post.
REEL_MIN_SECONDS = 3
REEL_MAX_SECONDS = 90

MODES = ("probe", "on", "off")

OUTPUT_DIR = Path("assets/videos")


def is_reel_day(day):
    """True on the days this lane publishes."""
    return day.weekday() in REEL_WEEKDAYS


def mode_from_env():
    mode = (os.environ.get("REELS_MODE") or "probe").strip().lower()
    return mode


def plan(day, mode):
    """Everything the cheap decision needs: no import of moviepy, no render."""
    if mode not in MODES:
        return {"reel_today": "no", "reason": "unknown REELS_MODE %r (want one of %s)"
                % (mode, "|".join(MODES)), "exit": 4}
    if mode == "off":
        return {"reel_today": "no", "reason": "reels disabled (vars FB_REELS=off)", "exit": 0}
    if not is_reel_day(day):
        return {"reel_today": "no",
                "reason": "not a reel day (%s)" % ", ".join(
                    day_name for day_name, index in
                    (("Mon", 0), ("Tue", 1), ("Wed", 2), ("Thu", 3), ("Fri", 4))
                    if index in REEL_WEEKDAYS),
                "exit": 0}
    # The decision must not depend on the renderer being importable. `reel_topic`
    # reads the rotation, and the rotation lives in the module that imports PIL and
    # moviepy — so a laptop, or a runner mid-install, would otherwise turn a cheap
    # "is today a reel day?" into a traceback. Asked politely, it answers "topic
    # unknown", and the render step is where a missing renderer is reported.
    try:
        topic = reel_topic(day)
        topic_error = ""
    except Exception as exc:                       # ImportError, or anything the
        topic = ""                                 # renderer raises at import time
        topic_error = "%s: %s" % (type(exc).__name__, exc)
    return {
        "reel_today": "yes",
        "mode": mode,
        "topic": topic,
        "title": topic,
        "topic_error": topic_error,
        "run_date": day.isoformat(),
        "output_path": str(OUTPUT_DIR / ("docoga_reel_%s.mp4" % day.strftime("%Y%m%d"))),
        "exit": 0,
    }


def reel_topic(day):
    """The day's frame title, from the shared rotation.

    Imported lazily on purpose, and *raises* if the rotation's module cannot be
    loaded — `plan()` is what decides whether that matters yet.
    """
    import generate_short_video as words
    return words.script_for_date(day)["title"]


def render(day, output_path=None):
    """Render the reel through MotionStudio. Returns (ok, path_or_reason, info)."""
    try:
        import shorts_reel  # the MotionStudio bridge — imports PIL + numpy
    except Exception as exc:  # Pillow/numpy missing on this machine
        return False, "the renderer could not be imported (%s: %s) — on a runner, " \
                      "install requirements-youtube.txt" % (type(exc).__name__, exc), {}
    problems = shorts_reel.ms.check_environment()
    if problems:
        return False, "the renderer cannot run here: %s" % "; ".join(problems), {}

    script = shorts_reel.topic_for(day)
    if not script.get("slides"):
        return False, "the rotation returned no slides for %s" % day.isoformat(), {}
    try:
        planned_seconds = shorts_reel.planned_seconds(script)
    except Exception as exc:
        return False, "the rotation's frame for '%s' does not fit the Shorts grammar (%s: %s)" \
                      % (script.get("title"), type(exc).__name__, exc), {}
    if not (REEL_MIN_SECONDS <= planned_seconds <= REEL_MAX_SECONDS):
        # Catch it here, in the file that owns the lane, where the message can say
        # what to do — not in Meta's silence after a 2-minute render.
        return False, ("the rotation's frame for '%s' is %.1fs; Reels need %d-%ds, so "
                       "trim slides in scripts/generate_short_video.py"
                       % (script["title"], planned_seconds, REEL_MIN_SECONDS,
                          REEL_MAX_SECONDS)), {}

    path = Path(output_path) if output_path else (
        OUTPUT_DIR / ("docoga_reel_%s.mp4" % day.strftime("%Y%m%d")))
    try:
        video_path = shorts_reel.render_topic(script, path, tag="fb", platform="Facebook Reels")
    except Exception as exc:
        return False, "render failed (%s: %s)" % (type(exc).__name__, exc), {}

    video = Path(video_path)
    if not video.is_file() or video.stat().st_size < 10_000:
        return False, ("render produced no usable MP4 (%s, %d bytes)"
                       % (video, video.stat().st_size if video.is_file() else -1)), {}
    import shorts_sound
    return True, str(video), {"seconds_planned": planned_seconds, "bytes": video.stat().st_size,
                              "title": script["title"], "topic": script["title"],
                              "soundtrack": shorts_sound.summary_line(video)}


def emit(outputs):
    """Print the `key=value` lines, and *also* write them to `$GITHUB_OUTPUT`.

    Both, not either. The daily path reads step outputs; the manual `mode: reel`
    path and the ledger's title fallback grep the tee'd log
    (`/tmp/fb_reel_render.log`). An if/else here would make those greps silently
    empty in CI while passing every local run — the shape of bug where "it worked
    on my machine" is literally true and useless. `scripts/youtube_short_daily.py`
    has the same if/else; it survives only because nothing greps its log.
    """
    for key, value in outputs.items():
        print("%s=%s" % (key, value))
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    with open(github_output, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write("%s=%s\n" % (key, value))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Decide and render the daily Facebook Reel")
    parser.add_argument("--date", help="ISO date to plan for (default: today in Africa/Lagos)")
    parser.add_argument("--plan", action="store_true",
                        help="decide only — never render (this is the default)")
    parser.add_argument("--render", action="store_true",
                        help="render the file as well, and print its path")
    parser.add_argument("--output", help="where to write the .mp4 (default: assets/videos/…)")
    parser.add_argument("--mode", choices=MODES, help="override REELS_MODE / vars.FB_REELS")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    day = date.fromisoformat(args.date) if args.date else datetime.now(LAGOS).date()
    mode = args.mode or mode_from_env()
    decided = plan(day, mode)
    emit({"reel_today": decided["reel_today"], "mode": mode,
          "reason": decided.get("reason", "planned"),
          "topic": decided.get("topic", ""), "title": decided.get("title", ""),
          "topic_error": decided.get("topic_error", ""),
          "run_date": decided.get("run_date", day.isoformat()),
          "output_path": decided.get("output_path", "")})
    if decided.get("topic_error"):
        print("⚠️  the rotation could not be read (%s) — the render step will name it"
              % decided["topic_error"])

    if decided["exit"]:
        print("❌ %s" % decided["reason"])
        return decided["exit"]
    if decided["reel_today"] != "yes":
        print("⏭ %s" % decided["reason"])
        return 0
    if not args.render:
        print("🎬 planned: %s (%s) — render step will do the work"
              % (decided["title"], decided["mode"]))
        return 0

    ok, result, info = render(day, args.output or decided.get("output_path"))
    if not ok:
        print("❌ %s" % result)
        return 3
    emit({"video_path": result, "title": info["title"], "topic": info["topic"],
          "bytes": info["bytes"]})
    print("🎬 rendered %s (%d bytes, planned %.1fs) · sound: %s"
          % (result, info["bytes"], info["seconds_planned"], info.get("soundtrack", "?")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
