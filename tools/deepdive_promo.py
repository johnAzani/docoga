#!/usr/bin/env python3
"""Every channel promotes the Deep-Dive — the words for Telegram, Facebook, Threads, Instagram.

    python3 tools/deepdive_promo.py show [--day YYYY-MM-DD]      # what each lane would say today

Owner, 17 Oct 2026: "remember to promote deep dives in the other social media channels."
Research the same day: a Facebook post whose body carries an external link reaches 60–80 % less
(and Pages are now capped at two body links a month without Meta Verified) — the link goes in
the first comment under a native card; Instagram's API cannot place a link sticker, so a
caption says where the episode lives and the bio carries the link; Threads reads a link in our
own reply; Telegram loves a button. Long-form views come from the audiences that already
follow us, not from a Short's 16 seconds — so the week after an episode goes public, every
lane names it once, in its own shape, and the Shorts trail it all fortnight.

The schedule, keyed on the day the episode became watchable (P):
  P      Threads evening (20:10 WAT, ~70 min after the 19:00 slot) — the launch, link in reply.
  P+1    Telegram 09:00 and Facebook 09:30 — the feature: card, hook, what you will learn, link.
  P+2    Threads lunch + Instagram (the same copy the Instagram lane reads) — "in case you missed it".
  P+1…P+14  Telegram posts carry a "▶ This week's Deep-Dive" button under the usual two rows;
         every Short without a published parent trails the latest episode (description + comment).

Nothing here needs the brain or Gemini: the words are the episode's own (title, chapter titles,
the hook sentence of its script), so a promo day costs ₦0 and cannot fail for quota. The lane
generators call `pack_for(day, channel)` and fall back to their normal post when it is None.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
LONGFORM_LEDGER = ROOT / "logs" / "youtube_longform.json"
EPISODES_DIR = ROOT / "episodes"
HOST = "https://docoga.com.ng"
LAGOS = ZoneInfo("Africa/Lagos")
WATCH = "https://www.youtube.com/watch?v=%s"
FOOTER_DAYS = 14
HOOK_MAX = 230
CHUNK = re.compile(r"^--- C(\d+) ---\s*$", re.M)
DISCLAIMER = "General information, not legal advice."
HASHTAGS = {"telegram": "#DocOga #DeepDive #TenantRights #Nigeria",
            "facebook": "#DocOga #DeepDive #TenantRights #Nigeria",
            "threads": "#TenantRightsNigeria",
            "instagram": "#DocOga #DeepDive #TenantRightsNigeria #RentNigeria #LandlordAndTenant"}

# Stage by (day − P) for each channel: the lane asks for its channel and gets None on other days.
STAGES = {"threads_evening": {0: "launch"}, "telegram": {1: "feature"}, "facebook": {1: "feature"},
          "threads": {2: "recap"}, "instagram": {2: "recap"}}


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _when(row):
    """The day the upload became watchable: publish_at's date (scheduled) else the ledger date."""
    text = str(row.get("publish_at") or "").strip()
    if text:
        try:
            when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
            return when.astimezone(LAGOS)
        except ValueError:
            pass
    try:
        return dt.datetime.combine(dt.date.fromisoformat(str(row.get("date"))[:10]), dt.time(19, 0), LAGOS)
    except (TypeError, ValueError):
        return None


def hook_of(script_path, limit=HOOK_MAX):
    """The first sentence or two of chunk C1, under `limit` characters, ending on a full stop."""
    try:
        text = Path(script_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    parts = CHUNK.split(text)
    first = " ".join(parts[2].split()) if len(parts) > 2 else " ".join(text.split())
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", first):
        if not sentence:
            continue
        if out and len(out) + 1 + len(sentence) > limit:
            break
        out = (out + " " + sentence).strip()
        if len(out) >= limit * 0.6:
            break
    return out[:limit].rstrip()


def latest(now=None, ledger=None, episodes_dir=None):
    """The newest watchable Deep-Dive with an episode folder, or None.

    Watchable = the ledger row has a video id, was not deleted, and is public/unlisted now
    (a scheduled upload counts once its publish_at has passed). Returns the episode's words."""
    now = now or dt.datetime.now(LAGOS)
    rows = _load(ledger or LONGFORM_LEDGER) or []
    try:
        import youtube_ledger
        gone = youtube_ledger.deleted_ids()
    except Exception:  # noqa: BLE001
        gone = set()
    episodes = {}
    for folder in sorted(Path(episodes_dir or EPISODES_DIR).glob("dd*")):
        meta = _load(folder / "episode.json")
        if meta and (folder / "script.txt").is_file():
            meta["_folder"] = folder
            for key in (str((meta.get("youtube") or {}).get("title") or "").strip(), str(meta.get("title") or "").strip()):
                if key:
                    episodes[key] = meta
    best = None
    for row in rows:
        if not isinstance(row, dict) or not row.get("video_id") or row["video_id"] in gone:
            continue
        if row.get("state") in ("rejected", "failed", "missing", "deleted"):
            continue
        when = _when(row)
        if when is None or when > now:
            continue
        if row.get("privacy") == "private" and not row.get("publish_at"):
            continue
        meta = episodes.get(str(row.get("title") or "").strip()) or episodes.get(str(row.get("topic") or "").strip())
        if not meta:
            continue
        if best is None or when > best[0]:
            best = (when, row, meta)
    if not best:
        return None
    when, row, meta = best
    sections = [str(s.get("title") or "").strip() for s in (meta.get("sections") or []) if isinstance(s, dict)]
    learn = [s for s in sections[1:-1] if s][:4]
    return {"id": meta["id"], "number": meta.get("number") or "", "title": str((meta.get("youtube") or {}).get("title") or meta.get("title")),
            "short_title": str(meta.get("title") or "").strip(),
            "url": row.get("url") or WATCH % row["video_id"], "video_id": row["video_id"],
            "page": "%s/videos/%s.html" % (HOST, meta["id"]), "published_on": when.date(), "privacy": row.get("privacy"),
            "learn": learn, "hook": hook_of(meta["_folder"] / "script.txt"), "tags": list((meta.get("youtube") or {}).get("tags") or [])}


def latest_link(now=None, **kw):
    """(title, url) of the latest watchable episode — the Shorts' fallback parent."""
    ep = latest(now, **kw)
    return (ep["title"], ep["url"]) if ep else None


def stage_for(day, channel, ep):
    if not ep:
        return None
    offset = (day - ep["published_on"]).days
    stage = STAGES.get(channel, {}).get(offset)
    if stage:
        return stage
    if channel == "telegram" and 1 <= offset <= FOOTER_DAYS:
        return "footer"
    return None


def _learn_lines(ep, bullet="•"):
    return "\n".join("%s %s" % (bullet, s) for s in ep["learn"])


def _page(ep, channel):
    try:
        import brain_drafts
        return brain_drafts.tag_links(ep["page"], channel)
    except Exception:  # noqa: BLE001
        return ep["page"]


def feature_text(ep, channel):
    minutes = "9 minutes"
    head = "🎬 New Deep-Dive (%s): %s" % (minutes, ep["title"])
    body = [head]
    if ep["hook"]:
        body.append(ep["hook"])
    if ep["learn"]:
        body.append("What you will learn:\n" + _learn_lines(ep))
    if channel == "telegram":
        body.append("▶ Watch on YouTube: %s\n📄 Prefer reading? The full transcript: %s" % (ep["url"], _page(ep, channel)))
        body.append("Forward this to someone paying rent this month.")
    elif channel == "facebook":
        body.append("Send this to someone who pays rent in cash.")
        body.append("Watch the full episode on YouTube:\n%s" % ep["url"])   # a standalone link line → the first comment
    body.append(DISCLAIMER + " " + HASHTAGS[channel])
    return "\n\n".join(body)


def launch_text(ep):
    """Threads, the evening the episode goes public: link-free body, link in our reply."""
    parts = ["New Deep-Dive, just published: %s" % ep["title"]]
    if ep["hook"]:
        parts.append(ep["hook"])
    if ep["learn"]:
        parts.append("Nine minutes on " + ", ".join(s.lower() for s in ep["learn"][:3]) + " — and what to do about it.")
    parts.append("Link in the reply. Which part do you want me to break down here first?")
    return "\n\n".join(parts)


def recap_text(ep, channel):
    """Two days on: 'in case you missed it' — Threads lunch and the Instagram caption."""
    parts = ["In case you missed it: %s" % ep["title"]]
    if ep["learn"]:
        parts.append("The nine-minute Deep-Dive covers:\n" + _learn_lines(ep))
    if channel == "instagram":
        parts.append("▶ Watch on YouTube — DocOga (link in bio). Prefer reading? The transcript is at docoga.com.ng/videos/%s.html" % ep["id"])
        parts.append("Send this to someone who pays rent in cash.")
        parts.append(DISCLAIMER + "\n\n" + HASHTAGS["instagram"])
    else:
        parts.append("Link in the reply. Save it for the next time rent comes up.")
    return "\n\n".join(parts)


def reply_text(ep):
    return "▶ The full episode, free (9 minutes): %s\n📄 Read it instead: %s" % (ep["url"], _page(ep, "threads"))


def card_text(ep):
    """The card: title + the chapter list, with the one fact a glance needs — nine minutes, YouTube."""
    lines = [ep["short_title"] or ep["title"]]          # the kicker already says "new deep-dive · 9 min"
    if ep["learn"]:
        lines.append("")
        lines += ["• " + s for s in ep["learn"]]
    lines += ["", "Watch on YouTube · DocOga"]
    return "\n".join(lines)


def telegram_button(ep):
    return [{"text": "▶ This week's Deep-Dive (9 min)", "url": ep["url"]}]


_UNSET = object()


def pack_for(day, channel, now=None, ep=_UNSET):
    """What `channel` should say on `day`, or None when it is a normal day for that lane.

    {"stage", "post_type", "text", "card_text", "reply_text", "ig_caption", "buttons", "episode"}"""
    day = day if isinstance(day, dt.date) else dt.date.fromisoformat(str(day)[:10])
    ep = latest(now) if ep is _UNSET else ep
    stage = stage_for(day, channel, ep)
    if not stage:
        return None
    out = {"stage": stage, "post_type": "deepdive", "episode": ep["id"], "title": ep["title"], "url": ep["url"],
           "card_text": card_text(ep), "reply_text": reply_text(ep), "buttons": [telegram_button(ep)]}
    if stage == "feature":
        out["text"] = feature_text(ep, channel)
    elif stage == "launch":
        out["text"] = launch_text(ep)
    elif stage == "recap":
        out["text"] = recap_text(ep, channel)
        out["ig_caption"] = recap_text(ep, "instagram")
    else:  # footer — the lane's own text, plus the button
        out["text"] = ""
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deep-Dive promotion words per channel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("--day", default="")
    args = ap.parse_args(argv)
    day = dt.date.fromisoformat(args.day) if args.day else dt.datetime.now(LAGOS).date()
    ep = latest()
    if not ep:
        print("PROMO_EPISODE=none")
        return 0
    print("PROMO_EPISODE=%s (%s, watchable since %s)" % (ep["id"], ep["title"], ep["published_on"]))
    for channel in ("threads_evening", "telegram", "facebook", "threads", "instagram"):
        pack = pack_for(day, channel, ep=ep)
        print("\n== %s: %s" % (channel, pack["stage"] if pack else "normal day"))
        if pack and pack.get("text"):
            print(pack["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
