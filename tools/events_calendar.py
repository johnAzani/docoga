#!/usr/bin/env python3
"""events_calendar.py — the Nigerian days DocOga marks, and what each one is *for*.

Owner, 23 Oct 2026: "Is there a possibility of integrating special events post to the contents
eg Christmas, Independence Day, Children's Day, Democracy Day, Eid etc." Yes — but a DocOga
event post is never a greeting card. Every event here carries a tenancy angle, because the day
is when the problem shows up: "pack out before Christmas" notices, Sallah travel and the
locked flat, January renewals after New Year. The brain gets the angle in its day context
(tools/brain.py calendar_notes), the card renderer gets the frame (tools/social_card.py: the
flag ribbon on national days, the greeting in the kicker), the dashboard gets the next dates.

Dates
  * Fixed days: New Year, Workers' Day, Children's Day, Democracy Day (12 June since 2018 —
    29 May is no longer the holiday), Independence Day, Christmas, Boxing Day.
  * Easter: Good Friday / Easter Monday from the Gregorian computus.
  * Islamic feasts (Eid el-Fitr, Eid el-Kabir, Eid el-Maulud): Nigeria declares them on
    moon sighting, so the dates the Federal Government announced or the press projects are
    PINNED per year below (2026 confirmed by the Ministry of Interior; 2027 provisional), and
    any other year falls back to the tabular Islamic calendar (±1–2 days) with `approx=True`
    so the copy says "this Sallah", never the date.
  * World Habitat Day / International Tenants' Day: first Monday of October.

    python3 tools/events_calendar.py --date 2026-12-25        # events on a day (JSON)
    python3 tools/events_calendar.py --year 2027              # the year's table
    python3 tools/events_calendar.py --next 60 [--date …]     # what is coming
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

FLAG_GREEN = (0, 135, 81)   # docs/BRAND_STYLE.md: event frames only

# slug: (name, kind, greeting, frame, lead_days, angle)
#   kind     national | religious | observance | housing
#   greeting the one line the post may open or close with ("" = none; still a normal post)
#   frame    "flag" draws the green-white-green ribbon on the card; "" leaves the card as is
#   lead     how many days before the day the brain may already build towards it
#   angle    the tenancy hook — the reason the day is ours to post about
EVENTS = {
    "new-year": ("New Year's Day", "national", "Happy New Year", "", 2,
                 "January is renewal month: a renewal is not a new tenancy, advance rent has legal limits "
                 "in several states, and the year's first payment deserves the year's first receipt."),
    "good-friday": ("Good Friday", "religious", "Happy Easter", "", 1,
                    "Easter travel: photograph the flat before you lock it, keep the agreement on your phone, "
                    "and no landlord may enter or change the locks while you are away."),
    "easter-monday": ("Easter Monday", "religious", "Happy Easter", "", 0,
                      "Back from Easter: check the flat against your photos; damage you did not cause is not "
                      "yours to pay for, and the caution fee covers damage, not holidays."),
    "eid-el-fitr": ("Eid el-Fitr", "religious", "Eid Mubarak — Barka da Sallah", "", 2,
                    "Sallah travel: the flat stays yours while you are away; photograph it, lock it, keep the "
                    "receipt and agreement on your phone. A landlord cannot re-let a room because you travelled."),
    "workers-day": ("Workers' Day", "national", "Happy Workers' Day", "", 1,
                    "The salary pays the rent; the receipt is the worker's proof. Rent paid in cash with no paper "
                    "is rent paid twice when there is a dispute."),
    "childrens-day": ("Children's Day", "observance", "Happy Children's Day", "", 1,
                      "A family's home: the agreement names who lives there, children included, and a landlord "
                      "may not lock a family out — eviction is a court order, never a padlock."),
    "eid-el-kabir": ("Eid el-Kabir", "religious", "Eid Mubarak — Barka da Sallah", "", 2,
                     "Sallah spending meets rent: pay the rent first and get the receipt; a landlord who says "
                     "'pay after Sallah' still owes you a receipt dated the day the money moved."),
    "democracy-day": ("Democracy Day", "national", "Happy Democracy Day", "flag", 1,
                      "The law is the tenant's vote: a receipt is a right, notice has a statutory "
                      "length, and the court — not the landlord — ends a tenancy."),
    "eid-el-maulud": ("Eid el-Maulud", "religious", "Happy Maulud", "", 1,
                      "A public holiday is not a grace period: rent due on a holiday is due the next working day, "
                      "and a receipt is due the day it is paid."),
    "world-habitat-day": ("World Habitat Day / International Tenants' Day", "housing", "", "", 2,
                          "The UN's housing day and the tenants' day fall together: one post on what adequate housing "
                          "means in Nigerian law — a written agreement, a receipt, notice before eviction."),
    "independence-day": ("Independence Day", "national", "Happy Independence Day", "flag", 2,
                         "Independence at home: a tenant who holds a receipt, an agreement and a dated notice cannot "
                         "be bullied. 1 October is the day to say what the law already gives you."),
    "christmas": ("Christmas Day", "religious", "Merry Christmas", "", 4,
                  "'Pack out before Christmas' is not a notice: a quit notice must be written, must give the "
                  "statutory months, and December does not shorten it. Travel: photograph, lock, keep "
                  "the papers on your phone."),
    "boxing-day": ("Boxing Day", "religious", "Merry Christmas", "", 0,
                   "Between Christmas and New Year the renewal letters arrive: a renewal is not a new tenancy, and "
                   "the increase must be agreed, not announced."),
}

FIXED = {
    "new-year": (1, 1), "workers-day": (5, 1), "childrens-day": (5, 27), "democracy-day": (6, 12),
    "independence-day": (10, 1), "christmas": (12, 25), "boxing-day": (12, 26),
}

# Islamic feasts as Nigeria observed / projects them (first day of the holiday).
# 2026: Ministry of Interior declarations (Eid el-Fitr 20 Mar; Eid el-Kabir 27 May; Maulud 25 Aug).
# 2027: provisional projections (Eid el-Fitr 10 Mar; Eid el-Kabir 16 May; Maulud 14 Aug).
PINNED = {
    2026: {"eid-el-fitr": (3, 20), "eid-el-kabir": (5, 27), "eid-el-maulud": (8, 25)},
    2027: {"eid-el-fitr": (3, 10), "eid-el-kabir": (5, 16), "eid-el-maulud": (8, 14)},
}
CONFIRMED_YEARS = {2026}   # the Federal Government declared these; later years are projections
HIJRI_FEASTS = {"eid-el-fitr": (10, 1), "eid-el-kabir": (12, 10), "eid-el-maulud": (3, 12)}


def easter(year):
    """Easter Sunday, Gregorian (Anonymous/Meeus algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _hijri_to_jd(y, m, d):
    """Tabular (Kuwaiti) Islamic calendar → Julian Day Number."""
    return (d + (29.5 * (m - 1)).__ceil__() + (y - 1) * 354 + (3 + 11 * y) // 30 + 1948439.5) - 1


def _jd_to_gregorian(jd):
    jd = int(jd + 0.5)
    a = jd + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return date(year, month, day)


def _hijri_year_for(gregorian_year):
    # 1 Muharram of the Hijri year that starts within or just before the Gregorian year.
    return int((gregorian_year - 622) * 33 / 32) + 1


def islamic_feasts(year):
    """{slug: (date, approx)} — pinned when Nigeria's dates are known, tabular otherwise."""
    out = {}
    pinned = PINNED.get(year, {})
    for slug, (hm, hd) in HIJRI_FEASTS.items():
        if slug in pinned:
            out[slug] = (date(year, *pinned[slug]), year not in CONFIRMED_YEARS)
            continue
        candidates = []
        for hy in range(_hijri_year_for(year) - 2, _hijri_year_for(year) + 3):
            g = _jd_to_gregorian(_hijri_to_jd(hy, hm, hd))
            if g.year == year:
                candidates.append(g)
        if candidates:
            out[slug] = (candidates[0], True)
    return out


def first_monday_of_october(year):
    d = date(year, 10, 1)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def year_table(year):
    """[{slug, name, kind, date, approx, greeting, frame, lead_days, angle}] sorted by date."""
    rows = {}
    for slug, (m, d) in FIXED.items():
        rows[slug] = (date(year, m, d), False)
    es = easter(year)
    rows["good-friday"] = (es - timedelta(days=2), False)
    rows["easter-monday"] = (es + timedelta(days=1), False)
    rows["world-habitat-day"] = (first_monday_of_october(year), False)
    rows.update(islamic_feasts(year))
    out = []
    for slug, (when, approx) in rows.items():
        name, kind, greeting, frame, lead, angle = EVENTS[slug]
        out.append({"slug": slug, "name": name, "kind": kind, "date": when.isoformat(), "approx": approx,
                    "greeting": greeting, "frame": frame, "lead_days": lead, "angle": angle})
    out.sort(key=lambda r: r["date"])
    return out


def events_on(day):
    """The events that fall on `day` (a date)."""
    return [r for r in year_table(day.year) if r["date"] == day.isoformat()]


def upcoming(day, within=7):
    """Events after `day` up to `within` days ahead, with `in_days`."""
    rows = year_table(day.year) + (year_table(day.year + 1) if day.month == 12 else [])
    out = []
    for r in rows:
        gap = (date.fromisoformat(r["date"]) - day).days
        if 0 < gap <= within:
            out.append(dict(r, in_days=gap))
    return out


def frame_event(day):
    """The one event that shapes the card on `day` (national/flag first), else None."""
    todays = events_on(day)
    if not todays:
        return None
    todays.sort(key=lambda r: (r["frame"] != "flag", r["kind"] != "national"))
    return todays[0]


def brain_notes(day):
    """Lines for the brain's day context: today's events with their angle and the rules, and the
    ones inside their lead window. Empty when nothing is near."""
    notes = []
    for r in events_on(day):
        rule = ("One greeting line at most — '%s' — as the opening or the closing line; the post still teaches "
                "one rule with a fact id. Flag-green frame allowed today." % r["greeting"]) if r["greeting"] else \
               "No greeting; the day is the angle."
        when = "today" if not r["approx"] else "today (date set by moon sighting — write 'this Sallah', never the date)"
        notes.append("%s is %s. Angle: %s %s" % (r["name"], when, r["angle"], rule))
    for r in upcoming(day, within=max(e[4] for e in EVENTS.values())):
        if r["in_days"] <= r["lead_days"]:
            notes.append("%s is in %d day%s%s — build towards it: %s" % (
                r["name"], r["in_days"], "" if r["in_days"] == 1 else "s",
                " (moon-sighting date; say 'this Sallah')" if r["approx"] else "", r["angle"]))
    return notes


def main(argv=None):
    ap = argparse.ArgumentParser(description="DocOga's Nigerian events calendar")
    ap.add_argument("--date", help="YYYY-MM-DD (default today, Lagos)")
    ap.add_argument("--year", type=int, help="print the whole year's table")
    ap.add_argument("--next", type=int, metavar="DAYS", help="events in the next DAYS days")
    a = ap.parse_args(argv)
    if a.date:
        day = date.fromisoformat(a.date)
    else:
        from datetime import datetime, timezone
        day = datetime.now(timezone(timedelta(hours=1))).date()
    if a.year:
        rows = year_table(a.year)
    elif a.next:
        rows = upcoming(day, a.next)
    else:
        rows = {"date": day.isoformat(), "events": events_on(day), "frame": frame_event(day), "brain_notes": brain_notes(day)}
    json.dump(rows, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
