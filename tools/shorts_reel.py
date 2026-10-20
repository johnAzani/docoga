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
    tip × 4     "TIP n OF 4" kicker + green check badge + cascade + support   whip / flash alternating
    conclusion  wordpop "FREE." + button + support + disclaimer kicker   dissolve

v5 (20 Oct 2026, owner: "text motion graphics as the voice-over speaks, smooth camera
movements, images that explain what is being said per time"): once the narrator has read,
every sentence gets its own photograph (shot_plan → `_shots`, a camera move each, cross-
dissolved) and its words (shorts_sound.sync_words) so the captions light word by word.

No icon grid, no name cycler (those need social/assets/icon-*.png), no strike
(nothing here is an external price). Palette and typeface come from the engine
constants — there is deliberately no colour or font literal in this file.

Run:  python3 tools/shorts_reel.py [--date YYYY-MM-DD] [--out PATH] [--dry-run]
"""

import argparse
import json
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
SHORTS_LEDGER = Path(__file__).resolve().parents[1] / "logs" / "youtube_published.json"


def series_kicker(ledger=SHORTS_LEDGER, env=None):
    """`DOCOGA · TENANT TIPS · No. 7` — the episode number as a returning-viewer cue on the cover
    (18 Oct 2026, fourth pass). Numbered series read as a show, not a one-off, and the number is
    the one thumbnail element that changes every day without touching the system. Counted from
    the YouTube ledger: distinct published / scheduled Shorts + 1. `SHORTS_SERIES_NO` overrides;
    `SHORTS_SERIES_NO=off` keeps the plain kicker. No ledger → plain kicker."""
    env = os.environ if env is None else env
    raw = str(env.get("SHORTS_SERIES_NO", "")).strip().lower()
    if raw == "off":
        return SERIES_KICKER
    if raw.isdigit():
        return "%s · No. %d" % (SERIES_KICKER, int(raw))
    try:
        rows = json.loads(Path(ledger).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SERIES_KICKER
    seen = {r.get("video_id") for r in rows if isinstance(r, dict)
            and r.get("video_id") and str(r.get("state", "")).lower() in ("published", "scheduled", "listed")}
    return "%s · No. %d" % (SERIES_KICKER, len(seen) + 1) if seen else SERIES_KICKER
CTA_SUPPORT = "Free tenant documents. No signup."
DISCLAIMER_KICKER = "GENERAL INFO · RULES VARY BY STATE"
FOLLOW_KICKER = "FOLLOW " + HANDLE.upper()

DEFAULT_OUTPUT_DIR = ROOT / "assets" / "videos"


def tip_counter(i, n):
    """`TIP 2 OF 4`; the last one says so — the payoff is announced, not discovered."""
    return ("LAST TIP · %d OF %d" if i == n - 1 else "TIP %d OF %d") % (i + 1, n)


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
    hook_beats = [ms.Beat("kicker", "kicker", series_kicker(), size=30, y=470, color=ms.FAINT)]
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
                # The step counter is the retention cue: a viewer who knows there are four, and
                # that this is the second, stays for the other two (20 Oct 2026). Listed last with
                # its own t0 so the badge → cascade chain, and the scene's length, are untouched.
                ms.Beat("kicker", "kicker", tip_counter(i, len(tips)), size=28, y=392, color=ms.FAINT,
                        t0=0.02, exempt=True, why="a glance label, not a line to read"),
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


def shot_plan(reel, topic):
    """[(scene, [(t0, t1, text), …])] — one shot per spoken sentence of each hook/tip scene,
    from the caption beats the voice timed (shorts_sound.caption_beats); a scene with no
    captions (no voice, or a one-line read) is one shot for the whole scene, asked for in the
    narrator's words. The picture changes when the sentence does — "images that explain what
    the voice-over is saying per time" (owner, 20 Oct 2026)."""
    plan = []
    for sc, text, chain in shots_for(reel, topic):
        caps = sorted((b for b in sc["beats"] if b["kind"] == "caption"), key=lambda b: b["t0"])
        if caps:
            plan.append((sc, [(float(b["t0"]), float(b["t1"]), b["text"]) for b in caps]))
        else:
            plan.append((sc, [(0.0, float(sc["dur"]), text)]))
    return plan


def attach_shots(reel, topic):
    """Put matched CC0 photographs behind each hook/tip scene — one per spoken sentence (`_shots`,
    each W×H brand duotone with its own camera move; `_bg`/`_bg_raw` stay the scene's first shot
    for the cover) — owner, 17 Oct 2026: free images behind the cards, matching what is being
    said; 20 Oct 2026: per sentence, with a camera. A sentence whose picture cannot be found
    keeps the shot before it (or the navy); the Short is never late because of a photo. Returns
    the number of scenes that got at least one photograph (SHOTS_HITS)."""
    import shot_match
    if not shot_match.enabled():
        return 0
    import brain_visual
    hits, k, n_shots = 0, 0, 0
    for sc, spans in shot_plan(reel, topic):
        shots, last_query = [], None
        for t0, t1, text in spans:
            raw = {}

            def _treat(im, size, raw=raw):
                raw["img"] = im           # the untreated photograph — the cover treats it its own way
                return brain_visual.treat(im, size, darken=SHOT_DARKEN)
            chain = shot_match.query_chain(text, hint=sc.get("shot"))
            if shots and chain[0] == last_query:
                shots[-1]["t1"] = t1       # same subject, same picture: let the camera keep moving
                continue
            img, note = shot_match.photo_for(text, hint=sc.get("shot"), size=(ms.W, ms.H), treat=_treat)
            if img is None:
                if shots:
                    shots[-1]["t1"] = t1
                print("  · scene %s %.1f–%.1fs keeps the shot before it (%s)" % (sc["id"], t0, t1, note))
                continue
            last_query = chain[0]
            shots.append(dict(t0=t0, t1=t1, img=img, raw=raw.get("img"), move=ms.CAM_MOVES[k % len(ms.CAM_MOVES)],
                              query=note.get("query")))
            k += 1
            print("  📷 scene %s %.1f–%.1fs ← %s (%s) · camera %s" % (sc["id"], t0, t1, note.get("query"),
                                                                   note.get("license") or "cc0", shots[-1]["move"]))
        sc["shot"] = shot_match.query_chain(spans[0][2], hint=sc.get("shot"))[0]
        if shots:
            shots[0]["t0"] = 0.0           # the first picture is there from the cut, before the voice
            sc["_shots"] = shots
            sc["_bg"] = shots[0]["img"]
            if shots[0].get("raw") is not None:
                sc["_bg_raw"] = shots[0]["raw"]
            hits += 1
            n_shots += len(shots)
        else:
            print("  · scene %s stays navy" % sc["id"])
    print("SHOTS_TOTAL=%d" % n_shots)   # machine line: photographs across the Short
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


def title_for(script):
    """The YouTube title for a rotation script — the searchable subject first, the hook after
    (generate_short_video.yt_title). Words only, through the bridge, like topic_for."""
    import generate_short_video as words
    return words.yt_title(script)


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
            shorts_sound.sync_words(clips)             # WORDSYNC=vosk|estimate — when each word is said
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
