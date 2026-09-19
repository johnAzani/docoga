#!/usr/bin/env python3
"""
DocOga POST-DEPLOY LIVE VERIFICATION
====================================
Rule: after every deploy, run this. If it's not green, the LIVE site is
broken — fix before anything else. This fetches the REAL pages your
customers see and parses the REAL JavaScript their browsers will run.

Checks: every page's inline JS parses (the 19-Sep-bug check, but on the
LIVE site), config values live, SEO wiring live, Worker healthy.
"""
import re, os, sys, json, tempfile, subprocess, urllib.request

BASE = "https://docoga.com.ng"
WORKER = "https://docoga-pass.johnazani.workers.dev"
errors = []

def check(name, cond, detail=""):
    print(f"  {'✅' if cond else '❌'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        errors.append(name)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DocOga-QA/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def node_check(code):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
        t.write(code); p = t.name
    r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
    os.unlink(p)
    return r.returncode == 0, (r.stderr[:80] if r.returncode else "")

print(f"── Live pages @ {BASE} ──")
for path, markers in [
    ("/", ["Notice to Quit", "Oga Pass", "FAQPage"]),
    ("/success.html", ["Oga Pass"]),
]:
    try:
        html = fetch(BASE + path)
        check(f"{path}: fetched ({len(html)} bytes)", True)
    except Exception as e:
        check(f"{path}: fetched", False, str(e)[:80]); continue
    for m in markers:
        check(f"{path}: contains '{m}'", m in html)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    ok = True; detail = ""
    for s in scripts:
        good, err = node_check(s)
        if not good: ok = False; detail = err; break
    check(f"{path}: {len(scripts)} live script(s) PARSE CLEAN", ok, detail)

print("── Live config ──")
home = fetch(BASE + "/")
for key, expect in [
    ("PAYMENT_URL", "https://flutterwave.com/pay/"),
    ("SUPPORT_WHATSAPP", None),
    ("WORKER_URL", ".workers.dev"),
]:
    m = re.search(rf'const {key} = "([^"]*)"', home)
    if not m or not m.group(1):
        check(f"live {key} is set", False); continue
    v = m.group(1)
    if expect:
        check(f"live {key} = {v[:40]}", expect in v)
    else:
        check(f"live {key} = {v}", bool(re.fullmatch(r"\d{13}", v)))

print("── Live SEO wiring ──")
robots = fetch(BASE + "/robots.txt")
check("robots.txt sitemap → docoga.com.ng", "Sitemap: https://docoga.com.ng/sitemap.xml" in robots)
smap = fetch(BASE + "/sitemap.xml")
check("sitemap.xml: our domain only", "docoga.com.ng" in smap and "docoga.top" not in smap)

print("── Worker health ──")
try:
    w = json.loads(fetch(WORKER + "/"))
    check("Worker responds ok:true", w.get("ok") is True)
except Exception as e:
    check("Worker responds ok:true", False, str(e)[:80])

print()
if errors:
    print(f"⛔ LIVE VERIFICATION FAILED — {len(errors)} error(s). The live site needs attention NOW.")
    sys.exit(1)
print("🏆 LIVE SITE VERIFIED HEALTHY — pages, scripts, config, SEO, Worker all green.")
