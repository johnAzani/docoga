#!/usr/bin/env python3
"""
SHORTS REEL — the one way a tenant-tip topic becomes a YouTube Short / Facebook Reel.

`scripts/generate_short_video.py` owns the *words* (the date-seeded VIDEO_SCRIPTS
rotation: a hook, four tips, a disclaimer). `tools/motionstudio.py` owns the
*picture* (Inter Black on #061A33, springs, cascades, the yellow underline, the
grain — docs/BRAND_STYLE.md §5 and docs/DESIGN_SYSTEM.md §6). This module is the
only bridge between them, so a publish lane cannot reach a renderer that is not
MotionStudio.

    topic = script_for_date(day)                 # words
    reel  = reel_from_topic(topic, out_path)     # MotionStudio spec
    render_topic(topic, out_path, tag)           # → mp4, or raises

Grammar used (and nothing else):
    hook        kicker + cascade + support          flash
    tip × 4     green check badge + cascade + support   whip / flash alternating
    conclusion  wordpop "FREE." + button + support + disclaimer kicker   dissolve

No icon grid, no name cycler (those need social/assets/icon-*.png), no strike
(nothing here is an external price). Palette and typeface come from the engine
constants — there is deliberately no colour or font literal in this file.

Run:  python3 tools/shorts_reel.py [--date YYYY-MM-DD] [--out PATH] [--dry-run]
"""

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import motionstudio as ms  # noqa: E402

# Shorts and Reels tolerate longer than the 15.6 s brand Reels cap; reading time
# governs, not the cap. Six scenes with four tips sit at ~20 s.
SHORTS_CAP = 24.0
# How much of the matched photograph survives behind the words (brain_visual.treat `darken`).
# 0.36 shipped on 17 Oct and read as plain navy on a phone (brightest pixel ≈ 86/255) — the
# owner's second complaint about the first TikTok draft, 18 Oct 2026. 0.68 keeps the duotone
# photograph plainly visible while white and yellow type still clear 4.5:1 over the scrimmed band.
SHOT_DARKEN = 0.68
HANDLE = "@docoga.ng"
CTA_URL = "docoga.com.ng"
SERIES_KICKER = "DOCOGA · TENANT TIPS"
CTA_SUPPORT = "Free tenant documents. No signup."
DISCLAIMER_KICKER = "GENERAL INFO · RULES VARY BY STATE"
FOLLOW_KICKER = "FOLLOW " + HANDLE.upper()

DEFAULT_OUTPUT_DIR = ROOT / "assets" / "videos"


def _up(text):
    return " ".join(str(text or "").split()).upper()


def _clean(text):
    return " ".join(str(text or "").split())


def split_hook(text):
    """(setup, consequence) for a two-beat STAKES hook; (whole, None) otherwise.

    The rotation writes the beat break as a newline ("PAY WITHOUT A RECEIPT.\\nPAY
    TWICE."); a hook written as two sentences on one line splits at the first
    full stop that ends a sentence. A single-sentence hook is left whole."""
    raw = str(text or "")
    if "\n" in raw.strip():
        a, b = raw.strip().split("\n", 1)
        return _up(a), (_up(b) or None)
    whole = _up(raw)
    parts = [p.strip() for p in whole.split(". ") if p.strip()]
    if len(parts) == 2:
        return parts[0] + ".", parts[1]
    return whole, None


def split_topic(topic):
    """(hook, tips[], disclaimer) from a rotation entry; raises if the shape is off."""
    slides = list(topic.get("slides") or [])
    if len(slides) < 3:
        raise ValueError("topic '%s' has %d slides; need hook + tips + disclaimer"
                         % (topic.get("title"), len(slides)))
    hook, body, disclaimer = slides[0], slides[1:-1], slides[-1]
    if "GENERAL INFO" not in _up(disclaimer.get("text")):
        raise ValueError("topic '%s': the last slide must be the GENERAL INFO disclaimer"
                         % topic.get("title"))
    tips = body[:4]  # the grammar carries at most four tips; the rotation ships four
    if not tips:
        raise ValueError("topic '%s' has no tips" % topic.get("title"))
    return hook, tips, disclaimer


def reel_from_topic(topic, out_path, platform="YouTube Shorts"):
    """Build the MotionStudio reel dict for one rotation topic."""
    hook, tips, disclaimer = split_topic(topic)
    out_path = str(Path(out_path).resolve())
    scenes = []

    setup, consequence = split_hook(hook["text"])
    hook_beats = [ms.Beat("kicker", "kicker", SERIES_KICKER, size=30, y=470, color=ms.FAINT)]
    if consequence:
        # STAKES hook (the pattern the channel's numbers reward — see
        # generate_short_video.py): the careless act lands first in white, the
        # consequence slams in underneath in brand yellow. Two cascades, so each
        # line wraps on its own and neither drags the reel's type size down.
        hook_beats += [
            ms.Beat("cascade", "hook", setup, size=132, y=560, color=ms.WHITE),
            ms.Beat("cascade", "hook", consequence, size=150, y=820, color=ms.YELLOW),
            ms.Beat("support", "support", _clean(hook.get("sub")), size=56, y=1060,
                    color=ms.MUTED),
        ]
    else:
        hook_beats += [
            ms.Beat("cascade", "hook", setup, size=150, y=600, color=ms.WHITE),
            ms.Beat("support", "support", _clean(hook.get("sub")), size=56, y=900,
                    color=ms.MUTED),
        ]
    scenes.append(dict(id="A", role="hook", dur=3.2, punch=0.050, trans="flash", beats=hook_beats))

    for i, tip in enumerate(tips):
        scenes.append(dict(
            id=chr(ord("B") + i), role="tip", dur=3.4, punch=0.030,
            trans="whip" if i % 2 == 0 else "flash",
            beats=[
                ms.Beat("badge", "emphasis", shape="check", color=ms.GREEN, cy=500, r=52),
                ms.Beat("cascade", "emphasis", _up(tip["text"]), size=140, y=610,
                        color=ms.WHITE),
                ms.Beat("support", "support", _clean(tip.get("sub")), size=52, y=930,
                        color=ms.MUTED),
            ]))

    disclaimer_text = DISCLAIMER_KICKER
    scenes.append(dict(
        id=chr(ord("B") + len(tips)), role="conclusion", dur=4.6, punch=0.0, trans="dissolve",
        beats=[
            ms.Beat("wordpop", "conclusion", "FREE.", size=190, y=520, color=ms.WHITE,
                    underline=ms.YELLOW, rings=True),
            ms.Beat("button", "cta", CTA_URL, y=840),
            ms.Beat("support", "support", CTA_SUPPORT, size=44, y=1010, color=ms.MUTED),
            ms.Beat("kicker", "kicker", disclaimer_text, size=24, y=1135, color=ms.FAINT,
                    t0=1.60),
            ms.Beat("kicker", "kicker", FOLLOW_KICKER, size=24, y=1185, color=ms.BLUE,
                    t0=1.85),
        ]))

    return dict(
        name="DocOga Short — %s" % topic["title"],
        out=out_path,
        cap=SHORTS_CAP,
        purpose="one practical document-keeping habit for Nigerian tenants",
        audience="tenants and landlords in Nigeria on their phones",
        platform=platform,
        tone="calm, confident, useful — never alarmist, never legal advice",
        peak="the four tips land one by one; FREE. resolves it",
        hierarchy="hook > tip cascades > CTA > disclaimer",
        scenes=scenes,
        # Carried for the lanes and the ledger; the engine ignores unknown keys.
        topic=topic["title"],
        disclaimer=_clean(disclaimer.get("text")) + " — " + _clean(disclaimer.get("sub")),
    )


def shots_for(reel, topic):
    """[(scene, what is said, query chain)] for the hook and tip scenes — the words the narrator
    reads in that scene are the words the picture must match. The conclusion stays on the navy:
    FREE. and the button are the brand's own frame."""
    import shorts_sound
    import shot_match
    said = {line["scene"]: line["text"] for line in shorts_sound.narration_for(reel, topic)}
    out = []
    for sc in reel["scenes"]:
        if sc["role"] not in ("hook", "tip"):
            continue
        text = said.get(sc["id"]) or " ".join(b.get("text") or "" for b in sc["beats"])
        out.append((sc, text, shot_match.query_chain(text, hint=sc.get("shot"))))
    return out


def attach_shots(reel, topic):
    """Put a matched CC0 photograph behind each hook/tip scene (`_bg`, W×H, brand duotone) — owner,
    17 Oct 2026: free images behind the cards, matching what is being said. A scene whose picture
    cannot be found or fetched keeps the navy; the Short is never late because of a photo."""
    import shot_match
    if not shot_match.enabled():
        return 0
    import brain_visual
    hits = 0
    for sc, text, chain in shots_for(reel, topic):
        raw = {}

        def _treat(im, size, raw=raw):
            raw["img"] = im           # the untreated photograph — the cover treats it its own way
            return brain_visual.treat(im, size, darken=SHOT_DARKEN)
        img, note = shot_match.photo_for(text, hint=sc.get("shot"), size=(ms.W, ms.H), treat=_treat)
        sc["shot"] = chain[0]
        if img is not None:
            sc["_bg"] = img
            if raw.get("img") is not None:
                sc["_bg_raw"] = raw["img"]
            hits += 1
            print("  📷 scene %s ← %s (%s)" % (sc["id"], note.get("query"), note.get("license") or "cc0"))
        else:
            print("  · scene %s stays navy (%s)" % (sc["id"], note))
    return hits


def planned_seconds(topic):
    """The solved timeline length, without rendering a frame."""
    reel = reel_from_topic(topic, "/tmp/_planned.mp4")
    ms.solve_sizes(reel)
    ms.solve_layout(reel)
    ms.schedule(reel)
    return float(reel["total"])


def topic_for(day):
    """The rotation's words for a date — the ONLY thing taken from generate_short_video."""
    import generate_short_video as words
    return words.script_for_date(day)


def default_output_path(day, prefix="docoga_short"):
    return DEFAULT_OUTPUT_DIR / ("%s_%s.mp4" % (prefix, day.strftime("%Y%m%d")))


def sound_enabled():
    """SHORTS_SOUND=off renders the silent picture only (tests, a laptop without ffmpeg audio)."""
    return os.environ.get("SHORTS_SOUND", "on").strip().lower() not in ("off", "0", "no", "false")


def render_topic(topic, out_path, tag="short", platform="YouTube Shorts", sound=None):
    """Render through MotionStudio, then score it. Returns the Path; raises if QA refuses.

    Sound (tools/shorts_sound.py) is voice-first: the locked narrator reads each
    scene, the scene stretches to the read, MotionStudio renders those timings,
    and the mix (voice + ducked bed + SFX) replaces the engine's empty track.
    No voice → no publish under the default policy (SHORTS_VOICE=required):
    VoiceUnavailable names when the narrator's bucket refills, and the lane
    resumes then. SHORTS_VOICE=optional ships music + SFX instead. Silent is
    never an outcome (owner, 15 Oct 2026).
    """
    problems = ms.check_environment()
    if problems:
        raise RuntimeError("MotionStudio cannot render here: " + "; ".join(problems))
    sound = sound_enabled() if sound is None else sound
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reel = reel_from_topic(topic, out_path, platform=platform)
    clips, dropped = [], ""
    if sound:
        import shorts_sound
        print("── 0. NARRATION (%s) ──" % shorts_sound._deepdive().LOCKED_VOICE_NAME)
        clips, dropped = shorts_sound.narrate(shorts_sound.narration_for(reel, topic))
        shorts_sound.require_voice(clips, dropped)   # raises VoiceUnavailable under the default policy
        if clips:
            total = shorts_sound.fit_scenes(reel, clips)
            print("  scenes stretched to the read: %.1fs" % total)
            captions = shorts_sound.caption_beats(reel, clips, ms=ms)
            if captions:
                print("  detailed read: %d caption sentence(s) follow the narrator" % captions)
        else:
            print("  ⚠️  " + dropped)
    hits = attach_shots(reel, topic)
    wanted = sum(1 for sc in reel["scenes"] if sc["role"] in ("hook", "tip"))
    print("SHOTS_HITS=%d/%d" % (hits, wanted))   # machine line: the workflows surface it
    # The cover (frame 0 + <master>.cover.jpg) is designed, not a paused frame: the verdict on
    # yellow slabs inside the grid-safe band (tools/short_cover.py, docs/SHORT_COVER.md).
    import short_cover
    reel["cover_fn"] = lambda: short_cover.render(reel)
    print("  " + short_cover.describe(reel))
    ok = ms.build(reel, tag)
    if not ok:
        raise RuntimeError("MotionStudio refused to encode '%s' — the video QA engine found "
                           "violations it could not auto-fix (see the log above)" % topic["title"])
    if not out_path.is_file() or out_path.stat().st_size < 10_000:
        raise RuntimeError("MotionStudio reported success but %s is missing or tiny" % out_path)
    if sound:
        print("── 7. SOUNDTRACK ──")
        shorts_sound.score(reel, clips, out_path, dropped_reason=dropped)
    cover = cover_for(out_path)
    if cover.is_file():
        print("COVER=%s" % cover)   # machine line: the settled hook card, the custom thumbnail
    return out_path


def cover_for(out_path):
    """The cover JPEG MotionStudio writes beside a master (`<name>.cover.jpg`): the opening card
    drawn settled, identical to frame 0 of the video."""
    return Path(ms.cover_path_for(str(out_path)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render today's tenant-tip Short with MotionStudio")
    ap.add_argument("--date", help="ISO date (default: today, Africa/Lagos)")
    ap.add_argument("--out", help="output .mp4 (default: assets/videos/docoga_short_YYYYMMDD.mp4)")
    ap.add_argument("--platform", default="YouTube Shorts")
    ap.add_argument("--tag", default="short", help="scratch frame dir suffix (/tmp/ms_<tag>)")
    ap.add_argument("--dry-run", action="store_true", help="print the solved spec, render nothing")
    args = ap.parse_args(argv)

    if args.date:
        day = date.fromisoformat(args.date)
    else:
        from zoneinfo import ZoneInfo
        day = datetime.now(ZoneInfo("Africa/Lagos")).date()
    topic = topic_for(day)
    out = Path(args.out) if args.out else default_output_path(day)

    if args.dry_run:
        reel = reel_from_topic(topic, out, platform=args.platform)
        for line in ms.solve_sizes(reel) + ms.solve_layout(reel) + ms.schedule(reel):
            print(line)
        for sc in reel["scenes"]:
            print("%s %-10s %4.1fs %-8s" % (sc["id"], sc["role"], sc["dur"], sc["trans"]),
                  " | ".join("%s:%s@%s" % (b["kind"], (b["lines"] or [b["text"]]), b["size"])
                             if b["kind"] not in ("badge", "button") else b["kind"]
                             for b in sc["beats"]))
        print("total %.2fs → %s" % (reel["total"], out))
        return 0
    path = render_topic(topic, out, tag=args.tag, platform=args.platform)
    print("video_path=%s" % path)
    print("topic=%s" % topic["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
