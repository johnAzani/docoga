#!/usr/bin/env python3
"""live_probe.py — is DocOga actually up? (₦0, five times a day)

Why this exists (29 Oct 2026)
-----------------------------
The heartbeat (tools/automation_heartbeat.py) judges whether every *lane* ran. Nothing
judged whether the *product* answered: the site on Cloudflare Pages, the payment worker
(docoga-pass), the receipt ledger (docoga-ledger) and the clock worker (docoga-clock).
A broken deploy, an expired certificate, a Worker that starts throwing 1101, a page that
quietly 404s after a rename — each would have been found by the next paying customer,
and this business has none to spare. Paid uptime monitors start at $7/month; a GitHub
Actions runner has unrestricted egress and this repository is public, so the probe is free.

What it checks (read-only GETs only — nothing here can verify a code, move money or post)
    * the home page: 200, served as HTML, carries the brand and its og:image tag
    * sitemap.xml and robots.txt: 200
    * the home link-preview image: 200, image/jpeg (WhatsApp shows nothing if this breaks)
    * EVERY URL in the sitemap: 200 after at most one redirect, and the final URL must not
      end in .html (a clean-URL regression — the reason Search Console indexed pages twice)
    * docoga-pass GET /  → {ok:true, service:"docoga-pass", priceNGN:2000}
    * docoga-ledger GET /health and /api/stats → 200 JSON
    * docoga-clock GET /  → {ok:true, token:"present", paused:false}
    * TLS certificate of docoga.com.ng: more than 14 days left

Flapping guard: anything that fails is tried again after a pause before it counts, so a
single Cloudflare hiccup is not an alarm. The workflow files ONE issue under the label
`live-probe` while anything is failing and closes it when everything answers again.

    python3 tools/live_probe.py [--out logs/live_probe.json] [--markdown /tmp/live_probe.md]
                                [--retry-wait 45] [--quick]
Machine lines on stdout: LIVE_PROBE=ok|degraded · LIVE_PROBE_FAILING=<n> · LIVE_PROBE_SIGNATURE=<hash>
Exit 0 when everything answers, 1 when something is down after the retry, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://docoga.com.ng"
PASS = "https://docoga-pass.johnazani.workers.dev"
LEDGER = "https://docoga-ledger.johnazani.workers.dev"   # must equal site/index.html's LEDGER_URL
CLOCK = "https://docoga-clock.johnazani.workers.dev"
PRICE_NGN = 2000                                         # the one price; a change here is news
TLS_MIN_DAYS = 14
TIMEOUT = 20
UA = "DocOga-live-probe/1 (+https://github.com/johnAzani/docoga)"
OUT = ROOT / "logs" / "live_probe.json"
SLOW_MS = 4000      # reported, never a failure: Cloudflare's edge is in Lagos, the runner is not


class Result:
    __slots__ = ("name", "url", "ok", "status", "ms", "note")

    def __init__(self, name, url, ok, status=None, ms=None, note=""):
        self.name, self.url, self.ok, self.status, self.ms, self.note = name, url, ok, status, ms, note

    def as_dict(self):
        return {"name": self.name, "url": self.url, "ok": self.ok, "status": self.status,
                "ms": self.ms, "note": self.note}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def fetch(url, follow=True, timeout=TIMEOUT):
    """(status, final_url, headers, body_bytes, ms). Never raises for HTTP errors."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect())
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read(2_000_000)
            return r.status, r.geturl(), dict(r.headers), body, int((time.monotonic() - t0) * 1000)
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read(200_000)
        except Exception:
            pass
        return e.code, e.geturl() if hasattr(e, "geturl") else url, dict(e.headers or {}), body, int((time.monotonic() - t0) * 1000)
    except Exception as e:  # DNS, TLS, timeout, reset
        return 0, url, {}, str(e).encode("utf-8", "replace"), int((time.monotonic() - t0) * 1000)


def _json(body):
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return None


# ── individual checks ───────────────────────────────────────────────────────────────────

def check_home():
    status, final, hdrs, body, ms = fetch(SITE + "/")
    text = body.decode("utf-8", "replace")
    ctype = (hdrs.get("Content-Type") or hdrs.get("content-type") or "").lower()
    problems = []
    if status != 200:
        problems.append("status %s" % status)
    if "text/html" not in ctype:
        problems.append("content-type %r" % ctype)
    if "DocOga" not in text:
        problems.append("brand missing from the page")
    if 'property="og:image"' not in text:
        problems.append("og:image tag missing (link previews gone)")
    return Result("home page", SITE + "/", not problems, status, ms, "; ".join(problems))


def check_static(path, must_type, must_contain=None):
    status, final, hdrs, body, ms = fetch(SITE + path)
    ctype = (hdrs.get("Content-Type") or hdrs.get("content-type") or "").lower()
    problems = []
    if status != 200:
        problems.append("status %s" % status)
    if must_type not in ctype:
        problems.append("content-type %r" % ctype)
    if must_contain and must_contain.encode() not in body:
        problems.append("%r missing" % must_contain)
    return Result(path.lstrip("/"), SITE + path, not problems, status, ms, "; ".join(problems)), body


def sitemap_locs(body):
    return sorted(set(re.findall(rb"<loc>\s*(https://docoga\.com\.ng/[^<\s]*)\s*</loc>", body or b"")))


def check_page(url):
    url = url.decode() if isinstance(url, bytes) else url
    status, final, hdrs, body, ms = fetch(url, follow=False)
    hops = 0
    while status in (301, 302, 307, 308) and hops < 1:
        loc = hdrs.get("Location") or hdrs.get("location") or ""
        if loc.startswith("/"):
            loc = SITE + loc
        status, final, hdrs, body, ms2 = fetch(loc, follow=False)
        final = loc
        ms += ms2
        hops += 1
    problems = []
    if status != 200:
        problems.append("status %s after %d redirect(s)" % (status, hops))
    if final.split("?")[0].endswith(".html"):
        problems.append("lands on a .html URL (clean-URL regression)")
    if status == 200 and b"<title>" not in body[:20000]:
        problems.append("no <title> in the first 20 KB")
    name = url.replace(SITE, "") or "/"
    return Result(name, url, not problems, status, ms, "; ".join(problems))


def check_pass():
    status, final, hdrs, body, ms = fetch(PASS + "/")
    d = _json(body) or {}
    problems = []
    if status != 200:
        problems.append("status %s" % status)
    if d.get("ok") is not True or d.get("service") != "docoga-pass":
        problems.append("not the pass worker's health body")
    if d.get("priceNGN") not in (None, PRICE_NGN):
        problems.append("priceNGN is %r, expected %d" % (d.get("priceNGN"), PRICE_NGN))
    return Result("docoga-pass (payments)", PASS + "/", not problems, status, ms, "; ".join(problems))


def check_ledger():
    out = []
    status, final, hdrs, body, ms = fetch(LEDGER + "/health")
    d = _json(body) or {}
    bad = [] if (status == 200 and d.get("ok") is True) else ["status %s / body %r" % (status, body[:80])]
    out.append(Result("docoga-ledger /health", LEDGER + "/health", not bad, status, ms, "; ".join(bad)))
    status, final, hdrs, body, ms = fetch(LEDGER + "/api/stats")
    d = _json(body)
    bad = [] if (status == 200 and isinstance(d, dict) and "total" in d) else ["status %s / not the stats JSON" % status]
    out.append(Result("docoga-ledger /api/stats (Rent Monitor)", LEDGER + "/api/stats", not bad, status, ms, "; ".join(bad)))
    return out


def check_clock():
    status, final, hdrs, body, ms = fetch(CLOCK + "/")
    d = _json(body) or {}
    problems = []
    if status != 200 or d.get("ok") is not True:
        problems.append("status %s" % status)
    if d.get("token") != "present":
        problems.append("dispatch token %r — the clock cannot ring any lane" % d.get("token"))
    if d.get("paused") is True:
        problems.append("clock is paused (CLOCK=off)")
    if isinstance(d.get("entries"), int) and d["entries"] < 10:
        problems.append("only %d schedule entries" % d["entries"])
    return Result("docoga-clock (the schedule)", CLOCK + "/", not problems, status, ms, "; ".join(problems))


def check_tls(host="docoga.com.ng", min_days=TLS_MIN_DAYS):
    t0 = time.monotonic()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                cert = ss.getpeercert()
        not_after = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
        days = (not_after - dt.datetime.now(dt.timezone.utc)).days
        ok = days > min_days
        return Result("TLS certificate", "https://%s" % host, ok, 200 if ok else 0,
                      int((time.monotonic() - t0) * 1000),
                      "%d days left" % days if ok else "only %d days left (renews itself on Cloudflare; if this persists, look)" % days)
    except Exception as e:
        return Result("TLS certificate", "https://%s" % host, False, 0, int((time.monotonic() - t0) * 1000), str(e)[:160])


# ── the pass ────────────────────────────────────────────────────────────────────────────

def run_once(quick=False, log=print):
    results = [check_home()]
    smap, smap_body = check_static("/sitemap.xml", "xml", "<urlset")
    results.append(smap)
    results.append(check_static("/robots.txt", "text/plain", "Sitemap:")[0])
    results.append(check_static("/og/home.jpg", "image/jpeg")[0])
    locs = sitemap_locs(smap_body)
    if smap.ok and len(locs) < 20:
        results.append(Result("sitemap size", SITE + "/sitemap.xml", False, 200, 0, "only %d URLs in the sitemap" % len(locs)))
    pages = locs if not quick else locs[:5]
    for loc in pages:
        results.append(check_page(loc))
    results.append(check_pass())
    results.extend(check_ledger())
    results.append(check_clock())
    results.append(check_tls())
    return results


RETRYABLE = {"home page", "sitemap.xml", "robots.txt", "og/home.jpg", "docoga-pass (payments)",
             "docoga-ledger /health", "docoga-ledger /api/stats (Rent Monitor)", "docoga-clock (the schedule)",
             "TLS certificate"}


def retry(failed, log=print):
    """Second look at every failure; returns the ones still failing."""
    still = []
    for r in failed:
        if r.name == "home page":
            again = check_home()
        elif r.name == "sitemap.xml":
            again = check_static("/sitemap.xml", "xml", "<urlset")[0]
        elif r.name == "robots.txt":
            again = check_static("/robots.txt", "text/plain", "Sitemap:")[0]
        elif r.name == "og/home.jpg":
            again = check_static("/og/home.jpg", "image/jpeg")[0]
        elif r.name.startswith("docoga-pass"):
            again = check_pass()
        elif r.name.startswith("docoga-ledger /health"):
            again = check_ledger()[0]
        elif r.name.startswith("docoga-ledger /api/stats"):
            again = check_ledger()[1]
        elif r.name.startswith("docoga-clock"):
            again = check_clock()
        elif r.name == "TLS certificate":
            again = check_tls()
        elif r.url.startswith(SITE + "/") and r.name != "sitemap size":
            again = check_page(r.url)
        else:
            again = r
        log("  retry %-48s %s" % (again.name, "ok" if again.ok else again.note))
        if not again.ok:
            still.append(again)
    return still


def signature(failing):
    return hashlib.sha1("|".join(sorted("%s:%s" % (r.name, r.note) for r in failing)).encode()).hexdigest()[:10]


def markdown(results, failing, took_s):
    lines = ["| check | status | ms | note |", "|---|---|---|---|"]
    for r in results:
        if r.ok and r.url.startswith(SITE + "/") and r.name not in RETRYABLE and r.name != "sitemap size":
            continue      # the 80 sitemap pages are summarised below when they pass
        lines.append("| %s %s | %s | %s | %s |" % ("✅" if r.ok else "❌", r.name, r.status, r.ms, r.note.replace("|", "/")))
    pages = [r for r in results if r.url.startswith(SITE + "/") and r.name not in RETRYABLE and r.name != "sitemap size"]
    slow = [r for r in results if r.ok and (r.ms or 0) > SLOW_MS]
    head = "**%s** — %d checks, %d failing, %d sitemap pages, %.0f s" % (
        "ALL ANSWERING" if not failing else "%d DOWN" % len(failing), len(results), len(failing), len(pages), took_s)
    body = [head, ""] + lines
    if slow:
        body += ["", "Slow (over %d ms, not a failure): %s" % (SLOW_MS, ", ".join("%s %d ms" % (r.name, r.ms) for r in slow[:8]))]
    return "\n".join(body) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--markdown", default="")
    ap.add_argument("--retry-wait", type=int, default=45)
    ap.add_argument("--quick", action="store_true", help="only the first five sitemap pages (for a dispatch smoke test)")
    a = ap.parse_args(argv)

    t0 = time.monotonic()
    results = run_once(quick=a.quick)
    failing = [r for r in results if not r.ok]
    for r in results:
        if not r.ok or (r.ms or 0) > SLOW_MS:
            print("  %-4s %-48s %s %s" % ("ok" if r.ok else "FAIL", r.name, r.ms, r.note))
    if failing:
        print("live_probe: %d failing on the first pass — looking again in %d s" % (len(failing), a.retry_wait))
        time.sleep(max(0, a.retry_wait))
        still = retry(failing)
        still_names = {r.name for r in still}
        recovered = [Result(f.name, f.url, True, f.status, f.ms, "recovered on retry")
                     for f in failing if f.name not in still_names]
        results = [r for r in results if r.ok] + recovered + still
        failing = still
    took = time.monotonic() - t0

    sig = signature(failing)
    report = {
        "taken_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ok": not failing, "failing": [r.as_dict() for r in failing], "signature": sig,
        "checks": [r.as_dict() for r in results], "took_s": round(took, 1),
    }
    md = markdown(results, failing, took)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.markdown:
        Path(a.markdown).write_text(md, encoding="utf-8")
    print(md)
    print("LIVE_PROBE=%s" % ("ok" if not failing else "degraded"))
    print("LIVE_PROBE_FAILING=%d" % len(failing))
    print("LIVE_PROBE_SIGNATURE=%s" % sig)
    return 0 if not failing else 1


if __name__ == "__main__":
    sys.exit(main())
