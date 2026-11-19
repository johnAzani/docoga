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

**Which days (17 Nov 2026, owner: "Ok let's do it" — the Page goes daily).** The weekday
Reel is already published by `youtube_scheduled.yml`: every weekday Short is republished to
the Page at 19:00, the peak, and recorded in `logs/facebook_reels.json`. A morning Reel on a
weekday would either duplicate that post or publish first and make the 19:00 step skip as a
duplicate, trading the peak for 09:30. So this lane takes **Saturday and Sunday**, the two days
nothing covered.

**Which frame.** `reel_script()` removes the day's Short from the pool and walks the rotation
against the Page's own ledger with `fresh.FRESH_DAYS` (28): the page never carries the same
words twice inside four weeks, and never the same words as the day's Short. When every frame is
inside that window the lane stands down and says so, rather than recycling one (owner, 24 Oct
2026: "make sure you are not repeating or recycling contents"). With six frames in the rotation
that is roughly one Reel a fortnight, which is a content-supply fact, not a scheduling bug.

Modes (`REELS_MODE`, from the repository variable `FB_REELS`):

  ``on``     (default since 16 Nov 2026) render, then publish through the three-phase protocol.
  ``probe``  open and abandon a `video_reels` upload session. Proves the grant is live and
             publishes nothing — the old default, restored by `FB_REELS=probe`.
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

# **The weekend**, since 17 Nov 2026 (owner: "Ok let's do it" — the Page goes daily).
#
# Not every day, and that is the whole finding: the Page was already getting a Reel Monday to
# Friday. `youtube_scheduled.yml` republishes every weekday Short to the Page at 19:00, the
# peak, and records it in `logs/facebook_reels.json` (`SHORT_REELS`, on by default). A morning
# Reel on a weekday therefore either duplicates that post subject or, worse, gets published
# first and makes the 19:00 step skip as a duplicate — replacing the peak slot with a 09:30
# one. So this lane takes the two days nobody covers: Saturday and Sunday.
#
# What it adds is not only two posts. The frame is picked by `reel_script()`: the day's Short
# is out of the pool, and the walk reads the Page's own ledger with `fresh.FRESH_DAYS`, so a
# frame the Page carried inside four weeks is never recycled — the day stands down and says so
# (owner, 24 Oct 2026: "make sure you are not repeating or recycling contents").
REEL_WEEKDAYS = (5, 6)

# Meta's Reels surface: 3-90 seconds. Our render is 6 slides of 3-4s ≈ 23s, which
# is inside the range and inside the 15-30s engagement sweet spot the 2026 spec
# guides converge on. Nothing here forces that length; it is asserted in tests so
# that a slide edit which pushes a reel past 90s fails here rather than silently
# publishing as a plain video post.
REEL_MIN_SECONDS = 3
REEL_MAX_SECONDS = 90

MODES = ("probe", "on", "off")


def _fresh_days():
    """`fresh.FRESH_DAYS` without depending on the media stack (fresh is stdlib-only)."""
    try:
        import fresh
        return fresh.FRESH_DAYS
    except Exception:
        return 28

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
        return {"reel_today": "no", "exit": 0,
                "reason": ("the weekday Reel comes from youtube_scheduled.yml at 19:00, the peak; "
                           "this lane takes Saturdays and Sundays (%s)"
                           % ", ".join(name for name, index in
                                       (("Sat", 5), ("Sun", 6)) if index in REEL_WEEKDAYS))}
    # The decision must not depend on the renderer being importable. `reel_topic`
    # reads the rotation, and the rotation lives in the module that imports PIL and
    # moviepy — so a laptop, or a runner mid-install, would otherwise turn a cheap
    # "is today a reel day?" into a traceback. Asked politely, it answers "topic
    # unknown", and the render step is where a missing renderer is reported.
    try:
        script = reel_script(day)
        topic = str(script.get("title") or "")
        topic_error = ""
    except Exception as exc:                       # ImportError, or anything the
        script, topic = {}, ""                     # renderer raises at import time
        topic_error = "%s: %s" % (type(exc).__name__, exc)
    if not topic_error and script.get("stale"):
        return {"reel_today": "no", "exit": 0,
                "reason": ("every frame is inside the %d-day freshness window on the Page "
                           "(last carried %s) — new frames are the fix, not another day"
                           % (_fresh_days(), script.get("last_published") or "never")),
                "run_date": day.isoformat()}
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


def reel_script(day):
    """The Page's frame for `day` — the rotation walked against the Page's own ledger, with
    the day's Short taken out of the pool.

    Two rules, both the owner's:

      * the same words must not be on YouTube and Facebook on the same day
        (the same words on two platforms on one day) — so whatever `script_for_date` picked for the Short is
        not in the pool here;
      * the Page must not repeat itself inside `fresh.FRESH_DAYS` (24 Oct 2026: "make sure
        you are not repeating or recycling contents") — so the walk reads
        `logs/facebook_reels.json`, not YouTube's ledger.

    When every remaining frame is inside that window the pick comes back `stale=True` and
    `plan()` stands the day down instead of recycling. Raises only when the rotation itself
    cannot be imported; `plan()` turns that into its own reason.
    """
    import generate_short_video as words
    import fresh
    short = words.script_for_date(day) or {}
    short_title = str(short.get("title") or "")
    pool = [s for s in words.VIDEO_SCRIPTS if str(s.get("title") or "") != short_title]
    if len(pool) < 2:                      # one frame left is not a rotation
        pool = list(words.VIDEO_SCRIPTS)
    pick = fresh.pick_rotation(day, pool, fresh.history("facebook"))
    script = dict(pick.get("script") or {})
    if pick.get("stale"):
        script["stale"] = True
        last = pick.get("last_seen")
        script["last_published"] = last.isoformat() if last else ""
    try:
        return dict(words.with_series(script, day))
    except Exception:                      # the series is a frame; the Reel renders without it
        return script


def reel_topic(day):
    """The day's frame title. Imported lazily on purpose, and *raises* if the rotation's
    module cannot be loaded — `plan()` is what decides whether that matters yet."""
    return reel_script(day)["title"]


def render(day, output_path=None):
    """Render the reel through MotionStudio. Returns (ok, path_or_reason, info)."""
    # Content before machinery: a day with no fresh frame must not even import the
    # renderer, and must never spend two minutes rendering a frame the Page already
    # carried inside the freshness window (owner, 24 Oct 2026: no recycling).
    try:
        stale = reel_script(day)
    except Exception:
        stale = {}
    if stale.get("stale"):
        return False, ("every frame is inside the %d-day freshness window on the Page "
                       "(last carried %s) — render nothing rather than recycle one"
                       % (_fresh_days(), stale.get("last_published") or "never")), {}
    try:
        import shorts_reel  # the MotionStudio bridge — imports PIL + numpy
    except Exception as exc:  # Pillow/numpy missing on this machine
        return False, "the renderer could not be imported (%s: %s) — on a runner, " \
                      "install requirements-youtube.txt" % (type(exc).__name__, exc), {}
    problems = shorts_reel.ms.check_environment()
    if problems:
        return False, "the renderer cannot run here: %s" % "; ".join(problems), {}

    script = reel_script(day)
    if script.get("stale"):
        return False, ("every frame is inside the %d-day freshness window on the Page — "
                       "render nothing rather than recycle one" % _fresh_days()), {}
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
        import shorts_sound
        if isinstance(exc, shorts_sound.VoiceUnavailable):
            # Not an error: the narrator's bucket is empty and the policy says no voice →
            # no Reel. The reason names the refill time; narrator_resume.yml finishes it.
            import gemini_quota
            return False, exc.reason, {"paused": True, "title": script["title"], "topic": script["title"],
                                       "resumes_at": gemini_quota.lagos(exc.resumes_at) if exc.resumes_at else ""}
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
    if not ok and info.get("paused"):
        emit({"paused": "yes", "voice_reason": result, "voice_resumes_at": info.get("resumes_at", ""),
              "title": info.get("title", ""), "topic": info.get("topic", "")})
        print("⏸ no voice, no Reel: %s" % result)
        print("::warning title=Reel paused — narrator unavailable::%s. The resumer (narrator_resume.yml) "
              "publishes it once the bucket refills." % result)
        return 6
    if not ok:
        print("❌ %s" % result)
        return 3
    import gemini_quota
    emit({"video_path": result, "title": info["title"], "topic": info["topic"],
          "bytes": info["bytes"], "soundtrack": info.get("soundtrack", ""),
          "narrator": gemini_quota.status_line()})
    print("🎬 rendered %s (%d bytes, planned %.1fs) · sound: %s"
          % (result, info["bytes"], info["seconds_planned"], info.get("soundtrack", "?")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
