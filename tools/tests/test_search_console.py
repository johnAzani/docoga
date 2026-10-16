"""tools/search_console.py — Google's queries as a channel, with the missing-scope case named."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import search_console as scn  # noqa: E402


class R(object):
    def __init__(self, status, body):
        self.status_code, self._b, self.text = status, body, json.dumps(body)

    def json(self):
        return self._b


class FakeHttp(object):
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def request(self, method, url, headers=None, data=None, params=None, files=None):
        body = json.loads(data or "{}")
        self.calls.append((url, body))
        return self.answer(url, body)


def rows(*items):
    return {"rows": [{"keys": list(k), "clicks": c, "impressions": i, "ctr": c / i if i else 0, "position": p} for k, c, i, p in items]}


class SearchConsoleTests(unittest.TestCase):
    def test_a_domain_property_is_read_nigeria_first_and_striking_distance_is_ranked(self):
        def answer(url, body):
            self.assertIn("sc-domain%3Adocoga.com.ng", url)
            self.assertEqual(body["dataState"], "final")
            dims = body.get("dimensions")
            if dims == ["country"]:
                return R(200, rows((("nga",), 200, 8000, 7.0), (("gbr",), 10, 1000, 12.0)))
            if dims == ["query", "page"]:
                self.assertEqual(body["dimensionFilterGroups"][0]["filters"][0]["expression"], "nga")
                return R(200, rows((("tenancy agreement sample nigeria", "https://docoga.com.ng/tenancy-agreement-nigeria.html"), 60, 2000, 4.2),
                                   (("notice to quit lagos", "https://docoga.com.ng/notice-to-quit-lagos.html"), 3, 800, 9.1),
                                   (("rent receipt format", "https://docoga.com.ng/rent-receipt-format-nigeria.html"), 1, 15, 11.0),
                                   (("caution fee refund", "https://docoga.com.ng/caution-fee-nigeria.html"), 0, 300, 18.4)))
            return R(200, rows((("https://docoga.com.ng/",), 90, 3000, 6.0)))
        data, state, _ = scn.pull(FakeHttp(answer), days=28, today=date(2026, 10, 19))
        self.assertEqual(state, "ok")
        self.assertEqual(data["window"], {"start": "2026-09-18", "end": "2026-10-16", "days": 28}, "ends three days ago: Google finalises late")
        self.assertEqual((data["clicks"], data["impressions"], data["nigeria_clicks"]), (210, 9000, 200))
        self.assertEqual(data["top_queries"][0]["query"], "tenancy agreement sample nigeria")
        self.assertEqual([q["query"] for q in data["striking_distance"]], ["notice to quit lagos", "caution fee refund"],
                         "positions 5–20 with ≥20 impressions, biggest first; position 4.2 is already page one")

    def test_a_token_without_the_scope_is_named_not_a_red_run(self):
        http = FakeHttp(lambda url, body: R(403, {"error": {"code": 403, "message": "Request had insufficient authentication scopes.",
                                                            "status": "PERMISSION_DENIED"}}))
        data, state, detail = scn.pull(http, today=date(2026, 10, 19))
        self.assertIsNone(data)
        self.assertEqual(state, "missing-scope")
        self.assertIn("scopes", detail)
        self.assertEqual(len(http.calls), 1, "no point asking the second property shape")

    def test_the_url_prefix_property_is_tried_when_the_domain_property_is_not_ours(self):
        def answer(url, body):
            if "sc-domain" in url:
                return R(403, {"error": {"message": "User does not have sufficient permission for site 'sc-domain:docoga.com.ng'."}})
            if body.get("dimensions") == ["country"]:
                return R(200, rows((("nga",), 5, 100, 8.0)))
            return R(200, {"rows": []})
        data, state, _ = scn.pull(FakeHttp(answer), today=date(2026, 10, 19))
        self.assertEqual(state, "ok")
        self.assertEqual(data["site"], "https://docoga.com.ng/")
        self.assertEqual(data["striking_distance"], [])


if __name__ == "__main__":
    unittest.main()
