"""Offline safety tests for the aggregate-only GA4 snapshot writer."""
import datetime as dt
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import analytics_snapshot as snapshot  # noqa: E402


FAKE_TOKEN = "not-a-real-access-token-used-only-in-tests"


def api_row(channel, sessions, users, engagement_rate):
    return {
        "dimensionValues": [{"value": channel}],
        "metricValues": [
            {"value": str(sessions)},
            {"value": str(users)},
            {"value": str(engagement_rate)},
        ],
    }


def api_response(rows, row_count, **metadata):
    return {"rows": rows, "rowCount": row_count, "metadata": metadata}


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class AnalyticsSnapshotTests(unittest.TestCase):
    def test_report_window_is_seven_lagos_calendar_days_ending_two_days_ago(self):
        start, end = snapshot.report_window(today=dt.date(2026, 10, 10))
        self.assertEqual(start, dt.date(2026, 10, 2))
        self.assertEqual(end, dt.date(2026, 10, 8))
        self.assertEqual((end - start).days + 1, 7)

    def test_request_is_fixed_aggregate_only_and_preserves_quality_flags(self):
        response = api_response(
            [api_row("Organic Search", 12, 9, "0.75")],
            1,
            subjectToThresholding=False,
            dataLossFromOtherRow=True,
            schemaRestrictionResponse={"activeMetricRestrictions": []},
            samplingMetadatas=[{"samplesReadCount": "9", "samplingSpaceSize": "9"}],
            timeZone="Africa/Lagos",
            currencyCode="NGN",
        )
        with mock.patch.object(
            snapshot.urllib.request, "urlopen", return_value=FakeResponse(response)
        ) as urlopen:
            result = snapshot.fetch(
                "558370565", FAKE_TOKEN, today=dt.date(2026, 10, 10)
            )

        request = urlopen.call_args.args[0]
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, snapshot.API_URL.format(property_id="558370565"))
        self.assertEqual(request.get_header("Authorization"), f"Bearer {FAKE_TOKEN}")
        self.assertEqual(request_body["dimensions"], [{"name": "sessionDefaultChannelGroup"}])
        self.assertEqual(
            request_body["metrics"],
            [{"name": "sessions"}, {"name": "totalUsers"}, {"name": "engagementRate"}],
        )
        self.assertEqual(request_body["dateRanges"], [{"startDate": "2026-10-02", "endDate": "2026-10-08"}])
        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["property_timezone"], "Africa/Lagos")
        self.assertEqual(result["property_currency"], "NGN")
        self.assertEqual(result["rows"], [{
            "channel": "Organic Search",
            "sessions": "12",
            "users": "9",
            "engagement_rate": "0.75",
        }])
        self.assertTrue(result["warnings"]["data_loss_from_other_row"])
        self.assertEqual(len(result["warnings"]["sampling_metadatas"]), 1)
        self.assertEqual(result["warnings"]["row_count"], 1)
        self.assertEqual(result["warnings"]["returned_rows"], 1)
        self.assertTrue(result["warnings"]["pagination_complete"])
        self.assertNotIn(FAKE_TOKEN, json.dumps(result))
        self.assertNotIn("pageLocation", request_body)
        self.assertNotIn("userId", request_body)

    def test_fetches_all_pages_and_records_pagination_status(self):
        metadata = {"timeZone": "Africa/Lagos", "currencyCode": "NGN"}
        pages = [
            api_response([api_row("Direct", 3, 2, "0.5")], 2, **metadata),
            api_response([api_row("Referral", 1, 1, "1")], 2, **metadata),
        ]
        with mock.patch.object(
            snapshot.urllib.request,
            "urlopen",
            side_effect=[FakeResponse(page) for page in pages],
        ) as urlopen:
            result = snapshot.fetch(
                "558370565", FAKE_TOKEN, today=dt.date(2026, 10, 10)
            )

        offsets = [json.loads(call.args[0].data.decode("utf-8"))["offset"]
                   for call in urlopen.call_args_list]
        self.assertEqual(offsets, [0, 1])
        self.assertEqual([row["channel"] for row in result["rows"]], ["Direct", "Referral"])
        self.assertEqual(result["warnings"]["pages_fetched"], 2)
        self.assertTrue(result["warnings"]["pagination_complete"])

    def test_http_error_is_friendly_and_redacts_token(self):
        error_body = json.dumps({
            "error": {"message": f"The supplied token was {FAKE_TOKEN} and was rejected."}
        }).encode("utf-8")
        http_error = urllib.error.HTTPError(
            snapshot.API_URL.format(property_id="558370565"),
            403,
            "Forbidden",
            hdrs=None,
            fp=io.BytesIO(error_body),
        )
        with mock.patch.object(snapshot.urllib.request, "urlopen", side_effect=http_error):
            with self.assertRaises(snapshot.SnapshotError) as caught:
                snapshot.fetch("558370565", FAKE_TOKEN)
        self.assertIn("HTTP 403", str(caught.exception))
        self.assertIn("[REDACTED]", str(caught.exception))
        self.assertNotIn(FAKE_TOKEN, str(caught.exception))

    def test_refuses_unexpected_property_timezone(self):
        response = api_response(
            [], 0, timeZone="Etc/UTC", currencyCode="NGN"
        )
        with mock.patch.object(
            snapshot.urllib.request, "urlopen", return_value=FakeResponse(response)
        ):
            with self.assertRaisesRegex(snapshot.SnapshotError, "timezone"):
                snapshot.fetch("558370565", FAKE_TOKEN)

    def test_rejects_non_numeric_property_id_before_network_access(self):
        with mock.patch.object(snapshot.urllib.request, "urlopen") as urlopen:
            with self.assertRaisesRegex(snapshot.SnapshotError, "numeric"):
                snapshot.fetch("558370565:runReport", FAKE_TOKEN)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
