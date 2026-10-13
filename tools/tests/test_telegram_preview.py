"""Reading a channel's own public preview — the guard that does not trust our bookkeeping.

`t.me/s/<name>` is server-rendered HTML, needs no token and no session, and lists the ~20
newest posts. The Bot API cannot read channel history (that limitation is why the committed
ledger exists at all), so this page is the only way to ask Telegram — rather than ourselves —
whether a message is already on the channel.

The fixture below is hand-authored, modelled on the public markup of a channel preview: a
`div` carrying `data-post="<channel>/<id>"` per message, the text in
`.tgme_widget_message_text`, and — the part that breaks naive matching — a **link-preview
card appended inside the same block**, plus `[text](url)` rewritten into an `<a href>` whose
URL lives in an attribute. Sandbox egress does not include t.me, so the parser is pinned to
this fixture instead of to live bytes; if Telegram renames a class, the block-split on
`data-post` still works, and if it changes more than that, the callers fail *open*.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import telegram_preview as tp  # noqa: E402

# The message as the poster holds it: MarkdownV2, escaped punctuation, an em dash, and a
# markdown link.
SOURCE = (
    r"Your landlord is holding your caution fee\? It is a \*\*security deposit\*\* — "
    r"not a gift\. Get a receipt for every payment: \[docoga\.com\.ng\]\(https://docoga\.com\.ng\)"
)

# The same message as the channel renders it: markup applied, the link turned into an anchor
# whose text is the domain, and a preview card bolted on inside the same block.
RENDERED = (
    '<div class="tgme_widget_message_text js-message_text" dir="auto">Your landlord is holding '
    "your caution fee? It is a <strong>security deposit</strong> — not a gift. Get a receipt for "
    'every payment: <a href="https://docoga.com.ng">docoga.com.ng</a></div>'
    '<div class="tgme_widget_message_link_preview">docoga.com.ng Caution Fee in Nigeria: Rules, '
    "Refunds &amp; Receipts (2026 Guide) — Free Template Is a caution fee refundable in Nigeria? "
    "How much should it be, what can a landlord deduct</div>"
    '<div class="tgme_widget_message_date"><time datetime="2026-10-07T06:22:00+00:00">07.10.2026</time></div>'
)

OTHER = (
    '<div class="tgme_widget_message_text">Notice to quit in Lagos: what a tenant must know about '
    "the six month rule and the court order that actually removes a person from a home.</div>"
)


def page(*blocks):
    return "".join(
        '<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="docogadaily/%d">%s</div></div>'
        % (30 + index, body) for index, body in enumerate(blocks, start=1)
    )


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class FakeFetch:
    """Scripts one page per call and records the URLs asked for."""

    def __init__(self, *pages):
        self.pages = list(pages)
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if not self.pages:
            raise AssertionError("asked for more pages than the test scripted: %s" % url)
        page_or_error = self.pages.pop(0)
        if isinstance(page_or_error, Exception):
            raise page_or_error
        return page_or_error


class Parsing(unittest.TestCase):
    def test_one_entry_per_message_id_with_the_readable_text(self):
        posts = tp.parse_preview(page(RENDERED, OTHER))
        self.assertEqual([message_id for _c, message_id, _t in posts], [31, 32])
        self.assertTrue(all(channel == "docogadaily" for channel, _i, _t in posts))

    def test_the_stored_text_is_readable_not_squeezed(self):
        """Tokens need separators; the squeezed form is only for containment."""
        block = tp.parse_preview(page(RENDERED))[0][2]
        self.assertIn("caution fee", block)
        self.assertNotIn("<div", block)

    def test_entities_are_decoded_and_breaks_survive(self):
        """`<br>` is the paragraph structure; folding it away would glue sentences together."""
        self.assertEqual(tp.to_readable('<div>a &amp; b<br/>c &quot;d&quot;</div>'), 'a & b\nc "d"')

    def test_the_link_preview_card_is_not_counted_as_our_words(self):
        """The card's title and description are the linked page's text, not ours."""
        body = ('<div class="tgme_widget_message_text">Our own sentence about tenancy in Ikeja.</div>'
                '<div class="tgme_widget_message_link_preview">Tenancy Law 2011 — full text of the '
                "principal act, with annotations and a table of contents for practitioners</div>")
        block = tp.parse_preview('<div data-post="docogadaily/5">%s</div>' % body)[0][2]
        self.assertIn("Our own sentence", block)
        self.assertNotIn("table of contents", block)

    def test_a_page_we_cannot_parse_reads_as_no_messages(self):
        self.assertEqual(tp.parse_preview(""), [])
        self.assertEqual(tp.parse_preview("<html><body>redirected to a login wall</body></html>"), [])

    def test_an_unfamiliar_wrapper_still_yields_the_message(self):
        """The block is cut on `data-post`, so a class rename cannot make us blind."""
        posts = tp.parse_preview('<span data-post="docogadaily/9">totally new markup about tenancy</span>')
        self.assertEqual(len(posts), 1)
        self.assertIn("totally new markup", posts[0][2])


class Matching(unittest.TestCase):
    def test_a_rendered_copy_of_our_message_matches_its_source(self):
        posts = tp.parse_preview(page(OTHER, RENDERED))
        self.assertEqual(tp.find(SOURCE, posts), ("docogadaily", 32))

    def test_the_url_scheme_is_not_allowed_to_break_the_match(self):
        """The anchor's href is stripped by the tag pass; our source still spells https://."""
        self.assertTrue(tp.is_duplicate(SOURCE, tp.to_readable(RENDERED)))

    def test_a_different_message_does_not_match(self):
        posts = tp.parse_preview(page(RENDERED))
        self.assertIsNone(tp.find(
            "Rent advances in Abuja are regulated differently and a tenant may deduct them from "
            "the next payment under a written agreement.", posts))

    def test_new_wording_next_to_familiar_words_is_not_a_duplicate(self):
        """A post that recycles a sentence and adds an angle must still be allowed out."""
        new_post = ("Your landlord is holding your caution fee? It is a security deposit. "
                    "Today: what the 2026 estate circular says about service charges, itemised.")
        self.assertFalse(tp.is_duplicate(new_post, tp.to_readable(RENDERED)))

    def test_a_message_whole_contained_in_an_older_post_is_a_repeat(self):
        """Deliberate: 'the channel already carries exactly these words' is the definition.

        A one-line follow-up whose entire wording sits inside a longer earlier post is refused
        on purpose — re-posting it does put the same words in front of the same readers. The
        escape hatch is TELEGRAM_FORCE, and the ledger's floors do the same job.
        """
        shared = "Your landlord is holding your caution fee? It is a security deposit — not a gift."
        longer = shared + " But today: a new angle on service charges, with figures for three estates."
        self.assertTrue(tp.is_duplicate(shared, longer))

    def test_a_link_written_twice_in_source_and_once_on_the_channel_still_matches(self):
        """MarkdownV2 spells `[docoga.com.ng](https://docoga.com.ng)`; the post shows it once.

        Counting repetitions would reject the exact duplicate this exists to catch, which is why
        the fallback comparison is a set of words and not a multiset.
        """
        self.assertTrue(tp.is_duplicate(SOURCE, tp.to_readable(RENDERED)))
        counts = tp.tokens(SOURCE)
        self.assertGreater(counts["docoga"], 1)  # proof the source really does repeat it

    def test_too_few_words_to_judge_is_not_a_match(self):
        self.assertFalse(tp.is_duplicate("ok thanks", tp.to_readable(RENDERED)))
        self.assertFalse(tp.is_duplicate("the your of and to for a is in", tp.to_readable(RENDERED)))

    def test_the_anchor_floor_governs_the_word_test_only(self):
        """Short words are not evidence *of similarity*; an exact embedded copy still is.

        The floor exists so a handful of common words cannot decide a refusal by accident. It
        does not switch off the exact containment path, which is a different claim: those
        sentences, in that order, are already sitting on the channel.
        """
        no_anchor = "the fee is not a gift my dear sir"
        self.assertFalse(tp.tokens(no_anchor) and len(max(set(tp.tokens(no_anchor)), key=len)) >= 6)
        self.assertFalse(tp.is_duplicate(no_anchor, "an unrelated post about estoppel certificates in Ibadan"))
        self.assertTrue(tp.is_duplicate(no_anchor, "the fee is not a gift my dear sir, and nothing else here"))

    def test_empty_and_none_text_never_match(self):
        self.assertFalse(tp.is_duplicate("", "anything"))
        self.assertFalse(tp.is_duplicate("anything", ""))
        self.assertIsNone(tp.find(SOURCE, []))
        self.assertIsNone(tp.find(SOURCE, None))


class Handles(unittest.TestCase):
    def test_an_at_name_becomes_the_handle(self):
        self.assertEqual(tp.channel_handle(chat_id="@docogadaily"), "docogadaily")

    def test_a_numeric_chat_id_has_no_public_preview(self):
        self.assertIsNone(tp.channel_handle(chat_id="-1001234567890"))

    def test_the_explicit_username_wins_over_the_chat_id(self):
        self.assertEqual(tp.channel_handle(chat_id="-1001234567890", configured="@backup"), "backup")

    def test_no_configuration_at_all_is_not_an_error(self):
        with patch.dict(tp.os.environ, {}, clear=True):
            self.assertIsNone(tp.channel_handle())


class Fetching(unittest.TestCase):
    def test_one_page_by_default_and_the_url_carries_no_secrets(self):
        fetch = FakeFetch(FakeResponse(page(RENDERED, OTHER)))
        with patch.object(tp, "fetch_preview", fetch):
            posts, error = tp.recent_posts(handle="docogadaily")
        self.assertIsNone(error)
        self.assertEqual(len(posts), 2)
        self.assertEqual(fetch.urls, ["https://t.me/s/docogadaily"])

    def test_paging_walks_backwards_from_the_oldest_id(self):
        fetch = FakeFetch(FakeResponse(page(RENDERED, OTHER)), FakeResponse(page("older text about rent")))
        with patch.object(tp, "fetch_preview", fetch):
            posts, error = tp.recent_posts(handle="docogadaily", pages=2)
        self.assertIsNone(error)
        self.assertEqual(len(posts), 3)
        self.assertEqual(fetch.urls[1], "https://t.me/s/docogadaily?before=31")

    def test_a_transport_error_is_reported_as_unknown_not_as_safe_to_post(self):
        fetch = FakeFetch(OSError("timed out"))
        with patch.object(tp, "fetch_preview", fetch):
            posts, error = tp.recent_posts(handle="docogadaily")
        self.assertIsNone(posts)
        self.assertIn("OSError", error)

    def test_a_non_200_is_unknown(self):
        with patch.object(tp, "fetch_preview", FakeFetch(FakeResponse("nope", status_code=503))):
            posts, error = tp.recent_posts(handle="docogadaily")
        self.assertIsNone(posts)
        self.assertIn("HTTP 503", error)

    def test_a_readable_but_empty_page_is_unknown(self):
        with patch.object(tp, "fetch_preview", FakeFetch(FakeResponse("<html>nothing</html>"))):
            posts, error = tp.recent_posts(handle="docogadaily")
        self.assertIsNone(posts)
        self.assertIn("no messages", error)

    def test_no_handle_is_reported_rather_than_fetched(self):
        fetch = FakeFetch(FakeResponse("x"))
        with patch.object(tp, "fetch_preview", fetch):
            posts, error = tp.recent_posts(handle=None, chat_id="-1001234567890")
        self.assertIsNone(posts)
        self.assertIn("not a public @username", error)
        self.assertEqual(fetch.urls, [])  # nothing was asked for, no request to leak into

    def test_the_fetch_has_a_timeout_and_a_browser_user_agent(self):
        import inspect
        source = inspect.getsource(tp.fetch_preview)
        self.assertIn("timeout=", source)
        self.assertIn("User-Agent", source)

    def test_describe_says_what_the_guard_can_see(self):
        with patch.object(tp, "fetch_preview", FakeFetch(FakeResponse(page(RENDERED, OTHER)))):
            state, detail = tp.describe(handle="docogadaily")
        self.assertEqual(state, "readable")
        self.assertIn("2 post(s)", detail)
        self.assertIn("31-32", detail)

    def test_describe_says_why_not(self):
        state, detail = tp.describe(handle=None, chat_id="-1001234567890")
        self.assertEqual(state, "unavailable")
        self.assertIn("ledger is the only duplicate guard", detail)


if __name__ == "__main__":
    unittest.main()
