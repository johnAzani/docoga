#!/usr/bin/env python3
"""tools/events_calendar.py — the special days DocOga marks, with a tenancy angle each
(owner, 23 Oct 2026: "Christmas, Independence Day, Children's Day, Democracy Day, Eid etc.")."""
import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import events_calendar as ec  # noqa: E402


class Dates(unittest.TestCase):
    def test_2026_matches_the_federal_governments_declarations(self):
        table = {r["slug"]: r for r in ec.year_table(2026)}
        self.assertEqual(table["new-year"]["date"], "2026-01-01")
        self.assertEqual(table["eid-el-fitr"]["date"], "2026-03-20")
        self.assertEqual(table["good-friday"]["date"], "2026-04-03")
        self.assertEqual(table["easter-monday"]["date"], "2026-04-06")
        self.assertEqual(table["workers-day"]["date"], "2026-05-01")
        self.assertEqual(table["childrens-day"]["date"], "2026-05-27")
        self.assertEqual(table["eid-el-kabir"]["date"], "2026-05-27")
        self.assertEqual(table["democracy-day"]["date"], "2026-06-12", "12 June since 2018 — never 29 May")
        self.assertEqual(table["eid-el-maulud"]["date"], "2026-08-25")
        self.assertEqual(table["independence-day"]["date"], "2026-10-01")
        self.assertEqual(table["world-habitat-day"]["date"], "2026-10-05", "first Monday of October")
        self.assertEqual(table["christmas"]["date"], "2026-12-25")
        self.assertFalse(any(r["approx"] for r in table.values()), "2026 is confirmed")
        self.assertNotIn("2026-05-29", {r["date"] for r in table.values()})

    def test_2027_is_pinned_but_provisional_and_other_years_fall_back_to_the_tabular_calendar(self):
        t27 = {r["slug"]: r for r in ec.year_table(2027)}
        self.assertEqual(t27["eid-el-fitr"]["date"], "2027-03-10")
        self.assertTrue(t27["eid-el-fitr"]["approx"], "projection until the Ministry declares it")
        self.assertEqual(t27["good-friday"]["date"], "2027-03-26")
        t25 = {r["slug"]: r for r in ec.year_table(2025)}
        # Nigeria observed Eid el-Fitr on 30/31 Mar 2025, Eid el-Kabir on 6 Jun, Maulud on 5 Sep:
        # the tabular calendar lands within a day of each, and says so.
        self.assertEqual(t25["eid-el-fitr"]["date"], "2025-03-31")
        self.assertEqual(t25["eid-el-kabir"]["date"], "2025-06-07")
        self.assertEqual(t25["eid-el-maulud"]["date"], "2025-09-05")
        self.assertTrue(all(t25[s]["approx"] for s in ("eid-el-fitr", "eid-el-kabir", "eid-el-maulud")))
        for year in (2028, 2029, 2030):
            slugs = {r["slug"] for r in ec.year_table(year)}
            self.assertTrue({"eid-el-fitr", "eid-el-kabir", "eid-el-maulud"} <= slugs, year)

    def test_easter_computus(self):
        self.assertEqual(ec.easter(2024), datetime.date(2024, 3, 31))
        self.assertEqual(ec.easter(2025), datetime.date(2025, 4, 20))
        self.assertEqual(ec.easter(2026), datetime.date(2026, 4, 5))
        self.assertEqual(ec.easter(2027), datetime.date(2027, 3, 28))


class Angles(unittest.TestCase):
    def test_every_event_is_a_tenancy_post_not_a_greeting_card(self):
        for slug, (name, kind, greeting, frame, lead, angle) in ec.EVENTS.items():
            self.assertGreaterEqual(len(angle.split()), 15, slug)
            self.assertTrue(any(w in angle.lower() for w in ("rent", "receipt", "notice", "agreement", "landlord", "tenan", "flat", "housing", "evict")), slug)
            self.assertNotRegex(angle, r"\bs\.\d", "%s: sections come from the law shelf, not the calendar" % slug)
            self.assertIn(kind, ("national", "religious", "observance", "housing"))
            self.assertIn(frame, ("", "flag"))
            self.assertLessEqual(len(greeting.split(" — ")[0]), 28, "fits the card's masthead")
        self.assertEqual({s for s, e in ec.EVENTS.items() if e[3] == "flag"}, {"democracy-day", "independence-day"},
                         "flag green is for the national days only (docs/BRAND_STYLE.md)")

    def test_the_brain_notes_carry_the_angle_the_greeting_rule_and_the_lead_in(self):
        notes = ec.brain_notes(datetime.date(2026, 10, 1))
        self.assertEqual(len(notes), 1)
        self.assertIn("Independence Day is today", notes[0])
        self.assertIn("'Happy Independence Day'", notes[0])
        self.assertIn("still teaches one rule with a fact id", notes[0])
        self.assertIn("Flag-green frame allowed", notes[0])
        lead = ec.brain_notes(datetime.date(2026, 12, 22))
        self.assertEqual(len(lead), 1)
        self.assertTrue(lead[0].startswith("Christmas Day is in 3 days"), lead[0])
        self.assertIn("Pack out before Christmas", lead[0])
        self.assertEqual(ec.brain_notes(datetime.date(2026, 10, 23)), [], "an ordinary day says nothing")
        sallah = ec.brain_notes(datetime.date(2027, 3, 10))
        self.assertIn("moon sighting", sallah[0])
        self.assertIn("this Sallah", sallah[0])
        habitat = ec.brain_notes(datetime.date(2026, 10, 5))
        self.assertIn("No greeting; the day is the angle.", habitat[0])

    def test_frame_event_prefers_the_national_day_when_two_fall_together(self):
        ev = ec.frame_event(datetime.date(2026, 5, 27))   # Children's Day and Eid el-Kabir
        self.assertIn(ev["slug"], ("childrens-day", "eid-el-kabir"))
        self.assertEqual(ec.frame_event(datetime.date(2026, 6, 12))["frame"], "flag")
        self.assertIsNone(ec.frame_event(datetime.date(2026, 10, 23)))
        up = ec.upcoming(datetime.date(2026, 12, 30), within=5)
        self.assertEqual([r["slug"] for r in up], ["new-year"], "December looks into the next year")

    def test_the_cli_prints_json(self):
        import io
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ec.main(["--date", "2026-12-25"])
        blob = json.loads(out.getvalue())
        self.assertEqual(blob["frame"]["slug"], "christmas")
        self.assertEqual(blob["events"][0]["greeting"], "Merry Christmas")


class Wiring(unittest.TestCase):
    def test_the_brain_reads_the_calendar_and_the_old_hard_coded_days_are_gone(self):
        import brain
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        self.assertIn("events_calendar.brain_notes(day)", src)
        self.assertNotIn("(5, 29)", src, "29 May has not been Democracy Day since 2018")
        notes = brain.calendar_notes(datetime.date(2026, 6, 12))
        self.assertTrue(any("Democracy Day is today" in n for n in notes), notes)

    def test_the_card_carries_the_greeting_in_the_masthead_and_the_flag_only_on_national_days(self):
        import social_card as sc
        ind = sc.event_for("2026-10-01")
        self.assertEqual(sc.event_kicker("DocOga · know your rights", ind), "DocOga · Happy Independence Day")
        self.assertEqual(ind["frame"], "flag")
        eid = sc.event_for("2026-03-20")
        self.assertEqual(sc.event_kicker("DocOga", eid), "DocOga · Eid Mubarak", "the Hausa half stays in the copy, not the masthead")
        self.assertEqual(eid["frame"], "")
        self.assertIsNone(sc.event_for("2026-10-23"))
        self.assertEqual(sc.event_kicker("DocOga · promo", None), "DocOga · promo")
        self.assertIsNone(sc.event_for("not-a-date"), "a bad date is never a missing card")
        src = (ROOT / "tools" / "social_card.py").read_text(encoding="utf-8")
        self.assertIn('event.get("frame") == "flag"', src)
        self.assertEqual(sc.FLAG_GREEN, (0, 135, 81))

    def test_the_dashboard_feed_lists_the_next_special_days(self):
        import dashboard_feed as df
        rows = df.events(datetime.datetime(2026, 12, 20, 9, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual([r["name"] for r in rows], ["Christmas Day", "Boxing Day", "New Year's Day"])
        self.assertEqual(rows[0]["in_days"], 5)
        today = df.events(datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(today[0]["in_days"], 0)
        self.assertEqual(today[0]["frame"], "flag")
        admin = (ROOT / "site" / "admin.html").read_text(encoding="utf-8")
        self.assertIn('id="events-next"', admin)
        self.assertIn("FEED.feed.events", admin)


if __name__ == "__main__":
    unittest.main()
