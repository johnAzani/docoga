#!/usr/bin/env python3
"""
WhatsApp forward pack — Law 47/49 growth asset.  Independence Day card:
'The 10 Rights Every Nigerian Tenant Has' — one clean forwardable image.

Brand laws: navy/white/yellow, typed DOCOGA kicker, no emoji, no logo, no glow.
"""
from PIL import Image, ImageDraw, ImageFont
import os

ROOT = '/home/user/docoga'
TTF  = f'{ROOT}/tools/fonts/Inter-Variable.ttf'
NAVY = (6, 26, 51); WHITE = (255, 255, 255); YELLOW = (255, 214, 0)
BLUE = (0, 64, 224); MUTED = (160, 176, 199); LINE = (28, 62, 107)

W, H = 1080, 1350

def F(size, weight=700):
    f = ImageFont.truetype(TTF, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f

RIGHTS = [
    "Exclusive possession — the place is yours for the tenancy",
    "Quiet enjoyment — privacy, no disturbances",
    "Written notice before the landlord enters",
    "A written agreement you can read before signing",
    "A receipt for every payment",
    "A valid written notice to quit before any eviction",
    "7 days notice before any court application",
    "Court order only — nobody throws you out himself",
    "Protection from excessive advance rent",
    "The right to challenge an unreasonable rent increase",
]

c = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(c)
M = 64  # margin

# header
d.text((M, 58), '66 YEARS OF INDEPENDENCE', font=F(34, 800), fill=YELLOW)
d.text((M, 106), 'THE 10 RIGHTS EVERY', font=F(74, 900), fill=WHITE)
d.text((M, 190), 'NIGERIAN TENANT HAS', font=F(74, 900), fill=WHITE)
d.rectangle([M, 292, M + 150, 300], fill=BLUE)

# rights list
y = 340
row_h = 84
for i, r in enumerate(RIGHTS, 1):
    d.ellipse([M, y + 10, M + 52, y + 62], fill=YELLOW)
    n = str(i)
    nf = F(30, 900)
    tw = d.textlength(n, font=nf)
    d.text((M + 26 - tw / 2, y + 22), n, font=nf, fill=NAVY)
    d.text((M + 78, y + 18), r, font=F(31, 600), fill=WHITE)
    if i < 10:
        d.rectangle([M, y + 74, W - M, y + 75], fill=LINE)
    y += row_h

# footer hook + CTA
y += 14
d.text((M, y), 'Most tenants cannot name ONE. Can you?', font=F(36, 800), fill=YELLOW)
y += 62
d.rectangle([M, y, W - M, y + 2], fill=LINE)
y += 24
d.text((M, y), 'Know all ten, in full — free guide:', font=F(30, 600), fill=MUTED)
y += 44
d.text((M, y), 'docoga.com.ng/tenant-rights-nigeria', font=F(38, 900), fill=WHITE)
y += 58
d.text((M, y), 'Free to start. No signup. No card.', font=F(28, 600), fill=MUTED)
y += 52
d.text((M, y), 'DOCOGA', font=F(30, 800), fill=MUTED)

# Save to both locations
for out_dir in [os.path.join(ROOT, 'site', 'social'), os.path.join(ROOT, 'renders')]:
    os.makedirs(out_dir, exist_ok=True)
    c.save(os.path.join(out_dir, 'forward-10-rights.jpg'), quality=92)

print('saved: site/social/forward-10-rights.jpg (1080x1350)')
print('saved: renders/forward-10-rights.jpg (1080x1350)')