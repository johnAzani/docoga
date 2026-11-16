"""The money metre, tested on both sides of every threshold.

Two kinds of test here. The pure ones feed the ledger shapes the worker actually returns — a
28-day series plus today's counters, and visits that only arrive as 7- and 28-day totals — because
the failure that matters is silent: a brief that reads ₦0 because of a parsing mistake looks
exactly like a business that sold nothing.

The stage order is pinned deliberately. The funnel is only useful if the *first* empty step is the
one named: "rewrite the checkout" is advice for a business with traffic, and this one has 13 visits
a day.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import money  # noqa: E402


def payload(today="2026-11-16", series=None, today_row=None, site=None, price=2000):
    return {"data": {"ok": True, "date": today, "priceNGN": price,
                     "today": today_row if today_row is not None else {"sold": 1, "rev": 2000},
                     "snapshot": {"series": series if series is not None else [
                         {"date": "2026-11-14", "sold": 0, "rev": 0},
                         {"date": "2026-11-15", "sold": 2, "offline": 1, "rev": 4000, "bizpaid": 1, "bizrev": 25000},
                     ]}},
            "site": site if site is not None else {"ok": True, "connected": True,
                                                   "visits7": 91, "visits28": 364,
                                                   "pageviews7": 96, "pageviews28": 380,
                                                   "top_paths": [{"path": "/tenancy-agreement-nigeria", "visits": 30}],
                                                   "by_channel": {"direct": 40, "search": 51}}}


def ledger_of(*rows):
    return {"days": list(rows)}


class RowsFromTheDashboard(unittest.TestCase):
    def test_the_series_and_today_become_one_row_per_day(self):
        rows = money.rows_from(payload())
        self.assertEqual([row["date"] for row in rows], ["2026-11-14", "2026-11-15", "2026-11-16"])
        self.assertEqual(rows[-1]["revenue"], 2000)

    def test_offline_and_manual_sales_are_money_too(self):
        """The owner closes sales on WhatsApp; the worker counts them separately and they are real."""
        rows = money.rows_from(payload())
        self.assertEqual(rows[1]["passes"], 3, "2 sold + 1 offline")
        self.assertEqual(rows[1]["revenue"], 29000, "₦4,000 passes + ₦25,000 business")

    def test_todays_counters_win_over_the_series_on_the_same_day(self):
        rows = money.rows_from(payload(today="2026-11-15", today_row={"sold": 9, "rev": 18000}))
        self.assertEqual(rows[-1]["revenue"], 18000)

    def test_visits_are_stamped_on_the_day_they_were_read_and_only_then(self):
        rows = money.rows_from(payload())
        self.assertEqual(rows[-1]["visits_7d"], 91)
        self.assertNotIn("visits_7d", rows[0])

    def test_a_disconnected_site_api_is_not_a_zero(self):
        """`connected: false` must not read as 'nobody visited' — that is the wrong diagnosis."""
        rows = money.rows_from(payload(site={"ok": True, "connected": False}))
        self.assertNotIn("visits_7d", rows[-1])

    def test_no_site_at_all_is_still_a_ledger(self):
        rows = money.rows_from({"data": {"date": "2026-11-16", "today": {"sold": 0}, "snapshot": {}}, "site": {}})
        self.assertEqual(len(rows), 1)
        self.assertNotIn("visits_7d", rows[0])


class TheLedger(unittest.TestCase):
    def test_a_re_run_replaces_the_day_instead_of_double_counting_it(self):
        first = money.merge({"days": []}, [{"date": "2026-11-16", "revenue": 2000},
                                          {"date": "2026-11-15", "revenue": 0}])
        second = money.merge(first, [{"date": "2026-11-16", "revenue": 4000}])
        self.assertEqual([row["date"] for row in second["days"]], ["2026-11-15", "2026-11-16"])
        self.assertEqual(second["days"][-1]["revenue"], 4000)

    def test_a_row_that_only_carries_visits_keeps_the_counters_of_its_day(self):
        base = money.merge({"days": []}, [{"date": "2026-11-16", "revenue": 2000, "passes": 1}])
        merged = money.merge(base, [{"date": "2026-11-16", "visits_7d": 70}])
        self.assertEqual(merged["days"][0]["revenue"], 2000)
        self.assertEqual(merged["days"][0]["visits_7d"], 70)

    def test_the_ledger_is_capped(self):
        rows = [{"date": "2026-01-%02d" % day, "revenue": 0} for day in range(1, 29)]
        out = money.merge({"days": []}, rows)
        self.assertLessEqual(len(out["days"]), money.KEEP_DAYS)

    def test_a_damaged_ledger_reads_as_empty_rather_than_crashing(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{not json")
            path = handle.name
        try:
            self.assertEqual(money.load_ledger(path), {"days": []})
        finally:
            os.unlink(path)


class Windows(unittest.TestCase):
    def test_totals_count_only_the_window(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 2000, "passes": 1},
                           {"date": "2026-11-10", "revenue": 500, "passes": 1},
                           {"date": "2026-09-01", "revenue": 99999, "passes": 9})
        week = money.totals(ledger, 7, "2026-11-16")
        self.assertEqual(week["revenue"], 2500)
        self.assertEqual(week["passes"], 2)
        month = money.totals(ledger, 28, "2026-11-16")
        self.assertEqual(month["revenue"], 2500, "1 September is outside 28 days")

    def test_visits_per_day_uses_the_latest_reading_available(self):
        ledger = ledger_of({"date": "2026-11-15", "visits_7d": 70},
                           {"date": "2026-11-16", "revenue": 0})
        self.assertEqual(money.visits_per_day(ledger), (10.0, 7))

    def test_a_28_day_only_reading_divides_by_28(self):
        self.assertEqual(money.visits_per_day(ledger_of({"date": "2026-11-16", "visits_28d": 280})), (10.0, 28))


class Stages(unittest.TestCase):
    """The first empty step of the funnel is the one named."""

    def test_a_ledger_with_no_rows_says_it_is_blind_not_that_it_sold_nothing(self):
        found = money.diagnosis({"days": []}, "2026-11-16")
        self.assertEqual(found["stage"], "unmeasured")
        self.assertIn("DOCOGA_ADMIN_PASSPHRASE", found["action"])

    def test_money_today_is_earning_whatever_yesterday_did(self):
        found = money.diagnosis(ledger_of({"date": "2026-11-16", "revenue": 2000, "passes": 1}), "2026-11-16")
        self.assertEqual(found["stage"], "earning")
        self.assertEqual(found["revenue_today"], 2000)

    def test_a_full_day_is_at_target(self):
        found = money.diagnosis(ledger_of({"date": "2026-11-16", "revenue": 5000}), "2026-11-16", target=5000)
        self.assertEqual(found["stage"], "at-target")

    def test_sales_last_month_and_none_this_week_is_a_renewal_gap(self):
        ledger = ledger_of({"date": "2026-11-01", "revenue": 2000, "passes": 1},
                           {"date": "2026-11-16", "revenue": 0, "visits_7d": 700})
        found = money.diagnosis(ledger, "2026-11-16")
        self.assertEqual(found["stage"], "renewal-gap")
        self.assertIn("renewal", found["action"].lower())

    def test_traffic_without_a_sale_is_the_offer_not_the_traffic(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 0, "visits_7d": 700,
                            "top_paths": [{"path": "/notice-to-quit-lagos", "visits": 40}]})
        found = money.diagnosis(ledger, "2026-11-16")
        self.assertEqual(found["stage"], "offer-unseen")
        self.assertIn("/notice-to-quit-lagos", found["action"])
        self.assertIn("2,000", found["action"])

    def test_almost_no_traffic_is_named_as_no_traffic_rather_than_a_conversion_problem(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 0, "visits_7d": 91})
        found = money.diagnosis(ledger, "2026-11-16")
        self.assertEqual(found["stage"], "no-traffic")
        self.assertIn("13", found["action"], "91 visits in 7 days is 13 a day — say the number")

    def test_visits_that_cannot_be_read_are_said_not_guessed(self):
        found = money.diagnosis(ledger_of({"date": "2026-11-16", "revenue": 0}), "2026-11-16")
        self.assertEqual(found["stage"], "no-traffic-data")
        self.assertIn("Web Analytics", found["action"], "name the thing that is missing")

    def test_channel_tagged_sales_name_the_channel(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 2000,
                            "sources": {"sales": {"instagram": 2, "facebook": 1}}})
        found = money.diagnosis(ledger, "2026-11-16")
        self.assertIn("instagram", found["action"])


class TheArithmetic(unittest.TestCase):
    def test_the_visits_a_target_needs(self):
        self.assertEqual(money.required_visits(5000, 2000, 0.01), 250)
        self.assertEqual(money.required_visits(5000, 2000, 0.02), 125)
        self.assertEqual(money.required_visits(5000, 25000, 0.01), 20)

    def test_a_zero_conversion_does_not_divide_by_zero(self):
        self.assertGreater(money.required_visits(5000, 2000, 0), 0)


class TheBrief(unittest.TestCase):
    def ledger(self):
        return ledger_of({"date": "2026-11-15", "revenue": 0, "passes": 0, "visits_7d": 91, "price": 2000},
                         {"date": "2026-11-16", "revenue": 0, "passes": 0, "price": 2000})

    def test_it_carries_the_three_numbers_the_stage_and_one_action(self):
        text = money.brief(self.ledger(), "2026-11-16")
        self.assertIn("**7 days:** ₦0", text)
        self.assertIn("**Stage: `no-traffic`**", text)
        self.assertIn("**Today's one action:**", text)
        self.assertIn("**The arithmetic:**", text)

    def test_a_problem_is_printed_not_hidden(self):
        text = money.brief(self.ledger(), "2026-11-16", problems=["visits: /admin/site answered 500"])
        self.assertIn("Not measured: visits: /admin/site answered 500", text)

    def test_an_empty_ledger_still_renders(self):
        text = money.brief({"days": []}, "2026-11-16")
        self.assertIn("unmeasured", text)

    def test_the_machine_lines_the_workflow_greps_are_exactly_these(self):
        found = money.diagnosis(self.ledger(), "2026-11-16")
        lines = money.machine_lines(found)
        keys = [line.split("=", 1)[0] for line in lines]
        self.assertEqual(keys, ["MONEY_TODAY", "MONEY_7D", "MONEY_28D", "MONEY_TARGET",
                                "MONEY_STAGE", "MONEY_VISITS_PER_DAY"])
        self.assertIn("MONEY_STAGE=no-traffic", lines)


class PullWithoutTheNetwork(unittest.TestCase):
    def test_no_passphrase_is_a_named_problem_not_a_crash(self):
        found, problems = money.pull(passphrase="", http=lambda *a, **k: (0, {}))
        self.assertIsNone(found)
        self.assertIn("DOCOGA_ADMIN_PASSPHRASE", problems[0])

    def test_a_refused_login_is_reported_with_its_status(self):
        calls = []

        def fake(method, url, body=None, headers=None, timeout=30):
            calls.append((method, url))
            return 401, {"ok": False, "error": "bad_pass"}

        found, problems = money.pull(passphrase="wrong", http=fake)
        self.assertIsNone(found)
        self.assertIn("401", problems[0])

    def test_a_successful_pull_logs_out(self):
        def fake(method, url, body=None, headers=None, timeout=30):
            if url.endswith("/admin/login"):
                return 200, {"ok": True, "token": "tok"}
            if url.endswith("/admin/data"):
                return 200, payload()["data"]
            if url.endswith("/admin/site"):
                return 200, payload()["site"]
            return 200, {"ok": True}

        found, problems = money.pull(passphrase="right", http=fake)
        self.assertIsNotNone(found)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()


class CheckoutTaps(unittest.TestCase):
    """The worker tags checkout taps and verified sales by channel, per ISO week. They are the only
    numbers that say *where* a buyer came from, and they must survive the trip into the ledger."""

    def test_weekly_source_counters_become_channel_totals(self):
        now = "2026-11-16"
        this_week = money._iso_week(now)
        last_week = money._iso_week(now, 1)
        old_week = money._iso_week(now, 6)
        payload = {"data": {"date": now, "priceNGN": 2000, "today": {"sold": 0}, "snapshot": {
            "series": [], "sources": {
                "checkout": {this_week: {"instagram": 3}, last_week: {"facebook": 2}, old_week: {"search": 9}},
                "sale": {last_week: {"instagram": 1}}}}}, "site": {}}
        row = money.rows_from(payload)[-1]
        self.assertEqual(row["sources"]["checkouts"], {"search": 9, "instagram": 3, "facebook": 2})
        self.assertEqual(row["sources"]["checkouts_7d"], 5, "this week + last week only")
        self.assertEqual(row["sources"]["checkouts_28d"], 14)
        self.assertEqual(row["sources"]["sales"], {"instagram": 1})

    def test_taps_that_never_complete_are_named_as_a_payment_leak(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 0, "visits_7d": 700,
                            "sources": {"checkouts_7d": 4}})
        found = money.diagnosis(ledger, "2026-11-16")
        self.assertEqual(found["stage"], "checkout-broken")
        self.assertIn("admin/codes", found["action"])

    def test_small_sales_to_real_buyers_are_a_ticket_problem_not_a_traffic_problem(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 0, "passes": 0, "visits_7d": 700},
                           {"date": "2026-11-15", "revenue": 4000, "passes": 2})
        found = money.diagnosis(ledger, "2026-11-16", target=5000)
        self.assertEqual(found["stage"], "converting-weak")
        self.assertIn("Business", found["action"])

    def test_taps_with_a_sale_in_the_same_week_are_not_broken(self):
        ledger = ledger_of({"date": "2026-11-16", "revenue": 0, "visits_7d": 700,
                            "sources": {"checkouts_7d": 4}},
                           {"date": "2026-11-15", "revenue": 2000, "passes": 1})
        self.assertNotEqual(money.diagnosis(ledger, "2026-11-16")["stage"], "checkout-broken")
