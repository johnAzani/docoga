"""site_analytics — the Cloudflare Web Analytics pull finds its own site tag and never hammers the API.

17 Oct 2026: the first live pull with a freshly minted CF_ANALYTICS_TOKEN came back
"unable to execute query, please try again later". The RUM dataset wants a *siteTag*
filter (the dashboard always sends one); these tests pin that the puller discovers it
without the owner typing anything, and that a transient refusal is retried once or twice,
never in a loop.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import site_analytics as sa  # noqa: E402

BEACON = ("<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
          "data-cf-beacon='{\"token\": \"0123456789abcdef0123456789abcdef\"}'></script>")
SITES = '{"result":[{"host":"docoga.com.ng","site_tag":"feedfacefeedfacefeedfacefeedface"}]}'
ENV = {"CLOUDFLARE_ACCOUNT_ID": "acc", "CF_ANALYTICS_TOKEN": "tok"}
OK = {"data": {"viewer": {"accounts": [{"total": [{"count": 100, "sum": {"visits": 40}}],
                                        "referers": [{"sum": {"visits": 30}, "dimensions": {"refererHost": "t.me"}}],
                                        "paths": [{"sum": {"visits": 40}, "dimensions": {"requestPath": "/"}}],
                                        "countries": [{"sum": {"visits": 38}, "dimensions": {"countryName": "NG"}},
                                                      {"sum": {"visits": 2}, "dimensions": {"countryName": "GB"}}]}]}}}


class SiteTagDiscovery(unittest.TestCase):
    def setUp(self):
        self._fetch, self._http, self._sleep = sa.fetch, sa.http, sa.time.sleep
        sa.time.sleep = lambda s: None

    def tearDown(self):
        sa.fetch, sa.http, sa.time.sleep = self._fetch, self._http, self._sleep

    def test_the_site_list_wins_when_the_token_may_read_it(self):
        sa.fetch = lambda url, token=None, timeout=15: (200, SITES) if "rum/site_info" in url else (200, BEACON)
        self.assertEqual(sa.discover_site_tag("acc", "tok"), "feedfacefeedfacefeedfacefeedface")

    def test_the_beacon_on_the_live_page_is_the_fallback(self):
        sa.fetch = lambda url, token=None, timeout=15: (403, "") if "rum/site_info" in url else (200, BEACON)
        self.assertEqual(sa.discover_site_tag("acc", "tok"), "0123456789abcdef0123456789abcdef")

    def test_no_tag_anywhere_still_queries_and_says_so(self):
        sa.fetch = lambda url, token=None, timeout=15: (0, "")
        seen = []
        sa.http = lambda token, body, timeout=40: (seen.append(body["variables"]["filter"]) or (200, OK))
        data, problem = sa.pull(env=ENV)
        self.assertIsNone(problem)
        self.assertNotIn("siteTag", seen[0])
        self.assertIsNone(data["site_tag"])

    def test_an_explicit_variable_skips_discovery(self):
        sa.fetch = lambda url, token=None, timeout=15: self.fail("discovery must not run when the tag is given")
        seen = []
        sa.http = lambda token, body, timeout=40: (seen.append(body["variables"]["filter"]) or (200, OK))
        data, problem = sa.pull(env=dict(ENV, CF_WEB_ANALYTICS_SITE_TAG="abc"))
        self.assertIsNone(problem)
        self.assertEqual(seen[0]["siteTag"], "abc")
        self.assertEqual(data["visits"], 40)
        self.assertEqual(data["by_channel"], {"telegram": 30})
        self.assertEqual(data["nigeria_share"], 0.95)   # Cloudflare answers ISO codes, not names

    def test_try_again_later_is_retried_but_bounded(self):
        sa.fetch = lambda url, token=None, timeout=15: (200, BEACON)
        calls = []
        sa.http = lambda token, body, timeout=40: (calls.append(1) or
                                                   (200, {"errors": [{"message": "unable to execute query, please try again later"}]}))
        data, problem = sa.pull(env=ENV)
        self.assertIsNone(data)
        self.assertEqual(len(calls), 3)
        self.assertIn("try again later", problem)
        self.assertIn("siteTag 012345", problem)

    def test_a_hard_refusal_is_not_retried(self):
        sa.fetch = lambda url, token=None, timeout=15: (0, "")
        calls = []
        sa.http = lambda token, body, timeout=40: (calls.append(1) or (403, {"errors": [{"message": "authentication error"}]}))
        data, problem = sa.pull(env=ENV)
        self.assertEqual(len(calls), 1)
        self.assertIn("Account Analytics: Read", problem)
        self.assertIn("set CF_WEB_ANALYTICS_SITE_TAG", problem)


if __name__ == "__main__":
    unittest.main()
