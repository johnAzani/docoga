#!/usr/bin/env python3
"""
Design D6 story frames (2) + carousel C1 slides (5) — Sunday 27 Sep.
House style: navy #061A33, panel #0F3D7C, blue #4A8CFF, yellow #FFC93C, Inter.
Laws: no emoji, no slide numbers, typed DOCOGA kicker, nothing key top-right of
slide 1, swipe cue bottom-right, FREE trio, ₦2,000 confident yellow underline.
"""
from PIL import Image, ImageDraw, ImageFont
import os

NAVY, PANEL, BLUE, YELLOW, WHITE = (6,26,51), (15,61,124), (74,140,255), (255,201,60), (255,255,255)
SOFT = (207,224,255)
FD = "/usr/share/fonts/opentype/inter"

def F(w, s):
    return ImageFont.truetype(f"{FD}/Inter-{w}.otf", s)

OUT = "social"
os.makedirs(OUT, exist_ok=True)

def kicker(d, x, y, txt="DOCOGA", col=BLUE, size=34, track=10):
    f = F("Bold", size)
    cx = x
    for ch in txt:
        d.text((cx, y), ch, font=f, fill=col)
        cx += d.textlength(ch, font=f) + track
    return cx

def wrapped(d, x, y, txt, f, col, maxw, lh):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    for i, l in enumerate(lines):
        d.text((x, y + i*lh), l, font=f, fill=col)
    return y + len(lines)*lh

def swipe(d, W, H):
    f = F("Bold", 30)
    t = "swipe  →"
    w = d.textlength(t, font=f)
    d.text((W - w - 60, H - 100), t, font=f, fill=SOFT)

def rule(d, x, y, w, col=YELLOW, h=8):
    d.rectangle([x, y, x+w, y+h], fill=col)


# ────────────────────── Stories 1080×1920 ──────────────────────
def story(fname, head, head_size, sub, band_lines):
    W, H = 1080, 1920
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    # ambient panels
    d.rounded_rectangle([60, 1500, 1020, 1780], 26, fill=PANEL)
    d.ellipse([-220, -260, 340, 300], outline=(15,61,124), width=3)
    kicker(d, 90, 130)
    kicker(d, 90, 176, "NIGERIAN DOCUMENTS", SOFT, 22, 8)
    y = wrapped(d, 90, 460, head, F("Black", head_size), WHITE, 900, int(head_size*1.14))
    rule(d, 90, y + 36, 240)
    wrapped(d, 90, y + 110, sub, F("Regular", 42), SOFT, 880, 58)
    # bottom band content
    f1 = F("Bold", 46)
    f2 = F("Regular", 33)
    ty = 1560
    for i, (txt, col, f) in enumerate(band_lines):
        d.text((130, ty), txt, font=f, fill=col)
        ty += (66 if i == 0 else 52)
    swipe(d, W, H)
    im.save(f"{OUT}/{fname}", quality=92)
    print("rendered", fname)


story("d6a-oneline.jpg",
      "The line every landlord hopes you never read.",
      96,
      "It is one sentence long — and it decides who keeps your caution fee after you pack out.",
      [("THE 5 PROTECTIONS — FULL 2026 GUIDE", YELLOW, F("Bold", 46)),
       ("Free to read today. Link in bio.", SOFT, F("Regular", 33)),
       ("docoga.com.ng", WHITE, F("Bold", 33))])

story("d6b-protect5.jpg",
      "5 protections. 2 minutes. ₦0.",
      100,
      "Set them up on payment day — and your caution fee stops being a gift.",
      [("RECEIPT IT · CLAUSE IT · DEADLINE IT", YELLOW, F("Bold", 44)),
       ("RECORD IT · LIST IT", YELLOW, F("Bold", 44)),
       ("Caution-fee receipt generator — FREE to start.", SOFT, F("Regular", 33)),
       ("No signup. No card. docoga.com.ng", WHITE, F("Bold", 33))])


# ────────────────────── Carousel 1080×1350 ──────────────────────
CW, CH = 1080, 1350

def slide(fname, head, head_size, body_fn, swipe_on=True, band=None):
    im = Image.new("RGB", (CW, CH), NAVY)
    d = ImageDraw.Draw(im)
    kicker(d, 80, 90)
    kicker(d, 80, 132, "CAUTION FEE 2026", SOFT, 20, 8)
    y = wrapped(d, 80, 260, head, F("Black", head_size), WHITE, 900, int(head_size*1.15))
    rule(d, 80, y + 30, 200)
    body_fn(d, y + 100)
    if band:
        d.rounded_rectangle([70, 1120, 1010, 1290], 24, fill=PANEL)
        f = F("Bold", 34)
        d.text((110, 1150), band[0], font=f, fill=band[1])
        d.text((110, 1200), band[2], font=F("Regular", 28), fill=SOFT)
    if swipe_on:
        swipe(d, CW, CH)
    im.save(f"{OUT}/{fname}", quality=92)
    print("rendered", fname)


def s1_body(d, y):
    wrapped(d, 80, y, "The 2026 answer — in 5 slides.", F("Regular", 46), SOFT, 880, 62)
    wrapped(d, 80, y + 180,
            "Built on Lagos Tenancy Law 2011, the FCT Recovery of Premises Act and current market practice.",
            F("Regular", 32), SOFT, 880, 46)

slide("c1-s1.jpg", "Can your landlord keep your caution fee?", 84, s1_body,
      band=("THE ANSWER IS INSIDE →", YELLOW, "Swipe — it takes 30 seconds."))


def s2_body(d, y):
    wrapped(d, 80, y, "No. A caution fee is not rent.", F("Bold", 56), WHITE, 900, 74)
    wrapped(d, 80, y + 130,
            "It is a refundable security deposit — money held against damage, not the landlord's income.",
            F("Regular", 40), SOFT, 880, 58)
    wrapped(d, 80, y + 340,
            "At the end of the tenancy, only genuine, documented deductions may be held back. The rest must come back to you.",
            F("Regular", 40), SOFT, 880, 58)

slide("c1-s2.jpg", "It is not rent.", 84, s2_body)


def s3_body(d, y):
    items = [("Damage beyond fair wear and tear", "with photos or an itemised repair cost"),
             ("Unpaid rent", "arrears at handover"),
             ("Unpaid bills", "light, water, service charge — if you owed them")]
    ty = y
    for head, sub in items:
        d.ellipse([84, ty + 14, 112, ty + 42], fill=YELLOW)
        wrapped(d, 150, ty, head, F("Bold", 44), WHITE, 820, 56)
        wrapped(d, 150, ty + 58, sub, F("Regular", 32), SOFT, 820, 44)
        ty += 150
    wrapped(d, 80, ty + 30,
            "Everything else is refundable. Repainting normal wear is NOT deductible.",
            F("Bold", 36), YELLOW, 900, 50)

slide("c1-s3.jpg", "He may only deduct:", 80, s3_body)


def s4_body(d, y):
    steps = ["Receipt it separately from rent",
             "Write the refund clause in",
             "Fix a refund deadline",
             "Photograph every room at move-in",
             "Demand itemised deductions only"]
    ty = y
    for i, s in enumerate(steps, 1):
        d.text((84, ty), f"0{i}", font=F("Black", 48), fill=BLUE)
        wrapped(d, 190, ty + 6, s, F("Bold", 40), WHITE, 800, 52)
        ty += 100
    wrapped(d, 80, ty + 20,
            "Five lines of paperwork beat one long argument.",
            F("Regular", 32), SOFT, 900, 46)

slide("c1-s4.jpg", "The 5 protections on payment day", 72, s4_body)


def s5_body(d, y):
    wrapped(d, 80, y,
            "Caution-fee receipt with proper refund terms — generated on your phone.",
            F("Regular", 40), SOFT, 880, 58)
    wrapped(d, 80, y + 190,
            "FREE to start. No signup. No card.",
            F("Bold", 46), WHITE, 880, 62)
    d.text((80, y + 320), "docoga.com.ng", font=F("Black", 52), fill=WHITE)
    # confident yellow underline on the pass price — never struck
    f = F("Bold", 40)
    d.text((80, y + 420), "Oga Pass ₦2,000 / 30 days — all 9 tools", font=f, fill=SOFT)
    w = d.textlength("Oga Pass ₦2,000 / 30 days — all 9 tools", font=f)
    d.rectangle([80, y + 468, 80 + w, y + 474], fill=YELLOW)
    wrapped(d, 80, y + 510,
            "Full 2026 guide: docoga.com.ng/caution-fee-nigeria",
            F("Regular", 30), SOFT, 880, 42)

slide("c1-s5.jpg", "Get it back. Guaranteed by paperwork.", 72, s5_body, swipe_on=False)
print("ALL 7 ASSETS DONE")