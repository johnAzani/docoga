#!/usr/bin/env python3
"""Read a public Telegram channel's own web preview.

Why this exists in `tools/` instead of living inside the poster: two different things need
to answer the same question — "what is already on the channel, according to Telegram?" — and
they must not answer it with two parsers. The poster asks before it sends, to refuse a
duplicate its ledger never heard about. `tools/telegram_preflight.py` asks before the owner
trusts that guard, to say whether the channel can be read at all.

The Bot API cannot read channel history (that limitation is the reason the committed ledger
exists), but every *public* channel serves a server-rendered preview at `t.me/s/<name>`: the
~20 newest posts, plain HTML, no token, no session, no login. One GET a day costs nothing.

Private channels and numeric chat ids have no preview, and that is a fact about the
deployment, not an error: the caller must say "unavailable" rather than guess.
"""

import os
import re
from collections import Counter

try:
    import requests
except ImportError:  # the preflight runs before `pip install` — stdlib must be enough
    requests = None
import urllib.error
import urllib.request

from telegram_mdv2 import to_plain

PREVIEW_BASE = os.getenv("TELEGRAM_PREVIEW_BASE", "https://t.me/s/")
PREVIEW_TIMEOUT = 15
PREVIEW_UA = "Mozilla/5.0 (compatible; docoga-automation/1.0; +https://docoga.com.ng)"

_HTML_TAG = re.compile(r"<[^>]+>")
_HTML_ENTITIES = (
    ("<br/>", "\n"), ("<br />", "\n"), ("<br>", "\n"),
    ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
    ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"), ("&#8212;", "—"), ("&mdash;", "—"),
)
# A message "matches" when its letters and digits agree, in order, with nothing else left
# over. That is what makes our MarkdownV2 source and the rendered channel post comparable:
# markup, escapes, entities, tags and whitespace are gone from both sides, and a URL with
# `_` in it still lines up with itself.
_MATCH_CHARS = re.compile(r"[^a-z0-9]+")
_TOKEN = re.compile(r"[a-z0-9]+")
_DATA_POST = re.compile(r'data-post="([^"/]+)/([0-9]+)"')
# A channel post carries the link *text* while our MarkdownV2 source carries the link *and*
# its URL, so the two sides disagree by "https" and nothing else. Ignoring the scheme on both
# sides is what makes a rendered post comparable to the message that produced it.
_URL_NOISE = {"https", "http", "www"}
# How little evidence is enough to refuse a post on. A message of six short common words can
# appear inside somebody else's sentence by accident; a real re-post of our daily content is
# dozens of tokens with a long one in it. Below this the guard abstains and the ledger decides.
MIN_DISTINCT_TOKENS = 6
MIN_ANCHOR_LENGTH = 6
# The message body, so the comparison is against what was *written* rather than against the
# link-preview card Telegram bolts onto the same block (title, description, site name — none
# of it our words). Absent that class, `parse_preview` falls back to the whole block, which
# is looser but never blind: a class rename degrades to "unverified", not to "safe to re-post".
_MESSAGE_TEXT = re.compile(
    r'class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)(?=<div class="[^"]*tgme_widget_message_(?:link_preview|wrap)|$)',
    re.S | re.I)


def tokens(text):
    """The multiset of words, without URL noise. Order-free and markup-free."""
    return Counter(tok for tok in _TOKEN.findall(to_readable(text).lower())
                   if tok not in _URL_NOISE)


def is_duplicate(ours, theirs):
    """Would a reader see this exact message twice?

    Containment first (the cheap, exact case), then an order-independent multiset subset:
    Telegram rewrites `[docoga.com.ng](https://…)` into an anchor and appends a link-preview
    card with its own words, so the rendered post is a *superset* of the message in an order
    that need not match. Requiring every one of our tokens to be present — and a real anchor
    word, and enough distinct tokens to mean something — is what keeps that superset test from
    turning into "sounds similar".
    """
    our_norm = normalize_for_match(ours)
    if not our_norm:
        return False
    if our_norm in normalize_for_match(theirs):
        return True
    # A *set*, not a multiset: our MarkdownV2 writes a link twice (`[docoga.com.ng](https://
    # docoga.com.ng)`) and the channel shows it once, so counting repetitions would reject the
    # very duplicates this exists to catch.
    need, have = set(tokens(ours)), set(tokens(theirs))
    if len(need) < MIN_DISTINCT_TOKENS:
        return False
    if len(max(need, key=len)) < MIN_ANCHOR_LENGTH:
        return False
    return need <= have


def channel_handle(chat_id=None, configured=None):
    """The public @name for a chat, or None when no preview can exist.

    Only `@username` chats are readable; `-100…` numeric ids have no preview URL.
    `configured` (TELEGRAM_CHANNEL_USERNAME) wins, because the operator may point the
    poster at a numeric id while still wanting the guard to read the public name.
    """
    handle = (configured if configured is not None
              else os.environ.get("TELEGRAM_CHANNEL_USERNAME", "")).strip()
    if handle:
        return handle.lstrip("@")
    chat = str(chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    return chat[1:] if chat.startswith("@") else None


def to_readable(text):
    """Markup and tags gone, words still separated — the form worth *reading*.

    `to_plain` is the MarkdownV2 stripper the poster already uses for its plain-text
    fallback, so there is exactly one idea in the repo of what markup means.
    """
    if not text:
        return ""
    # Entities first, tags second: `<br/>` is a tag *and* a line break, and stripping tags
    # first would silently fold every paragraph of a channel post into one long line.
    for needle, replacement in _HTML_ENTITIES:
        text = text.replace(needle, replacement)
    return to_plain(_HTML_TAG.sub(" ", text)).strip()


def normalize_for_match(text):
    """Everything a rendered post and a MarkdownV2 source can agree on: letters and digits,
    in order, nothing else. Used for the exact containment path; token comparison uses
    `to_readable`, because a run of letters with no separators cannot be counted as words.
    """
    return _MATCH_CHARS.sub("", to_readable(text).lower())


def parse_preview(html):
    """[(channel, message_id, readable_text)] oldest first — the page's own order.

    Splitting on `data-post` instead of matching nested markup is deliberate: Telegram's
    preview classes have been stable for years, but a check that survives a class rename is
    worth more here than a precise one that dies quietly. A page with no `data-post` reads
    as "no messages", and every caller treats that as unknown, never as "safe to re-post".

    The text kept is the message body, not the whole block: a link-preview card inside the
    same block contributes a title and a description that were never ours to write, and
    counting them as "our words" is how a guard starts refusing legitimate posts.
    """
    if not html:
        return []
    marks = list(_DATA_POST.finditer(html))
    posts = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(html)
        block = html[mark.start():end]
        body = _MESSAGE_TEXT.search(block)
        # The *readable* form is stored, not the squeezed form: a message is matched both by
        # exact containment and by counting words, and a run of letters with no separators is
        # useless for the second one.
        posts.append((mark.group(1), int(mark.group(2)),
                      to_readable(body.group(1) if body else block)))
    return posts


class _Fetched:
    """The two attributes the reader uses, so urllib and requests look the same."""
    __slots__ = ("status_code", "text")

    def __init__(self, status_code, text):
        self.status_code, self.text = status_code, text


def fetch_preview(url):
    """One GET. Its own function so a test can script a page without a network.

    `requests` when it is installed (the poster's path); plain urllib when it is not — the
    workflow deliberately runs the preflight BEFORE `pip install`, so this module has to
    work with the standard library alone (13 Oct 2026: it did not, and the preflight died
    with ModuleNotFoundError before asking Telegram a single question)."""
    if requests is not None:
        return requests.get(url, timeout=PREVIEW_TIMEOUT, headers={"User-Agent": PREVIEW_UA})
    req = urllib.request.Request(url, headers={"User-Agent": PREVIEW_UA})
    try:
        with urllib.request.urlopen(req, timeout=PREVIEW_TIMEOUT) as resp:
            return _Fetched(resp.status, resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return _Fetched(exc.code, "")


def recent_posts(handle=None, pages=1, chat_id=None):
    """(posts, error). `posts` is None only when nothing at all could be read.

    Paging walks backwards with `?before=<lowest id>` — one request per page. The default
    single page is ~20 posts, which is three weeks of a daily lane and comfortably longer
    than the four-hours window the 3 Oct 2026 duplicates arrived in.
    """
    handle = handle or channel_handle(chat_id=chat_id)
    if not handle:
        return None, "the chat is not a public @username, so there is no preview to read"
    posts, errors = [], []
    before = None
    for _page in range(max(1, int(pages or 1))):
        url = "%s%s" % (PREVIEW_BASE, handle)
        if before:
            url += "?before=%d" % before
        try:
            response = fetch_preview(url)
        except Exception as exc:  # any transport problem is "unknown", never "duplicate"
            errors.append("%s: %s" % (type(exc).__name__, str(exc)[:120]))
            break
        status = getattr(response, "status_code", 0)
        if status != 200:
            errors.append("HTTP %s" % (status or "?"))
            break
        found = parse_preview(getattr(response, "text", "") or "")
        if not found:
            errors.append("the page carried no messages")
            break
        posts.extend(found)
        ids = [message_id for _c, message_id, _t in found]
        if before and min(ids) >= before:
            break
        before = min(ids)
    if not posts:
        return None, "; ".join(errors) or "unreadable"
    return posts, None


def find(message, posts):
    """The newest channel post that already carries this message, or None.

    Never similarity: a template that reuses a fixed paragraph across weeks must keep
    posting, and only an identical message is the accident worth refusing. Each post's
    *whole block* is passed in, because the link-preview card Telegram appends belongs to it.
    """
    for channel, message_id, text in reversed(posts or []):
        if is_duplicate(message, text):
            return channel, message_id
    return None


def describe(handle=None, pages=1, chat_id=None):
    """One sentence for a human: is the live guard even possible, and what does it see?"""
    handle = handle or channel_handle(chat_id=chat_id)
    if not handle:
        return ("unavailable", "no public @username for this chat, so t.me/s/ cannot be read "
                               "and the ledger is the only duplicate guard")
    posts, error = recent_posts(handle=handle, pages=pages)
    if error:
        return "unavailable", "%s — %s" % (handle, error)
    newest = max(message_id for _c, message_id, _t in posts)
    oldest = min(message_id for _c, message_id, _t in posts)
    return ("readable", "%d post(s) visible at t.me/s/%s (ids %s-%s, newest %s)"
            % (len(posts), handle, oldest, newest, newest))
