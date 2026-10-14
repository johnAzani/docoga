"""tools/yt_stats.py — the channel's numbers, pulled read-only, so decisions rest on data."""

import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    import yt_stats
    import yt_publish
    OK = True
except ImportError:
    OK = False


class R:
    def __init__(self, code, body):
        self.status_code, self._b, self.text = code, body, json.dumps(body)

    def json(self):
        return self._b


class FakeHttp:
    """Scripted Data API + Analytics API. `analytics` picks the analytics outcome."""
    token = "t"

    def __init__(self, analytics="forbidden"):
        self.analytics = analytics
        self.calls = []

    def request(self, method, url, params=None, **kw):
        self.calls.append((method, url, dict(params or {})))
        if url.endswith("/channels"):
            return R(200, {"items": [{"id": "UC1", "snippet": {"title": "DocOga"},
                                      "statistics": {"subscriberCount": "12", "viewCount": "340", "videoCount": "3"},
                                      "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if url.endswith("/playlistItems"):
            return R(200, {"items": [{"contentDetails": {"videoId": "LONG1"}}, {"contentDetails": {"videoId": "SHORT1"}}]})
        if url.endswith("/videos"):
            items = []
            for i in params["id"].split(","):
                items.append({"id": i, "snippet": {"title": "T-" + i, "publishedAt": "2026-10-14T10:00:00Z"},
                              "status": {"privacyStatus": "unlisted" if i == "LONG1" else "public"},
                              "contentDetails": {"duration": "PT9M58S" if i == "LONG1" else "PT45S"},
                              "statistics": {"viewCount": "7" if i == "LONG1" else "120", "likeCount": "1", "commentCount": "0"}})
            return R(200, {"items": items})
        if "youtubeanalytics" in url:
            if self.analytics == "forbidden":
                return R(403, {"error": {"code": 403, "message": "insufficient scope"}})
            if params.get("dimensions") == "video":
                return R(200, {"columnHeaders": [{"name": n} for n in ("video", "views", "estimatedMinutesWatched",
                                                                        "averageViewDuration", "averageViewPercentage",
                                                                        "subscribersGained", "likes", "comments", "shares")],
                               "rows": [["LONG1", 7, 40, 343, 57.3, 2, 1, 0, 0]]})
            return R(200, {"rows": [["YT_SEARCH", 80], ["SHORTS", 40]]})
        return R(404, {})


@unittest.skipUnless(OK, "requests not installed")
class SnapshotTests(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 14, 12, tzinfo=dt.timezone.utc)

    def snap(self, http):
        with patch.object(yt_publish, "authorize", return_value=(http, {})), \
             patch.object(yt_stats, "ledger_ids", return_value={"LONG1": {"lane": "longform", "title": "x", "published": "2026-10-14", "topic": "Caution"}}):
            return yt_stats.snapshot(days=28, now=self.NOW)

    def test_data_api_numbers_land_even_without_the_analytics_scope(self):
        http = FakeHttp("forbidden")
        snap = self.snap(http)
        self.assertEqual(snap["channel"]["subscribers"], 12)
        ids = {v["id"]: v for v in snap["videos"]}
        self.assertEqual(ids["LONG1"]["kind"], "longform")
        self.assertEqual(ids["LONG1"]["lane"], "longform")
        self.assertEqual(ids["SHORT1"]["kind"], "short")
        self.assertEqual(ids["LONG1"]["seconds"], 598)
        self.assertIn("yt-analytics.readonly", snap["analytics_note"])
        self.assertTrue(all(c[0] == "GET" for c in http.calls), "read-only: never anything but GET")

    def test_analytics_enriches_when_the_scope_is_there(self):
        snap = self.snap(FakeHttp("ok"))
        ids = {v["id"]: v for v in snap["videos"]}
        self.assertEqual(ids["LONG1"]["analytics"]["averageViewDuration"], 343)
        self.assertEqual(snap["traffic"], {"YT_SEARCH": 80, "SHORTS": 40})
        self.assertIsNone(snap["analytics_note"])

    def test_report_shows_deltas_against_the_previous_snapshot(self):
        a = self.snap(FakeHttp("forbidden"))
        b = json.loads(json.dumps(a))
        b["channel"]["subscribers"] = 15
        for v in b["videos"]:
            if v["id"] == "SHORT1":
                v["views"] = 150
        md = yt_stats.render_report([a, b])
        self.assertIn("| Subscribers | 15 | +3 |", md)
        self.assertIn("| 150 | +30 |", md)
        self.assertIn("Best Short so far", md)
        self.assertIn("Best Deep-Dive so far", md)
        self.assertIn("⚠️", md, "the missing analytics scope is said out loud")

    def test_report_with_analytics_has_retention_columns(self):
        md = yt_stats.render_report([self.snap(FakeHttp("ok"))])
        self.assertIn("% viewed", md)
        self.assertIn("57%", md)
        self.assertIn("YT_SEARCH", md)

    def test_iso_durations(self):
        self.assertEqual(yt_stats.iso_duration_seconds("PT9M58S"), 598)
        self.assertEqual(yt_stats.iso_duration_seconds("PT1H2M3S"), 3723)
        self.assertEqual(yt_stats.iso_duration_seconds("PT45S"), 45)
        self.assertEqual(yt_stats.iso_duration_seconds(None), 0)

    def test_snapshots_append_and_are_capped(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with patch.object(yt_stats, "STATS", Path(td) / "s.json"):
                for k in range(3):
                    hist = yt_stats.save_snapshot({"k": k, "videos": [], "channel": {}}, keep=2)
                self.assertEqual([h["k"] for h in hist], [1, 2])


class WorkflowTests(unittest.TestCase):
    def test_weekly_read_only_and_committed_with_skip_ci(self):
        src = (ROOT / ".github" / "workflows" / "youtube_stats.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '0 5 * * 1'", src)
        self.assertIn("tools/yt_stats.py", src)
        self.assertIn("[skip ci]", src)
        self.assertIn("docs/YOUTUBE_PERFORMANCE.md", src)
        self.assertNotIn("yt_publish.py --video", src, "a stats job never uploads")


if __name__ == "__main__":
    unittest.main()
