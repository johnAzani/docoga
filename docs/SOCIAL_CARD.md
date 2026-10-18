# The social card — Facebook, Instagram, Threads, Telegram (18 Oct 2026)

`tools/social_card.py` draws every static picture the four lanes post: the 4:5 feed card, the
9:16 Story frame and the carousel slides. On 18 Oct 2026 the card was redesigned to share the
Short cover's language (`docs/SHORT_COVER.md`), and the rotation copy behind it was rewritten
(`scripts/generate_telegram_content.py`). This note records why.

## 1. What the 2026 data says each channel rewards

| Channel | What decides it | Source of the number |
|---|---|---|
| Facebook | The first 40–80 characters (posts ≤ 80 chars earn ~66 % more engagement); photo posts beat link posts; a question or poll is the highest engagement per effort; the link belongs in the first comment | Hootsuite 2026 length study; Woobox; Buffer 52 M-post format study |
| Instagram | 4:5 takes 20 % more screen than square; the profile grid crops to the centre square; saves and sends outrank likes; carousels out-engage single images (0.50 % vs 0.33 %, Q2 2026) | Socialinsider Q2 2026; Mosseri (Jan 2025); adpicto/pineable carousel guides |
| Threads | Under 200 characters reads best; replies are the ranking signal (+42 % when the author replies); an image earns ~1.6× a text post | Hootsuite; Buffer 2026 |
| Telegram | The whole message is read; structure beats brevity; one link | our own channel data |

And for the picture itself (the same studies the Short cover drew on): one focal point, headline
2–3× the body, two type sizes, one accent colour used the same way on every piece, text inside
the centre square, legible at 200 px ("squint test"), no generic stock photography.

## 2. The design system

The same five devices as the cover, so a feed that recognises one recognises the other:

1. **Headline on stepped yellow slabs** — Inter Black in navy on `#FFC93C`, ≤ 3 lines, slabs 6 px
   apart as one block. A headline that cannot sit on three slabs at a size that out-weighs the
   body (≥ 1.6×) is set in white instead, and then there is no yellow on the card at all.
2. **Depth from a flat royal offset block** (`#0F3D7C`, 14 px behind the stack) — never a shadow,
   never a gradient (BRAND_STYLE §1/§4).
3. **The brand's marks as bullets** — `✅` lines get the green check, `❌` lines the red ✗
   (BRAND_STYLE §5), numbered lines a royal numeral chip, `A)`–`D)` poll options the same.
4. **The outlined chip** `FREE · docoga.com.ng` at the foot — inside the grid square.
5. **The tonal glyph** — the headline's first letter as a giant royal watermark bleeding off the
   bottom-right when there is no photograph (clipped out of a Story's chrome bands). With a
   photograph, a translucent navy band sits behind the type, its opacity chosen from the
   picture's brightness, so contrast never depends on the photo.

Plus a tracked small-caps kicker pinned to the top like a masthead (a carousel's `2 of 6`
becomes a `2 / 6` counter top-right), body in Inter Medium 40–54 px, film grain σ 2.2, and
everything between y 135 and 1215 on a 4:5 card — what Instagram's grid shows.

Layouts: `poster` (above), `stat` (the brain's `big` figure on the slab, headline in white under
it), `checklist` (body lines numbered). The Story frame uses the same plan with Facebook's
250 px chrome bands kept clear; the carousel slides share one kicker and one footer.

## 3. The copy

Every rotation template is now built the same way, and the card draws that shape:

* a **headline under 48 characters** carrying one specific tension — a number, a named section
  of law, a mistake the reader may be making right now ("No receipt is not a favour. It is a
  risk.", "Lagos: 6 months' notice for a yearly tenant.");
* a **body of one to five short lines** — `✅` for what to insist on, `❌` for what to refuse,
  numbers for a checklist, `A)`–`D)` for a poll — never a paragraph;
* a **question or one next step**, and the **link on its own last line** (Facebook moves it to the
  first comment; the card drops it — the chip already says where to go).

Rules kept: legal lines name their section and stay within what this repo has verified (Lagos
Tenancy Law 2011 s.4, s.5, s.13(1)); no statistic that cannot be cited; **no invented
customers** — the old "testimonial" quotes from people who do not exist are gone, replaced by
`Picture this:` scenarios plainly framed as scenarios. The brain's packs (`tools/brain.py`) are
unchanged; the rotation is what posts when the brain has nothing for the day.

Two lane fixes travelled with it: the Facebook rotation never repeats yesterday's words
(`generate_facebook_content.pick`), and the Threads lunch post says the same thing the Page says
that day. The Instagram caption now closes by asking for the two actions the ranking weighs — a
save and a send.

## 3b. Second pass (same evening) — what the first live card taught

The 1:10pm Threads card of 18 Oct 2026 was the first one the public saw. Three things came back:

* its kicker read **PIDGIN** — the workflow hands the raw post-type key to `--kicker`; the CLI
  now maps a bare key to the phrase (`DocOga · oya, make we talk`);
* greedy line breaks left one word alone on the third slab; slab headlines are now **balanced**
  (the break that makes the lines most even wins, ties to a longer first line);
* an en dash in a price range vanished (the drawable whitelist lacked `–`); `–`, `→`, `✓` draw.

And three content levers, each from the research table above: the rotation's **A)–D) questions
are real polls** now (a native Telegram poll under the post; the Threads poll in our reply under
the card — Facebook's and Threads' cheapest engagement in 2026); **nine-line lists set in two
columns** at a readable size instead of one tiny column; and Threads actually posts the card
again — every run since 17 Oct had dropped the image because one optional flag was refused
(`docs/INCIDENT_LOG.md`).

## 4. Checking it

`tools/tests/test_social_card_design.py`: slab geometry inside the grid square, yellow in one
place only, the 1.6× hierarchy, marks drawn only when the copy carries them, the squint test at
200 px, no blur/gradient/tilt in the source, every template's headline ≤ 50 characters and valid
MarkdownV2, no invented attributions, the repeat guard over 90 days.

To see a week: `python3 scripts/generate_facebook_content.py --date 2026-10-20 --print` renders
`assets/facebook/facebook_card_2026-10-20.jpg`; `python3 tools/social_card.py --text "…" --out
/tmp/card.jpg --story` draws the Story frame.
