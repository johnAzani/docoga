#!/usr/bin/env python3
"""Write a privacy-minimised, aggregate-only DocOga GA4 snapshot.

Modes:
  --placeholder : mechanism test; makes no Google API call.
  default       : read-only GA4 Data API call using a short-lived token supplied
                  by GitHub Actions, then write the sanitised report.

Only fixed channel-group aggregates are requested. Never add user identifiers,
URLs, query strings, pass codes, payment references, emails, or other raw event
or user-level dimensions to this report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any
from zoneinfo import ZoneInfo

REPORT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "analytics", "reports"
)
PROPERTY_TIME_ZONE_NAME = "Africa/Lagos"
PROPERTY_TIME_ZONE = ZoneInfo(PROPERTY_TIME_ZONE_NAME)
PROPERTY_CURRENCY = "NGN"
REPORT_DAYS = 7
REPORT_DELAY_DAYS = 2
PAGE_SIZE = 1000
MAX_PAGES = 100
API_URL = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
DIMENSION_NAMES = ("sessionDefaultChannelGroup",)
METRIC_NAMES = ("sessions", "totalUsers", "engagementRate")
PRIVACY_NOTE = (
    "Aggregate counts by session default channel group only. No user identifiers, "
    "emails, locations, pass codes, payment references, or URLs are requested or stored."
)


class SnapshotError(Exception):
    """A safe-to-display error that does not contain credentials or response data."""


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_window(days: int = REPORT_DAYS, today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """Return a complete report window, using the GA property's local calendar.

    The end is two property-calendar days ago to allow for GA4 processing lag.
    The range is inclusive and therefore contains exactly ``days`` dates.
    ``today`` is injectable for deterministic tests; production uses Africa/Lagos.
    """
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 90:
        raise SnapshotError("report window must be between 1 and 90 days")
    if today is None:
        today = dt.datetime.now(PROPERTY_TIME_ZONE).date()
    if not isinstance(today, dt.date) or isinstance(today, dt.datetime):
        raise SnapshotError("report date must be a calendar date")
    end = today - dt.timedelta(days=REPORT_DELAY_DAYS)
    start = end - dt.timedelta(days=days - 1)
    return start, end


def write_snapshot(payload: dict[str, Any]) -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)
    latest = os.path.join(REPORT_DIR, "latest.json")
    dated = os.path.join(REPORT_DIR, payload["generated_at_utc"][:10] + ".json")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    for path in (latest, dated):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print("wrote analytics/reports/latest.json")


def placeholder() -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc(),
        "mode": "placeholder",
        "note": "Mechanism test only. No Google Analytics call was made.",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "github_ref": os.environ.get("GITHUB_REF", ""),
        "property_id": None,
        "rows": [],
    }


def _safe_http_error_message(error: urllib.error.HTTPError, token: str) -> str:
    """Extract only Google's short error message; never echo a raw body or token."""
    message = "request rejected"
    try:
        payload = json.loads(error.read(8192).decode("utf-8"))
        api_error = payload.get("error", {}) if isinstance(payload, dict) else {}
        candidate = api_error.get("message") if isinstance(api_error, dict) else None
        if isinstance(candidate, str) and candidate.strip():
            message = candidate
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        pass
    if token:
        message = message.replace(token, "[REDACTED]")
    return " ".join(message.split())[:400]


def _request_page(
    property_id: str, token: str, start: dt.date, end: dt.date, offset: int
) -> dict[str, Any]:
    body = {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": name} for name in DIMENSION_NAMES],
        "metrics": [{"name": name} for name in METRIC_NAMES],
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    request = urllib.request.Request(
        API_URL.format(property_id=property_id),
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_response = response.read()
    except urllib.error.HTTPError as error:
        message = _safe_http_error_message(error, token)
        raise SnapshotError(
            f"Google Analytics Data API returned HTTP {error.code}: {message}"
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SnapshotError(
            "Google Analytics Data API request failed due to a network or timeout error."
        ) from None

    try:
        data = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SnapshotError("Google Analytics Data API returned invalid JSON.") from None
    if not isinstance(data, dict):
        raise SnapshotError("Google Analytics Data API returned an unexpected response.")
    return data


def _read_string_value(values: Any, index: int, field: str, row_number: int) -> str:
    if not isinstance(values, list) or len(values) <= index:
        raise SnapshotError(
            f"Google Analytics response row {row_number} is missing an expected {field}."
        )
    entry = values[index]
    if not isinstance(entry, dict) or not isinstance(entry.get("value"), str):
        raise SnapshotError(
            f"Google Analytics response row {row_number} has an invalid {field}."
        )
    return entry["value"]


def _parse_rows(raw_rows: Any, offset: int) -> list[dict[str, str]]:
    if raw_rows is None:
        return []
    if not isinstance(raw_rows, list):
        raise SnapshotError("Google Analytics returned an invalid rows collection.")
    parsed = []
    for index, row in enumerate(raw_rows):
        row_number = offset + index + 1
        if not isinstance(row, dict):
            raise SnapshotError(f"Google Analytics response row {row_number} is invalid.")
        channel = _read_string_value(row.get("dimensionValues"), 0, "channel", row_number)
        if len(channel) > 128 or any(ord(char) < 32 for char in channel):
            raise SnapshotError(
                f"Google Analytics response row {row_number} has an invalid channel value."
            )
        metrics = row.get("metricValues")
        parsed.append(
            {
                "channel": channel,
                "sessions": _read_string_value(metrics, 0, "sessions", row_number),
                "users": _read_string_value(metrics, 1, "totalUsers", row_number),
                "engagement_rate": _read_string_value(
                    metrics, 2, "engagementRate", row_number
                ),
            }
        )
    return parsed


def _validate_row_count(data: dict[str, Any]) -> int:
    row_count = data.get("rowCount")
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 0:
        raise SnapshotError("Google Analytics response is missing a valid rowCount.")
    return row_count


def _validate_metadata(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata", {})
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise SnapshotError("Google Analytics response metadata is invalid.")
    reported_timezone = metadata.get("timeZone")
    if reported_timezone and reported_timezone != PROPERTY_TIME_ZONE_NAME:
        raise SnapshotError(
            "GA4 reports a property timezone different from the verified Africa/Lagos setting; "
            "no snapshot was written."
        )
    return metadata


def _page_metadata_signature(metadata: dict[str, Any]) -> str:
    keys = (
        "subjectToThresholding",
        "dataLossFromOtherRow",
        "schemaRestrictionResponse",
        "samplingMetadatas",
        "timeZone",
        "currencyCode",
        "emptyReason",
    )
    selected = {key: metadata.get(key) for key in keys if key in metadata}
    return json.dumps(selected, sort_keys=True, separators=(",", ":"))


def fetch(
    property_id: str,
    token: str,
    days: int = REPORT_DAYS,
    *,
    today: dt.date | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9]{1,20}", property_id):
        raise SnapshotError("GA_PROPERTY_ID must be a numeric GA4 property ID.")
    if not token or any(char.isspace() for char in token):
        raise SnapshotError("ACCESS_TOKEN is missing or malformed.")

    start, end = report_window(days, today)
    rows: list[dict[str, str]] = []
    first_metadata: dict[str, Any] | None = None
    metadata_signature: str | None = None
    expected_row_count: int | None = None
    offset = 0
    pages_fetched = 0

    while True:
        if pages_fetched >= MAX_PAGES:
            raise SnapshotError("GA4 report exceeded the safe pagination limit; no snapshot was written.")
        data = _request_page(property_id, token, start, end, offset)
        page_row_count = _validate_row_count(data)
        metadata = _validate_metadata(data)
        signature = _page_metadata_signature(metadata)
        if expected_row_count is None:
            expected_row_count = page_row_count
            first_metadata = metadata
            metadata_signature = signature
        elif page_row_count != expected_row_count or signature != metadata_signature:
            raise SnapshotError(
                "GA4 report metadata changed during pagination; no snapshot was written."
            )

        page_rows = _parse_rows(data.get("rows", []), offset)
        if len(page_rows) > PAGE_SIZE or offset + len(page_rows) > page_row_count:
            raise SnapshotError("GA4 returned inconsistent pagination data; no snapshot was written.")
        rows.extend(page_rows)
        pages_fetched += 1
        next_offset = offset + len(page_rows)

        if next_offset >= expected_row_count:
            break
        if not page_rows:
            raise SnapshotError("GA4 pagination stopped before all rows were received.")
        offset = next_offset

    assert expected_row_count is not None and first_metadata is not None
    pagination_complete = len(rows) == expected_row_count
    if not pagination_complete:
        raise SnapshotError("GA4 returned an incomplete report; no snapshot was written.")

    api_timezone = first_metadata.get("timeZone")
    api_currency = first_metadata.get("currencyCode")
    return {
        "generated_at_utc": now_utc(),
        "mode": "live",
        "property_id": property_id,
        "property_timezone": PROPERTY_TIME_ZONE_NAME,
        "property_timezone_source": (
            "GA4 response metadata" if api_timezone else "owner-verified property setting"
        ),
        "property_currency": api_currency or PROPERTY_CURRENCY,
        "property_currency_source": (
            "GA4 response metadata" if api_currency else "owner-verified property setting"
        ),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "report_definition": {
            "dimensions": list(DIMENSION_NAMES),
            "metrics": list(METRIC_NAMES),
        },
        "rows": rows,
        "warnings": {
            "subject_to_thresholding": first_metadata.get("subjectToThresholding"),
            "data_loss_from_other_row": first_metadata.get("dataLossFromOtherRow"),
            "schema_restriction": first_metadata.get("schemaRestrictionResponse"),
            "sampling_metadatas": first_metadata.get("samplingMetadatas", []),
            "empty_reason": first_metadata.get("emptyReason"),
            "row_count": expected_row_count,
            "returned_rows": len(rows),
            "pages_fetched": pages_fetched,
            "pagination_complete": pagination_complete,
        },
        "privacy": PRIVACY_NOTE,
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "github_ref": os.environ.get("GITHUB_REF", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--placeholder", action="store_true")
    args = parser.parse_args()
    try:
        if args.placeholder:
            write_snapshot(placeholder())
            return 0
        property_id = os.environ.get("GA_PROPERTY_ID", "").strip()
        token = os.environ.get("ACCESS_TOKEN", "").strip()
        if not property_id or not token:
            raise SnapshotError("missing GA_PROPERTY_ID or ACCESS_TOKEN; use --placeholder")
        write_snapshot(fetch(property_id, token))
        return 0
    except SnapshotError as error:
        print(f"analytics snapshot failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("analytics snapshot failed: could not write the report files.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
