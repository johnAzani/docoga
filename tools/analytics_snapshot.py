#!/usr/bin/env python3
"""DocOga Analytics snapshot writer.

Modes:
  --placeholder : write a placeholder snapshot (no Google credentials yet).
  default       : call the GA4 Data API with a token from the environment and
                  write a sanitised aggregate snapshot.

The output is committed back into the repository by the workflow, because the
agent sandbox cannot read workflow logs or artifacts (blocked hosts). Keep the
snapshot AGGREGATE ONLY: no user identifiers, emails, pass codes, payment
references or URL query strings.
"""
import argparse, datetime, json, os, sys, urllib.request, urllib.error

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analytics", "reports")


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_snapshot(payload: dict) -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)
    latest = os.path.join(REPORT_DIR, "latest.json")
    dated = os.path.join(REPORT_DIR, payload["generated_at_utc"][:10] + ".json")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    for path in (latest, dated):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print("wrote", latest)


def placeholder() -> dict:
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


def fetch(property_id: str, token: str, days: int = 7) -> dict:
    end = datetime.date.today() - datetime.timedelta(days=2)  # complete days only
    start = end - datetime.timedelta(days=days - 1)
    body = {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [{"name": "sessions"}, {"name": "totalUsers"}, {"name": "engagementRate"}],
    }
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    rows = []
    for r in data.get("rows", []):
        rows.append({
            "channel": r["dimensionValues"][0]["value"],
            "sessions": r["metricValues"][0]["value"],
            "users": r["metricValues"][1]["value"],
            "engagement_rate": r["metricValues"][2]["value"],
        })
    return {
        "generated_at_utc": now_utc(),
        "mode": "live",
        "property_id": property_id,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "rows": rows,
        "warnings": {
            "subject_to_thresholding": data.get("metadata", {}).get("subjectToThresholding"),
            "schema_restriction": data.get("metadata", {}).get("schemaRestrictionResponse"),
            "row_count": data.get("rowCount"),
        },
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placeholder", action="store_true")
    args = ap.parse_args()
    if args.placeholder:
        write_snapshot(placeholder())
        return 0
    prop = os.environ.get("GA_PROPERTY_ID", "").strip()
    token = os.environ.get("ACCESS_TOKEN", "").strip()
    if not prop or not token:
        print("missing GA_PROPERTY_ID or ACCESS_TOKEN; use --placeholder", file=sys.stderr)
        return 2
    write_snapshot(fetch(prop, token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
