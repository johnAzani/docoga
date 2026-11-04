#!/usr/bin/env python3
"""The follow loop — the Page asks, specifically, and the site points at the Page (4 Nov 2026).

Owner, 4 Nov 2026 (second pass): "research very very very in-depth … improve on what you think I
have not added to get more guaranteed results on Facebook … automated … ₦0."

What the Page had: 1 follower after five weeks of daily posts, Reels and Stories. What the
research says, consistently, about a Page at zero (audience.my May 2026, krumzi Sep 2026,
orichi Oct 2026, crescitaly Jun 2026, rafflepress Jul 2026):

  * Most Pages never ask. A **specific** follow line — "follow for [this thing] every [when]" —
    converts far better than "follow for more", on Reels and on posts alike; generic asks are
    noise. Facebook's engagement-bait rule is about "like/share/comment if…" — a plain follow
    line with a promise is not bait.
  * Reach only grows followers if the Page converts the visit: an empty About, no website, no
    username kill it before it starts (`tools/fb_page_audit.py` reads and, where the token may,
    fills those fields).
  * The owned surfaces must point at the Page: the site had 85 visits last week and **no
    visible link to any channel** — the only mention was JSON-LD `sameAs`. One footer line on
    every page fixes that for every visit from now on.

So this module is the one place that knows the Page's address and the follow lines, and the
copy generators call it:

    fb_follow.line(day)              # the dated follow ask for a feed post
    fb_follow.reel_line()            # the one for a Reel caption (evening cadence)
    fb_follow.append(message, day)   # the ask placed before the hashtag block, link line intact
    fb_follow.site_row()             # the footer HTML for the site

Deterministic per date, so a re-run writes the same post and the duplicate guards still work.
"""
from __future__ import annotations

import datetime as dt
import re

PAGE_USERNAME = "docoga.com.ng"                      # taken 26 Sep 2026 (FACEBOOK_AUTOMATION.md §1)
PAGE_ID = "102466208923830"
PAGE_URL = "https://www.facebook.com/%s" % PAGE_USERNAME
PAGE_URL_BY_ID = "https://www.facebook.com/%s" % PAGE_ID

CHANNELS = (
    ("Facebook", PAGE_URL),
    ("YouTube", "https://www.youtube.com/channel/UCeOzX7F7sYX-WchNJyBM2qA"),
    ("Telegram", "https://t.me/docogadaily"),
    ("Instagram", "https://www.instagram.com/docoga.ng/"),
    ("Threads", "https://www.threads.com/@docoga.ng"),
)

# Specific, dated rotation — what you get and when. Never "follow for more".
LINES = (
    "Follow DocOga for one rent rule for your state, every morning at 9:30.",
    "New here? Follow DocOga — a tenant-law rule for a Nigerian state every morning, and a 60-second video every evening.",
    "Follow DocOga so tomorrow's rule finds you: one state, one rule, every morning at 9:30.",
    "Follow DocOga for the next one — a rent rule every morning and a 9-minute Deep-Dive every fortnight.",
    "Follow DocOga for a daily rule on rent, receipts and quit notices, Lagos to Kano — 9:30 every morning.",
    "Follow DocOga and get the rule before the landlord does: one state's tenancy law, every morning.",
)
REEL_LINE = "Follow DocOga for the next rule — a new 60-second one every evening, and the law behind it every morning."
VIDEO_LINE = "Follow DocOga for the next Deep-Dive — one every fortnight, and a rent rule every morning at 9:30."

_HASHTAG_BLOCK = re.compile(r"\n\n(#\S+(?:[ \t]+#\S+)*)\s*$")


def line(day) -> str:
    """The follow ask for a feed post on `day` (date or ISO string) — the same every re-run."""
    day = day if isinstance(day, dt.date) else dt.date.fromisoformat(str(day)[:10])
    return LINES[day.toordinal() % len(LINES)]


def reel_line() -> str:
    return REEL_LINE


def video_line() -> str:
    return VIDEO_LINE


def has_ask(text) -> bool:
    return "follow docoga" in (text or "").lower() or "follow the page" in (text or "").lower()


def append(message, day, ask=None) -> str:
    """Place the follow ask before a trailing hashtag block (or at the end), once.

    The standalone link line the Facebook publisher moves to the first comment is left exactly
    where it is, so `fb_publish.split_link` still finds it."""
    text = (message or "").rstrip()
    if not text or has_ask(text):
        return message
    ask = ask or line(day)
    m = _HASHTAG_BLOCK.search(text)
    if m:
        return text[: m.start()] + "\n\n" + ask + "\n\n" + m.group(1)
    return text + "\n\n" + ask


def site_row(style="") -> str:
    """One footer line for every page of the site: the channels, Facebook first."""
    links = " · ".join('<a href="%s" target="_blank" rel="noopener">%s</a>' % (url, name) for name, url in CHANNELS)
    return '<div class="follow"%s>Follow DocOga for one rent rule a day: %s</div>' % (' style="%s"' % style if style else "", links)


if __name__ == "__main__":
    import sys
    today = dt.date.today()
    print(line(sys.argv[1] if len(sys.argv) > 1 else today))
    print(reel_line())
    print(site_row())
