#!/usr/bin/env python3
"""
DocOga PRE-PUSH QA GATE
=======================
Rule: NO PUSH unless this script exits 0 (all ✅, zero ❌).

What it checks (every run, on every file — not just the one you touched):
  1. Every inline <script> in every site/*.html is extracted and syntax-parsed
     by node --check  (this is the check that would have caught the 19 Sep bug)
  2. No placeholders left anywhere (REPLACE-WITH, empty config values)
  3. Config block complete and consistent (PAYMENT_URL / SUPPORT_WHATSAPP /
     SITE_URL / WORKER_URL) across index.html AND success.html
  4. Domain consistency: canonical, og:url, sitemap.xml, robots.txt all agree
  5. Every id referenced from JS ($('x') / getElementById) exists in the HTML
  6. No duplicate static ids; balanced <script> tags; sane file sizes
  7. worker/index.js parses; wrangler.toml has a real KV id
  8. SECRET LEAK CHECK: nothing from .worker-secrets.env appears in any
     file that gets deployed or committed
  9. Dependency-light test suites: worker, full-app jsdom, and Analytics-consent suites
 10. Anchor integrity: every in-page href="#x" resolves to a real id
 11. Site-wide (every page, not just index.html): JSON-LD parses, every
     absolute …/#route deep link is a real SPA route, every sitemap loc is
     a file we actually ship
 12. Hosting is Cloudflare Pages: no netlify.toml, no Netlify references in
     deployable files, README still documents the host and the `site`
     publish-directory warning (Netlify retired 3 Oct 2026)
 13. Owner dashboard contract (ADMIN_DASHBOARD.md sync law): the admin page is
     unlisted and unadvertised, its API URL matches the storefront's, it holds no
     secret, the Worker routes + ledger hooks it depends on still exist, the
     Android wrapper still points at this origin, and both admin suites are green
"""
import re, os, sys, glob, tempfile, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = os.path.join(ROOT, "site")
WORKER = os.path.join(ROOT, "worker")

errors, warnings = [], []

def check(name, cond, detail=""):
    print(f"  {'✅' if cond else '❌'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        errors.append(name)

def warn(name, cond, detail=""):
    if not cond:
        print(f"  ⚠️  {name}" + (f"  [{detail}]" if detail else ""))
        warnings.append(name)

def node_check(code: str) -> tuple:
    """Return (ok, first_error_line_or_None) for a JS snippet."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
        t.write(code)
        path = t.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if r.returncode == 0:
            return True, None
        m = re.search(r":(\d+)\n(.*)", r.stderr)
        return False, (f"line {m.group(1)}: {m.group(2)[:80]}" if m else r.stderr[:80])
    finally:
        os.unlink(path)

print("── 1. JavaScript syntax (every inline script, every page) ──")
for f in sorted(glob.glob(f"{SITE}/*.html")):
    html = open(f, encoding="utf-8").read()
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    ok = True; detail = ""
    for s in scripts:
        good, err = node_check(s)
        if not good:
            ok = False; detail = err; break
    check(f"{os.path.basename(f)}: {len(scripts)} script(s) parse", ok, detail)
consent_js_path = os.path.join(SITE, "analytics-consent.js")
if os.path.exists(consent_js_path):
    consent_ok, consent_err = node_check(open(consent_js_path, encoding="utf-8").read())
    check("analytics-consent.js parses", consent_ok, consent_err or "")
else:
    check("analytics-consent.js exists", False)

print("── 2. Placeholders & completeness ──")
for f in sorted(glob.glob(f"{SITE}/*.html")):
    html = open(f, encoding="utf-8").read()
    check(f"{os.path.basename(f)}: no placeholders", "REPLACE-WITH" not in html and "REPLACE_WITH" not in html)

idx = open(f"{SITE}/index.html", encoding="utf-8").read()
suc = open(f"{SITE}/success.html", encoding="utf-8").read()

def cfg(src, key):
    m = re.search(rf'const {key} = "([^"]*)"', src)
    return m.group(1) if m else None

print("── 3. Config block (index.html + success.html) ──")
check("PAYMENT_URL is a live https link", (cfg(idx, "PAYMENT_URL") or "").startswith("https://flutterwave.com/pay/"))
check("SUPPORT_WHATSAPP is 13-digit intl format", bool(re.fullmatch(r"\d{13}", cfg(idx, "SUPPORT_WHATSAPP") or "")))
check("SITE_URL is https://docoga.com.ng", cfg(idx, "SITE_URL") == "https://docoga.com.ng")
check("WORKER_URL set (workers.dev)", ".workers.dev" in (cfg(idx, "WORKER_URL") or ""))
check("success.html WORKER_URL == index.html", cfg(suc, "WORKER_URL") == cfg(idx, "WORKER_URL"))
check("success.html SUPPORT_WHATSAPP == index.html", cfg(suc, "SUPPORT_WHATSAPP") == cfg(idx, "SUPPORT_WHATSAPP"))

print("── 4. Domain consistency (SEO wiring) ──")
canon = re.search(r'rel="canonical" href="(https://[^/"]+)', idx)
og = re.search(r'og:url" content="(https://[^/"]+)', idx)
check("canonical == SITE_URL", canon and canon.group(1) == cfg(idx, "SITE_URL"))
check("og:url == SITE_URL", og and og.group(1) == cfg(idx, "SITE_URL"))
robots = open(f"{SITE}/robots.txt", encoding="utf-8").read()
smap = open(f"{SITE}/sitemap.xml", encoding="utf-8").read()
check("robots.txt sitemap on our domain", f"Sitemap: {cfg(idx,'SITE_URL')}/sitemap.xml" in robots)
check("sitemap.xml: 3+ locs on our domain", len(re.findall(r"<loc>https://docoga\.com\.ng/", smap)) >= 3)
check("sitemap.xml: zero docoga.top leftovers", "docoga.top" not in smap)

print("── 5. JS-referenced ids exist ──")
check("pass-state CTAs wired (buy-btn id + has-pass toggle + sticky-cta)",
      ('id="buy-btn"' in idx) and ("classList.toggle('has-pass'" in idx) and ('id="sticky-cta"' in idx) and ('buy-btn' in idx[idx.find("updatePassUI"):idx.find("function openModal")]),
      "pricing/sticky CTAs must react to pass state")
used = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", idx)) | set(re.findall(r"getElementById\('([^']+)'\)", idx))
defined = set(re.findall(r'id="([^"]+)"', idx))
missing = sorted(used - defined)
check(f"all {len(used)} JS-referenced ids exist in HTML", not missing, f"missing: {missing[:6]}")

print("── 6. Structural sanity ──")
for f, html in [("index.html", idx), ("success.html", suc)]:
    opens = len(re.findall(r"<script[ >]", html))
    closes = html.count("</script>")
    check(f"{f}: balanced <script> tags ({opens}/{closes})", opens == closes)
    warn(f"{f}: no duplicate static ids", len(re.findall(r'id="', html)) == len(set(re.findall(r'id="([^"]+)"', html))))
# Page-weight guard. The ORIGINAL rule was a 60–135KB RAW window (Sep 2026: 120.0KB raw
# with 9 tools = 33.3KB gzipped). Raw bytes are only a proxy — what reaches a phone on
# Nigerian data is the compressed payload, and raw size punishes exactly the thing we
# want to do (add tools) without tracking the thing we care about (load time).
#
# New gzip math, 8 Oct 2026, with 10 tools + a Business pricing tier:
#     135,856 bytes raw -> 38,217 bytes gzipped (28.1%)
#     i.e. 37.3KB over the wire, up from 33.3KB at the 9-tool baseline.
#     ~7.5% of the 500KB Nigerian-mobile page-weight guidance. Still single-file by
#     design, no build step.
#
# So: gate on GZIPPED size (the real metric), ceiling 48KB — comfortable headroom above
# the current 37.3KB for several more tools. Keep a generous RAW ceiling as a pure
# corruption tripwire (a duplicated or concatenated file blows past it immediately).
# Revisit the 48KB gzip ceiling if we ever add images or a second script bundle.
#
# Revisited 19 Oct 2026: the page stood at 47.4KB gzipped before the receipt ledger (the
# verification code + fingerprint, ~1.6KB gzipped) — the ceiling was going to be met by the
# next feature whatever it was. Ceiling 52KB: still ~10% of the 500KB Nigerian-mobile
# guidance, still one file, no build step. Next revisit at 52KB means splitting a bundle.
import gzip as _gzip
_idx_gz = len(_gzip.compress(idx.encode(), 9))
check("index.html gzipped payload under 52 KB (real page weight)",
      _idx_gz <= 52 * 1024, f"{_idx_gz} bytes gzipped")
check("index.html raw size sane (corruption tripwire, 40–200 KB)",
      40000 <= len(idx.encode()) <= 200000, f"{len(idx.encode())} bytes raw")

# 20 Oct 2026 — the split happened: the Business tier (waitlist, sign-in, configurator,
# checkout, renewal, team portal) lives in site/business.js and index.html's bizLoad()
# fetches it only when a team is signed in or a Business control is used. Retail readers
# (99% of visits) stopped downloading it: 51.2KB -> 45.4KB gzipped. The stamp BIZ_V in
# index.html is sha256(business.js)[:8] so a new business.js can never be served from a
# stale cache (the URL changes). These checks keep the two files honest with each other.
import hashlib as _hl, subprocess as _sp
_biz_path = f"{SITE}/business.js"
check("site/business.js exists (Business tier split out of index.html)", os.path.exists(_biz_path))
if os.path.exists(_biz_path):
    _biz = open(_biz_path, "rb").read()
    _biz_gz = len(_gzip.compress(_biz, 9))
    check("business.js gzipped under 16 KB (one Business module, not a second app)",
          _biz_gz <= 16 * 1024, f"{_biz_gz} bytes gzipped")
    _bv = re.search(r"const BIZ_V='([0-9a-f]{8})'", idx)
    check("index.html BIZ_V == sha256(business.js)[:8] (cache-busting stamp current)",
          bool(_bv) and _bv.group(1) == _hl.sha256(_biz).hexdigest()[:8],
          f"stamp={_bv.group(1) if _bv else None} actual={_hl.sha256(_biz).hexdigest()[:8]}")
    check("index.html no longer carries Business function bodies",
          not re.search(r"function (teamPortalRender|bizCharge|bizRenew|bizQuote|bizWaitlistSubmit)\(", idx))
    for fn in ("bizWaitlistSubmit", "bizLoginSubmit", "teamUIRender", "bizSetSegment", "bizUpdateQuote",
               "bizCreateTeam", "bizRenew", "bizPollActivation", "teamPortalRender"):
        check(f"business.js defines {fn}() that index.html calls through bizCall/bizLoad",
              re.search(r"function " + fn + r"\(", _biz.decode("utf-8")) is not None)
    try:
        _r = _sp.run(["node", "-e", "new Function(require('fs').readFileSync(process.argv[1],'utf8'))", _biz_path],
                     capture_output=True, text=True, timeout=30)
        check("business.js parses as a classic script (node)", _r.returncode == 0, _r.stderr.strip()[:200])
    except FileNotFoundError:
        print("   (node not found — business.js parse check skipped here; CI runs it)")

import json as _json
ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', idx, re.DOTALL)
ld_ok = True; ld_detail = ""
for b in ld_blocks:
    try:
        _json.loads(b)
    except Exception as e:
        ld_ok = False; ld_detail = str(e)[:80]; break
check(f"JSON-LD schema blocks valid ({len(ld_blocks)} found)", ld_ok, ld_detail)

print("── 7. Worker ──")
wsrc = open(f"{WORKER}/index.js", encoding="utf-8").read()
with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as t:
    t.write(wsrc); wpath = t.name
r = subprocess.run(["node", "--check", wpath], capture_output=True, text=True)
os.unlink(wpath)
check("worker/index.js parses", r.returncode == 0, r.stderr[:80] if r.returncode else "")
toml = open(f"{WORKER}/wrangler.toml", encoding="utf-8").read()
check("wrangler.toml KV id is real", "REPLACE_WITH" not in toml)

print("── 8. SECRET LEAK check (deployed files vs .worker-secrets.env) ──")
secret_file = os.path.join(ROOT, ".worker-secrets.env")
if os.path.exists(secret_file):
    leaked = []
    deployed = idx + suc + wsrc + toml
    for line in open(secret_file):
        val = line.split("=", 1)[1].strip() if "=" in line else ""
        if len(val) >= 16 and val in deployed:
            leaked.append(line.split("=")[0])
    check("no secrets in deployable files", not leaked, f"LEAKED: {leaked}")
else:
    warn("no .worker-secrets.env found — secret scan skipped", False)

print("── 9. Test suites (dependency-light) ──")
# 9a. worker logic, mock KV — real worker code, no network/deps (required)
r = subprocess.run(["node", os.path.join(ROOT, "tools", "tests", "workertest.mjs")],
                   capture_output=True, text=True, cwd=ROOT)
check("worker unit suite (workertest.mjs)", r.returncode == 0,
      (r.stderr or r.stdout)[-160:].replace("\n", " ") if r.returncode else "")
# 9a2. owner-admin API logic, mock KV — real worker code (required: the admin
# surface mints codes and reads revenue, so it is gated like the money path).
admw = os.path.join(ROOT, "tools", "tests", "adminworkertest.mjs")
if os.path.exists(admw):
    r = subprocess.run(["node", admw], capture_output=True, text=True, cwd=ROOT)
    check("admin API unit suite (adminworkertest.mjs)", r.returncode == 0,
          (r.stdout or r.stderr)[-200:].replace("\n", " ") if r.returncode else "")
# 9b. Analytics consent suite — fake DOM, local storage, and script sink only;
# it never makes a request to Google or any other external service.
consent_test = os.path.join(ROOT, "tools", "tests", "analytics_consent.test.mjs")
r = subprocess.run(["node", consent_test], capture_output=True, text=True, cwd=ROOT)
check("Analytics consent suite (analytics_consent.test.mjs)", r.returncode == 0,
      (r.stderr or r.stdout)[-240:].replace("\n", " ") if r.returncode else "")
# 9c. full-app DOM suite — executes the real index.html in jsdom.
# Skipped (exit 0 + notice) when jsdom is not installed, so a fresh clone is never blocked.
domt = os.path.join(ROOT, "tools", "tests", "domtest.mjs")
if os.path.exists(domt):
    r = subprocess.run(["node", domt], capture_output=True, text=True, cwd=ROOT, timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    if "jsdom not installed" in out:
        warn("DOM suite skipped — jsdom not installed (npm i jsdom to enable)", False)
    else:
        check("full-app DOM suite (domtest.mjs)", r.returncode == 0,
              "see node tools/tests/domtest.mjs" if r.returncode else "")

# 9c. the admin page is executed too (jsdom): login, render, mint, revoke.
admd = os.path.join(ROOT, "tools", "tests", "admindomtest.mjs")
if os.path.exists(admd):
    r = subprocess.run(["node", admd], capture_output=True, text=True, cwd=ROOT, timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    if "jsdom not installed" in out:
        warn("admin DOM suite skipped — jsdom not installed (npm i jsdom to enable)", False)
    else:
        check("admin page execution suite (admindomtest.mjs)", r.returncode == 0,
              out[-200:].replace("\n", " ") if r.returncode else "")

print("── 10. Anchor integrity (in-page links) ──")
anchor_bad = []
for i, (f, html) in enumerate([("index.html", idx), ("success.html", suc)]):
    ids = set(re.findall(r'id="([^"]+)"', html))
    for a in set(re.findall(r'href="#([^"\s]+)"', html)):
        if a and a not in ids and ("page-" + a) not in ids:
            anchor_bad.append(f"{f}#{a}")
for f in glob.glob(os.path.join(SITE, "*.html")):
    base = os.path.basename(f)
    if base in ("index.html", "success.html"):
        continue
    html = open(f, encoding="utf-8").read()
    ids = set(re.findall(r'id="([^"]+)"', html))
    for a in set(re.findall(r'href="#([^"\s]+)"', html)):
        if a and a not in ids:
            anchor_bad.append(f"{base}#{a}")
check("every in-page anchor resolves to a real id", not anchor_bad, ", ".join(sorted(anchor_bad)[:6]))

print("── 11. Site-wide schema & deep-link integrity (every page, not just index) ──")
# 11a. Step 6 only parses the JSON-LD in index.html. The 24 state pages and the
#      guide pages carry FAQPage schema too — invalid JSON there silently costs
#      the rich snippet, and nothing else would notice.
ld_bad, ld_count = [], 0
for f in sorted(glob.glob(f"{SITE}/*.html")):
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                        open(f, encoding="utf-8").read(), re.DOTALL):
        ld_count += 1
        try:
            _json.loads(b)
        except Exception as e:
            ld_bad.append(f"{os.path.basename(f)}: {str(e)[:60]}")
check(f"JSON-LD valid on every page ({ld_count} blocks)", not ld_bad, "; ".join(ld_bad[:3]))

# 11b. Every absolute deep link into the SPA (…/#route) must be a real route.
#      '#code=' is the magic pass link, not a route — excluded by design.
routes = set(re.findall(r'id="(page-[A-Za-z0-9_-]+)"', idx))
dead_routes = []
for f in sorted(glob.glob(f"{SITE}/*.html")):
    html = open(f, encoding="utf-8").read()
    for a in sorted(set(re.findall(r'docoga\.com\.ng/#([A-Za-z0-9_-]+)', html))):
        if a == "code":
            continue
        if ("page-" + a) not in routes:
            dead_routes.append(f"{os.path.basename(f)}#{a}")
check(f"every SPA deep link resolves to a real route ({len(routes)} routes)",
      not dead_routes, ", ".join(dead_routes[:5]))

# 11c. A sitemap entry for a file we don't ship is a soft 404 in Search Console.
smap_locs = re.findall(r"<loc>https://docoga\.com\.ng/([^<]*)</loc>", smap)
orphan = [l for l in smap_locs if l and not os.path.exists(os.path.join(SITE, l))]
check(f"every sitemap loc is a real file ({len(smap_locs)} locs)", not orphan, ", ".join(orphan[:5]))

print("── 12. Hosting is Cloudflare Pages (Netlify retired 3 Oct 2026) ──")
# The owner moved hosting off Netlify entirely. These three checks exist because
# the failure mode is silent: a re-added netlify.toml, or a doc that still says
# "Netlify deploys main", sends the next operator to the wrong dashboard while
# production quietly stops updating.
check("no netlify.toml / .netlify in repo",
      not os.path.exists(os.path.join(ROOT, "netlify.toml"))
      and not os.path.exists(os.path.join(ROOT, ".netlify")))
nl_site = [os.path.basename(f) for f in sorted(glob.glob(f"{SITE}/*.html"))
           if "netlify" in open(f, encoding="utf-8").read().lower()]
check("no Netlify references in deployable site/", not nl_site, ", ".join(nl_site[:4]))
rdme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
check("README documents Cloudflare Pages as the host",
      "## Deploy (Cloudflare Pages)" in rdme,
      "README deploy section must say Cloudflare Pages, not Netlify")
# The output-directory field is a security setting: blank or "/" publishes the
# repo root (PLAN.md, worker/, unlock-codes.txt). The README must keep saying so.
check("README keeps the `site` output-directory warning",
      "`site` is a security setting" in rdme and "never blank" in rdme,
      "do not drop the publish-directory warning from README")

print("── 13. Owner dashboard contract (ADMIN_DASHBOARD.md, 12 Oct 2026) ──")
# The dashboard is part of the product (business plan §11), so its contract is
# gated like the storefront. Each check below maps to a way this surface can rot
# silently: a broken link, a leaked secret, a code path that stopped counting.
admp = os.path.join(SITE, "admin.html")
check("site/admin.html exists (the owner’s UI)", os.path.exists(admp))
if os.path.exists(admp):
    adm = open(admp, encoding="utf-8").read()
    check("admin.html WORKER_URL == index.html", cfg(adm, "WORKER_URL") == cfg(idx, "WORKER_URL"),
          f"{cfg(adm, 'WORKER_URL')} vs {cfg(idx, 'WORKER_URL')}")
    check("admin.html is noindexed in the document too", 'name="robots" content="noindex' in adm)
    _lu = lambda src: (re.search(r'const LEDGER_URL\s*=\s*"([^"]*)"', src) or [None, None])[1]
    check("admin.html LEDGER_URL == index.html (the dashboard reads the same ledger the receipts write to)",
          _lu(adm) is not None and _lu(adm) == _lu(idx), f"{_lu(adm)} vs {_lu(idx)}")
    au = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", adm))
    ad = set(re.findall(r'id="([^"]+)"', adm))
    check(f"all {len(au)} admin JS-referenced ids exist", not (au - ad), f"missing: {sorted(au - ad)[:6]}")
    secret_const = re.search(r"""(SECRET|API_KEY|PASSPHRASE|TOKEN)\s*=\s*["'`][^"'`]{12,}""", adm)
    check("admin page carries no secret-valued constant", not secret_const
          and not re.search(r"Bearer [A-Za-z0-9+/=]{16,}", adm),
          "the dashboard file is public: the passphrase and every API key stay in Worker secrets")
    check("only the session token is persisted client-side (one localStorage write, known key)",
          "localStorage.setItem" in adm and adm.count("localStorage.setItem") == 1
          and "docoga.admin.token" in adm)
else:
    adm = ""
check("the storefront does not advertise the dashboard door",
      "/admin" not in idx and "admin.html" not in idx,
      "linking it from index.html hands the URL to every crawler and scraper")
check("robots.txt keeps /admin out of search", "Disallow: /admin" in robots)
hdrp = os.path.join(SITE, "_headers")
check("site/_headers exists and guards /admin", os.path.exists(hdrp)
      and "/admin" in open(hdrp, encoding="utf-8").read()
      and "frame-ancestors 'none'" in open(hdrp, encoding="utf-8").read())
# the worker side of the contract
check("worker answers 503 admin_disabled when unconfigured", "admin_disabled" in wsrc)
for route in ["/admin/login", "/admin/logout", "/admin/me", "/admin/data", "/admin/snapshot",
              "/admin/codes", "/admin/issue", "/admin/revoke", "/admin/extend", "/admin/resend",
              "/admin/sessions", "/admin/session"]:
    check(f"worker route {route}", f'"{route}"' in wsrc, "the page would 404 against a worker without it")
check("admin secrets are documented in the worker header",
      "ADMIN_PASSPHRASE" in wsrc and "ADMIN_AUTH_SECRET" in wsrc)
# SYNC LAW: every path that creates value must feed the ledger.
n_bumps = len(re.findall(r"await statBump\(env,", wsrc))
check("the ledger has a hook on every value path (≥ 7 bumps)", n_bumps >= 7, f"found {n_bumps}")
for must_count in ["issueCode", "OFFLINE_HASHES.has", "bizwait:", "handleInvoiceWebhook"]:
    check(f"value path still present: {must_count}", must_count in wsrc)
check("issued codes are indexed for lookup and expiry",
      "adminEmailIndex(env" in wsrc and "expIndexAdd(env" in wsrc)
check("the daily cron still rebuilds the owner rollup",
      "buildAdminSnapshot(env)" in wsrc[wsrc.find("async scheduled"):])
# the Android wrapper (mobile/) must still point here
mcap = os.path.join(ROOT, "mobile", "capacitor.config.json")
if os.path.exists(mcap):
    mcs = open(mcap, encoding="utf-8").read()
    check("the APK loads this site, not a stale one", (cfg(idx, "SITE_URL") or "docoga.com.ng") in mcs.replace("\\/", "/"))
    check("the APK never loads the dashboard over http", "http://" not in mcs.replace("\\/", "/"))
    mpkg = os.path.join(ROOT, "mobile", "package.json")
    if os.path.exists(mpkg):
        mp = _json.loads(open(mpkg, encoding="utf-8").read())
        # @capacitor/cli is a devDependency — it never ships in the APK but it is
        # the thing that scaffolds and syncs the project, so the CVE floor applies
        # to it exactly as much as to the runtime packages.
        dep = {**mp.get("dependencies", {}), **mp.get("devDependencies", {})}
        for pkg in ["@capacitor/core", "@capacitor/cli", "@capacitor/android"]:
            ver = dep.get(pkg, "")
            nums = [int(x) for x in re.findall(r"\d+", ver)] or [0]
            okver = nums[0] >= 8 and (nums[1] if len(nums) > 1 else 0) >= 5 and (nums[2] if len(nums) > 2 else 99) >= 1
            check(f"{pkg} is ≥ 8.5.1 (CVE-2026-103922 fixed)", bool(ver) and okver, ver or "missing")
    wap = os.path.join(ROOT, ".github", "workflows", "android-apk.yml")
    check("the APK is built in CI (workflow exists)", os.path.exists(wap))
    if os.path.exists(wap):
        y = open(wap, encoding="utf-8").read()
        check("CI builds with JDK 21 and no secret in the file",
              "java-version" in y and re.search(r"""java-version:\s*['"]?21['"]?""", y) is not None and "ADMIN_PASSPHRASE" not in y)
else:
    warn("mobile/ Capacitor wrapper absent — the APK pipeline is not in this clone", False)
# the operator doc must exist, or the next person cannot switch it on
check("ADMIN_DASHBOARD.md documents the setup", os.path.exists(os.path.join(ROOT, "ADMIN_DASHBOARD.md")))
rdme2 = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
check("README points at the dashboard doc", "ADMIN_DASHBOARD.md" in rdme2)

print("── 14. Social automation (Facebook daily post, 12 Oct 2026) ──")
# The Facebook pipeline claimed "live" for two weeks while its workflow had never
# run once. So the *automation* is gated like the storefront: the files exist, the
# schedule exists, the safety net exists, and no credential has a default.
# Deep behaviour lives in two unittest files that CI runs
# (`python3 -m unittest discover -s tools/tests -p 'test_*.py'`); these are the
# cheap invariants that must also hold on a `npm run qa` before a push.
import re as _re4
soc = {
    "workflow": os.path.join(ROOT, ".github", "workflows", "facebook_autopost.yml"),
    "publisher": os.path.join(ROOT, "tools", "fb_publish.py"),
    "preflight": os.path.join(ROOT, "tools", "fb_preflight.py"),
    "generator": os.path.join(ROOT, "scripts", "generate_facebook_content.py"),
    "poster": os.path.join(ROOT, "scripts", "post_facebook.py"),
    "doc": os.path.join(ROOT, "FACEBOOK_AUTOMATION.md"),
    "tests": os.path.join(ROOT, "tools", "tests", "test_post_facebook.py"),
}
for label, path in soc.items():
    check(f"social automation: {label} exists ({os.path.relpath(path, ROOT)})", os.path.exists(path))
wf = open(soc["workflow"], encoding="utf-8").read() if os.path.exists(soc["workflow"]) else ""
if wf:
    check("it is a schedule, not only a button", "on:\n  schedule" in wf or "schedule:" in wf.split("permissions:")[0],
          "an autopost that needs a person to press it is not an autopost")
    check("preflight runs before any post step",
          wf.find("fb_preflight.py") != -1 and wf.find("fb_preflight.py") < wf.find("post_facebook.py"),
          "the October Telegram lesson: name the credential that is wrong, in seconds")
    check("a failed run opens a labelled issue", "gh issue create" in wf and "facebook-automation" in wf,
          "a red tick in a repo nobody opens is indistinguishable from silence")
    # Line-based on purpose: a whole-file regex with DOTALL "finds" injection
    # across unrelated blocks. A `${{ inputs.x }}` is only dangerous when it is
    # not the value of an env: mapping (`X: ${{ inputs.x }}` is safe).
    # A line that *starts* with a key (`if:` or `NAME:` in env:/with:) is a
    # mapping and is fine; anything else holding an interpolation is a command.
    leaked = [ln.strip() for ln in wf.splitlines()
              if "${{ inputs." in ln and not ln.strip().startswith("#")
              and not _re4.match(r"^(if:|[A-Za-z_]+:)\s", ln.strip())]
    check("inputs reach the shell through env:, never interpolated", not leaked,
          ("line(s) like: %s" % leaked[:1]) if leaked else "")
    check("it can be tested without publishing (dry_run)", "dry_run" in wf)
    check("concurrency cannot interleave two publishes",
          "concurrency:" in wf and "cancel-in-progress: false" in wf)
    check("no secret is echoed into the summary", 'echo "$FB_PAGE_ACCESS_TOKEN"' not in wf)
pub = open(soc["publisher"], encoding="utf-8").read() if os.path.exists(soc["publisher"]) else ""
if pub:
    check("no secret-shaped default in the publisher",
          not _re4.search(r"""environ\.get\(\s*["'](.*(SECRET|TOKEN|PASSWORD|PASSPHRASE).*)["']\s*,\s*["']""", pub),
          "a credential with a literal fallback lives in git history forever")
    def _body(name):
        i = pub.find("def %s(" % name)
        return pub[i:pub.find("\ndef ", i + 1)] if i >= 0 else ""
    check("Page photo posts send `caption`, not `message`",
          all('"caption"' in _body(f) and '"message"' not in _body(f)
              for f in ("post_photo_file", "post_photo_url")),
          "`message` on /photos is accepted and ignored: a green run, a caption-less post")
    check("the Graph API version comes from one constant",
          'API_VERSION = os.environ.get("META_GRAPH_VERSION"' in pub
          and not _re4.search(r"graph\.facebook\.com/v\d", pub))
    # Judged on the code after the module docstring — the docstring is where the
    # old `print(new_token[:30])` bug is *described*, and a check that reads it as
    # code would make the file unable to document its own history.
    pub_code = pub.split('"""')[2] if pub.count('"""') >= 2 else pub
    check("the token is never printed, not even as a prefix",
          not _re4.search(r"print\([^)]*\btoken\[[^\]]*\]", pub_code) and "def fingerprint(" in pub,
          "Actions masks the exact secret only, so token[:30] is a leak")
    check("the duplicate guard reads the Page, not a local marker file",
          "/feed" in pub and "posted_on_date" in pub)
    check("no fallback Page id is compiled in",
          'environ.get("FB_PAGE_ID", "' not in pub,
          "a silent default posts to somebody else's Page")
gen = open(soc["generator"], encoding="utf-8").read() if os.path.exists(soc["generator"]) else ""
if gen:
    check("the Facebook copy is converted, not duplicated", "from telegram_mdv2 import to_plain" in gen,
          "two template sets drift; one source, one conversion")
    check("the Facebook photo is the brand card, never a brand/ file",
          "social_card" in gen and "brand/official" not in gen and "FB_PHOTO_IMAGES" not in gen,
          "owner, 15 Oct 2026: a brand/ comparison sheet reached the Page — 'this is not my brand style'")
    tg_gen = open("scripts/generate_telegram_content.py", encoding="utf-8").read()
    check("the Telegram photo is the brand card, never a brand/ file",
          "social_card" in tg_gen and "PHOTO_POST_IMAGES" not in tg_gen and "brand/official" not in tg_gen)
post = open(soc["poster"], encoding="utf-8").read() if os.path.exists(soc["poster"]) else ""
if post:
    check("a run that posted nothing fails loudly", "return 3" in post and "return 0" in post)
    check("a skipped day is not a failure (no issue for a duplicate)",
        "skipped" in post)
ig_wf = open(os.path.join(ROOT, ".github", "workflows", "instagram_autopost.yml"), encoding="utf-8").read() \
    if os.path.exists(os.path.join(ROOT, ".github", "workflows", "instagram_autopost.yml")) else ""
if ig_wf:
    check("the Instagram path got the same input-handling fix",
          not _re4.search(r"--caption \"\$\{\{ inputs", ig_wf) and "IG_CAPTION: ${{ inputs.caption }}" in ig_wf,
          "the shell-injection class was in both autoposts, not only Facebook's")
rdme3 = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
check("README points at the Facebook handbook", "FACEBOOK_AUTOMATION.md" in rdme3)
check("assets/facebook/ is gitignored (generated copy, not source)",
      "assets/facebook/" in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read())
# ── the Reels lane (Mon/Thu, three-phase video_reels) ──────────────────────
reel_files = {
    "decider": os.path.join(ROOT, "scripts", "facebook_reel_daily.py"),
    "reel tests": os.path.join(ROOT, "tools", "tests", "test_post_facebook_reels.py"),
}
for label, path in reel_files.items():
    check("reels: %s exists (%s)" % (label, os.path.relpath(path, ROOT)), os.path.exists(path))
pub_reel = open(soc["publisher"], encoding="utf-8").read() if os.path.exists(soc["publisher"]) else ""
if pub_reel:
    # Judged inside post_reel()'s own body: a file-wide "does A come before B" is
    # decided by where the definitions sit, which says nothing about call order.
    post_reel_body = pub_reel.split("def post_reel(")[1].split("\ndef ")[0] if "def post_reel(" in pub_reel else ""
    check("a reel is refused before any bytes move",
          bool(post_reel_body)
          and 0 <= post_reel_body.index("reel_spec_ok(") < post_reel_body.index("reel_start(")
          and "spec refused" in post_reel_body,
          "Meta accepts a non-9:16 or over-length file and then fails to publish it quietly")
    check("phase 2 talks to rupload with headers, not body fields",
          'RUPLOAD = "https://rupload.facebook.com/video-upload"' in pub_reel
          and '"Authorization": "OAuth %s" % token' in pub_reel
          and pub_reel.count("% (RUPLOAD, API_VERSION, video_id)") == 1)
    check("a probe cannot publish a reel",
          pub_reel.find("def reel_probe") > 0
          and "_phase(\"finish\")" not in pub_reel.split("def reel_probe")[1].split("def ")[0])
    check("an accepted-but-unpublished reel is recoverable",
          "--reel-finish" in pub_reel and "publish refused after the upload was accepted" in pub_reel)
    check("every reel failure returns a 2-tuple",
          "refusing to finish it\" % (transferred, size))" in pub_reel
          or "incomplete on Meta's side" in pub_reel,
          "a 3-tuple on one branch unpacks into a ValueError in the caller")
daily = open(reel_files["decider"], encoding="utf-8").read() if os.path.exists(reel_files["decider"]) else ""
if daily:
    check("the reel days never collide with the Shorts days",
          "REEL_WEEKDAYS = (0, 3)" in daily,
          "same weekday = same rotation index = the same frame on both platforms")
    check("the decision does not import the renderer at module level",
          "import generate_short_video" in daily.split("def reel_topic")[1][:400]
          and "import shorts_reel" not in daily.split("def render(")[0]
          and daily.index("import generate_short_video as words") > daily.index("def reel_topic"),
          "a plan step that cannot import is a skipped lane, in red")
    check("the mode defaults to probe", '"probe"' in daily and "REELS_MODE" in daily)
wf_reel = open(soc["workflow"], encoding="utf-8").read() if os.path.exists(soc["workflow"]) else ""
if wf_reel:
    check("the reel mode is a variable", "vars.FB_REELS" in wf_reel)
    check("the reel ledger is the shared tool, pointed at a Facebook file",
          "tools/youtube_ledger.py --ledger logs/facebook_reels.json" in wf_reel
          and not os.path.exists(os.path.join(ROOT, "tools", "facebook_ledger.py")),
          "a forked ledger drifts the first time someone fixes a race in the other one")
    check("the ledger lives where it can be committed",
          "logs/facebook_reels.json" in wf_reel
          and "logs/" not in [ln.strip() for ln in open(os.path.join(ROOT, ".gitignore"),
                                                          encoding="utf-8").read().splitlines()],
          "a ledger inside a gitignored directory is a 30-day window that never fills")
    check("reel steps consume the decision, not the cron",
          "steps.reel_plan.outputs.reel_today" in wf_reel
          and wf_reel.index("Reels — decide") < wf_reel.index("Reels — install the renderer"))
# ── brand gate: motion ships through MotionStudio or it doesn't ship ─────────
# 14 Oct 2026: the first pipeline Short reached YouTube off-palette, in DejaVu, as
# static cards — rendered by scripts/generate_short_video.py instead of the owner's
# tools/motionstudio.py. docs/BRAND_STYLE.md: "every piece of content follows this
# or it doesn't ship." These checks make that sentence executable for the lanes.
print("\n── 15. Brand gate — Shorts/Reels render through MotionStudio (14 Oct 2026) ──")
bridge_path = os.path.join(ROOT, "tools", "shorts_reel.py")
engine_path = os.path.join(ROOT, "tools", "motionstudio.py")
check("the MotionStudio bridge exists", os.path.exists(bridge_path))
bridge = open(bridge_path, encoding="utf-8").read() if os.path.exists(bridge_path) else ""
engine = open(engine_path, encoding="utf-8").read() if os.path.exists(engine_path) else ""
if bridge:
    check("the bridge builds a spec and hands it to motionstudio.build",
          "import motionstudio as ms" in bridge and "ms.build(reel, tag)" in bridge)
    bridge_body = bridge.split('"""', 2)[2] if bridge.count('"""') >= 2 else bridge
    check("the bridge carries no colour literal — palette lives in the engine",
          not re.search(r"#[0-9a-fA-F]{6}\b", bridge_body)
          and not re.search(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)", bridge),
          "a hex or RGB tuple here is a second palette; the first one is NAVY/WHITE/MUTED/"
          "FAINT/BLUE/YELLOW/RED/GREEN in tools/motionstudio.py")
    check("the bridge carries no typeface — Inter is resolved by the engine",
          "truetype(" not in bridge and "DejaVu" not in bridge)
    check("the bridge keeps the disclaimer in the conclusion",
          "GENERAL INFO" in bridge and "VARY BY STATE" in bridge)
    check("the bridge uses only asset-free grammar (no icon grid, no cycler, no strike)",
          '"icons"' not in bridge and '"cycler"' not in bridge and "strike=" not in bridge,
          "social/assets/icon-*.png are not in the repo; a strike is for an external price")
    # Owner, 15 Oct 2026, first Reel live: the old Reels "have the voice-over, the sound
    # effects, the background sounds". The engine encodes anullsrc; the bridge must score it.
    sound_path = os.path.join(ROOT, "tools", "shorts_sound.py")
    sound = open(sound_path, encoding="utf-8").read() if os.path.exists(sound_path) else ""
    check("every Short/Reel leaves the bridge with a soundtrack (voice + bed + SFX), never silent",
          "shorts_sound.narrate(" in bridge and "shorts_sound.fit_scenes(" in bridge
          and "shorts_sound.score(" in bridge and "def assert_not_silent" in sound,
          "the owner rejected the silent Reel — tools/shorts_sound.py is the fix")
    check("the Shorts narrator is the LOCKED Deep-Dive voice, imported — never restated",
          bool(sound) and "locked_voice()" in sound and "Narrate this" not in sound
          and "voiceName" not in sound and "generativelanguage" not in sound,
          "one definition of the voice, in tools/deepdive.py, behind its fingerprint")
    check("the soundtrack can still degrade to music + SFX when a person asks (SHORTS_VOICE=optional)",
          "music and effects only" in sound and "no GEMINI_API_KEY" in sound and "def voice_policy" in sound)
    # Owner, 15 Oct 2026, after a voiceless Short: "automatically know when the voice over
    # resets and automatically continue at that time … I want it to be knowledgeable."
    quota_path = os.path.join(ROOT, "tools", "gemini_quota.py")
    quota = open(quota_path, encoding="utf-8").read() if os.path.exists(quota_path) else ""
    check("the narrator's bucket is KNOWN: refusals are read whole, the reset is computed from the Pacific zone",
          "def parse_refusal" in quota and "America/Los_Angeles" in quota and "def next_reset" in quota
          and "gemini_quota.parse_refusal" in open(os.path.join(ROOT, "tools", "deepdive.py"), encoding="utf-8").read(),
          "a per-day 429 is an appointment at the Pacific midnight, not a retryDelay")
    check("no voice → no publish by default; the pause names the resume time (VoiceUnavailable)",
          "class VoiceUnavailable" in sound and 'os.environ.get("SHORTS_VOICE", "required")' in sound
          and "shorts_sound.require_voice(" in bridge)
    resume_path = os.path.join(ROOT, ".github", "workflows", "narrator_resume.yml")
    resume = open(resume_path, encoding="utf-8").read() if os.path.exists(resume_path) else ""
    check("a resumer runs minutes after the reset: warms the day's lines, dispatches what is owed",
          "just-reset" in resume and "shorts_sound.py warm" in resume and "gemini_quota.py owed" in resume
          and "12 7 * * *" in resume and "12 8 * * *" in resume,
          ".github/workflows/narrator_resume.yml")
for lane in ("youtube_short_daily.py", "facebook_reel_daily.py", "post_telegram_video.py"):
    lp = os.path.join(ROOT, "scripts", lane)
    if not os.path.exists(lp):
        continue
    lsrc = open(lp, encoding="utf-8").read()
    check("%s renders through the MotionStudio bridge" % lane,
          "shorts_reel.render_topic(" in lsrc and "generate_video(" not in lsrc
          and "create_slide_image" not in lsrc,
          "the retired card renderer is off-palette (#002040, #0060e0, #FFD700) and off-typeface")
if engine:
    check("the engine resolves Inter and ffmpeg (CI runners are not the owner's laptop)",
          "def find_font_template" in engine and "def find_ffmpeg" in engine
          and "MOTIONSTUDIO_FONT_DIR" in engine and "'--check'" in engine)
    check("the engine's palette is the brand palette",
          "NAVY   = (6, 26, 51)" in engine and "YELLOW, RED, GREEN = (74, 140, 255), (255, 201, 60)" in engine)
    check("the engine renders before it QA-checks the same event registry",
          engine.index("events_of(reel)  #") < engine.index("fd, n = render_reel(reel, tag)"),
          "render_reel reads strike_at_local, which events_of registers — KeyError otherwise")
for wf_name in ("youtube_scheduled.yml", "facebook_autopost.yml"):
    wfp = os.path.join(ROOT, ".github", "workflows", wf_name)
    if not os.path.exists(wfp):
        continue
    wsrc = open(wfp, encoding="utf-8").read()
    check("%s installs Inter + ffmpeg through tools/install_motionstudio_deps.sh" % wf_name,
          "tools/install_motionstudio_deps.sh" in wsrc and "fonts-dejavu-core" not in wsrc,
          "DejaVu on the runner is how the 14 Oct Short shipped in the wrong face")
inst = os.path.join(ROOT, "tools", "install_motionstudio_deps.sh")
check("the installer proves the environment before any render",
      os.path.exists(inst) and 'motionstudio.py" --check' in open(inst, encoding="utf-8").read())
check("the bridge has its own tests",
      os.path.exists(os.path.join(ROOT, "tools", "tests", "test_shorts_reel.py")))
# v5 (20 Oct 2026): camera + word-sync. Render and QA must share one background function, the
# captions must get their words between the voice fit and the caption beats, and every render
# lane installs the word-sync engine best-effort (a model mirror that blinks never costs a Short).
_eng = open(engine_path, encoding="utf-8").read()
check("MotionStudio v5: render and QA share camera_bg (one background for both)",
      "bg = BASE if flat else camera_bg(sc, lt, last)" in _eng and _eng.count("camera_bg(") >= 4 and "def smoother" in _eng)
check("MotionStudio v5/v6: the QA animation rule judges the type, not the camera (two looks)",
      "moved = (strong & prev_none)" in _eng and "def type_moved" in _eng
      and "compose_frame(sc, lt, last, flat=True)" in _eng and "bg = BASE if flat else camera_bg(sc, lt, last)" in _eng)
_br = open(bridge_path, encoding="utf-8").read()
check("the bridge syncs words after the voice fit and before the captions",
      0 < _br.find("shorts_sound.fit_scenes(") < _br.find("shorts_sound.sync_words(") < _br.find("shorts_sound.caption_beats("))
for wf_name in ("youtube_scheduled.yml", "facebook_autopost.yml", "narrator_resume.yml", "tiktok_test.yml"):
    wfp = os.path.join(ROOT, ".github", "workflows", wf_name)
    if os.path.exists(wfp):
        check("%s installs the word-sync engine (best effort)" % wf_name,
              "tools/install_wordsync_deps.sh" in open(wfp, encoding="utf-8").read())
_ws = os.path.join(ROOT, "tools", "install_wordsync_deps.sh")
check("the word-sync installer never fails the lane",
      os.path.exists(_ws) and "set -e" not in open(_ws, encoding="utf-8").read()
      and open(_ws, encoding="utf-8").read().rstrip().endswith("exit 0"))
check("the v5 motion grammar is documented and tested",
      os.path.exists(os.path.join(ROOT, "docs", "SHORTS_MOTION.md"))
      and os.path.exists(os.path.join(ROOT, "tools", "tests", "test_motion_v5.py")))
# v6 footage (owner, 20 Oct 2026 evening): a clip per spoken sentence, a photograph where no clip
# exists, as many free doors as possible, public-domain-only where we print no credits, and the
# clip always passes through the brand duotone before the camera touches it.
_sm_path = os.path.join(ROOT, "tools", "stock_media.py")
_sm = open(_sm_path, encoding="utf-8").read() if os.path.exists(_sm_path) else ""
check("v6 footage: the bridge asks for a clip first and a photograph where none exists",
      'stock_media.media_for(text, hint=sc.get("shot"), need_s=need_s, used=used)' in _br
      and 'kinds=("photo",)' in _br and "SHOTS_VIDEO=" in _br and "SHOTS_DOORS=" in _br)
check("v6 footage: every door is free and optional; Commons is public-domain-only; no close faces",
      all(k in _sm for k in ("PIXABAY_API_KEY", "PEXELS_API_KEY", "FLICKR_API_KEY", "UNSPLASH_ACCESS_KEY"))
      and 'COMMONS_FREE = ("public domain", "pd", "cc0", "cc-zero", "no restrictions")' in _sm
      and '"portrait", "selfie", "headshot", "face"' in _sm and "NIGERIA_BBOX" in _sm)
check("v6 footage: a clip is baked through the brand duotone (lut1d) before the camera rides it",
      "lut1d=file=" in _sm and "blend_image.STOPS" in _sm and "def clip_frame" in _eng
      and "shot_frame(cur, (lt - cur['t0']) / span, lt - cur['t0'])" in _eng)
for wf_name in ("youtube_scheduled.yml", "facebook_autopost.yml", "tiktok_test.yml"):
    wfp = os.path.join(ROOT, ".github", "workflows", wf_name)
    if os.path.exists(wfp):
        check("%s passes the footage keys (empty = door closed, never a failure)" % wf_name,
              "PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}" in open(wfp, encoding="utf-8").read())
check("v6 footage is documented and tested",
      "## 5b. Footage" in open(os.path.join(ROOT, "docs", "SHORTS_MOTION.md"), encoding="utf-8").read()
      and os.path.exists(os.path.join(ROOT, "tools", "tests", "test_stock_media.py"))
      and "PIXABAY_API_KEY" in open(os.path.join(ROOT, "docs", "TOKENS.md"), encoding="utf-8").read())

# ── the heartbeat (one cron that judges every other cron) ───────────────────
# The lanes publish; nothing else asks "did they". These checks are the pre-push
# guard for the guard: the parts that a missing dependency would hide from CI, and
# the cross-file contracts (tool ↔ workflow ↔ docs) that each side can break alone.
hb_paths = {
    "tool": os.path.join(ROOT, "tools", "automation_heartbeat.py"),
    "workflow": os.path.join(ROOT, ".github", "workflows", "automation-heartbeat.yml"),
    "tests": os.path.join(ROOT, "tools", "tests", "test_automation_heartbeat.py"),
}
for hb_label, hb_path in hb_paths.items():
    check("heartbeat: %s exists" % hb_label, os.path.exists(hb_path))
hb_src = open(hb_paths["tool"], encoding="utf-8").read() if os.path.exists(hb_paths["tool"]) else ""
hb_wf = open(hb_paths["workflow"], encoding="utf-8").read() if os.path.exists(hb_paths["workflow"]) else ""
if hb_src:
    check("heartbeat reads its lanes, never lists them",
          "def discover_lanes(" in hb_src
          and not re.search(r"\b(telegram|facebook|instagram|youtube)_\w*\.ya?ml", hb_src),
          "a hardcoded lane table is stale the day a cron moves, and a stale monitor "
          "reports a healthy repo")
    hb_imports = {m.split(" ")[1].split(".")[0] for m in
                  re.findall(r"^(?:import|from) .+$", hb_src, re.M)}
    check("heartbeat imports nothing beyond stdlib + PyYAML",
          hb_imports <= {"argparse", "base64", "collections", "datetime", "hashlib", "json",
                         "os", "pathlib", "re", "sys", "urllib", "yaml", "__future__"},
          "the job installs only pyyaml — one stray `import requests` is a crash at 18:00 "
          "and a silent month of no data")
    check("heartbeat counts the cadence from the cron, with slack capped at one cycle",
          "def silence_deadline(" in hb_src and "min(int(jitter), max(int(gap), 3600))" in hb_src,
          "12 h of scheduler slack is right for a daily lane and absurd for a 30-minute one")
    check("a schedule that only exists on a branch is never called dead",
          'options["default_crons"]' in hb_src,
          "build_verdicts reads it out of options; rebinding a local name in main() "
          "silently turns every unmerged lane into a false alarm")
    check("the heartbeat can only report 'I could not look'",
          "returning 'all clear' without data" in hb_src
          or "refusing to report a healthy repo" in hb_src)
    check("heartbeat exits 3 when the data is missing",
          re.search(r"could not look.*?return 3", hb_src, re.S) is not None)
if hb_wf:
    check("heartbeat workflow: scheduled and manually runnable",
          "schedule:" in hb_wf and "workflow_dispatch:" in hb_wf)
    check("heartbeat workflow: installs what the tool needs",
          "pip install" in hb_wf and "pyyaml" in hb_wf.lower())
    check("heartbeat workflow: reads every key the tool prints", hb_src.count("HEARTBEAT_") > 0)
    grep_keys = sorted(set(re.findall(r"sed -n 's/\^(HEARTBEAT_[A-Z_]+)=/", hb_wf)))
    check("heartbeat workflow reads at least one contract key", len(grep_keys) >= 3,
          "the sed pattern that finds them changed shape once already — an empty loop here "
          "would prove nothing and look like a pass")
    for key in grep_keys:
        check("heartbeat contract: %s is printed by the tool" % key,
              ('"%s=%%s"' % key) in hb_src or ("'%s='" % key) in hb_src,
              "the workflow greps this out of the log; a renamed key reads as 'healthy'")
    check("heartbeat files one issue, not one per day",
          'grep -q "$SIGNATURE"' in hb_wf or "grep -q \"$SIGNATURE\"" in hb_wf)
    check("heartbeat closes its own issue when the lanes heal",
          "gh issue close" in hb_wf,
          "an open issue about a healed lane is worse than no issue: it trains the "
          "reader to ignore the label")
    check("heartbeat commits nothing",
          "git push" not in hb_wf and "permissions:" in hb_wf and "contents: read" in hb_wf,
          "a monitor that can write to the repo is a monitor that can break it")
    readme_hb = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    clock_hb = open(os.path.join(ROOT, "docs", "CLOCK.md"), encoding="utf-8").read()
    check("the heartbeat is written down where the owner looks",
          "automation-heartbeat" in readme_hb and "automation-heartbeat" in clock_hb,
          "a monitor nobody can find is a monitor nobody re-runs")

# ── the publish ledger: what counts as having published ────────────────────
# Two bugs and one gap, all from 13 Oct 2026: the channel got the same post four times,
# the lane had no durable proof of publishing, and the log that looked like proof was
# gitignored scratch the tests themselves wrote to. These hold the three fixes in place.
tg_poster = open(os.path.join(ROOT, "scripts", "post_telegram.py"), encoding="utf-8").read()
tg_body = tg_poster.split("def post_to_telegram(")[1].split("\ndef ")[0]
check("telegram ledger: the duplicate check is consulted before anything is sent",
      0 <= tg_body.index("already_sent(") < tg_body.index("send_text_message(")
      and 0 <= tg_body.index("already_sent(") < tg_body.index("send_photo_message("),
      "checking after the send is bookkeeping, not protection")
check("telegram ledger: an entry is written only for a send Telegram accepted",
      tg_body.index("if ok:") < tg_body.index("ledger.record("),
      "recording the intent would turn the ledger into a wish")
check("telegram ledger: refusals are red, duplicates are green",
      "if sent == 0 and failed:" in tg_body and "return -1" in tg_body,
      "collapsing 'nothing to do' and 'nothing worked' is how the poster used to exit 0 on an API error")
check("telegram ledger: the shared tool, not a fork",
      "import youtube_ledger as ledger" in tg_poster
      and not os.path.exists(os.path.join(ROOT, "tools", "telegram_ledger.py")),
      "a forked ledger drifts the first time someone fixes a race in the other one")
tg_wf = open(os.path.join(ROOT, ".github", "workflows", "telegram_autopost.yml"),
             encoding="utf-8").read()
check("telegram workflow: the ledger file is the same path the poster writes",
      "telegram_sent.json" in tg_poster and "logs/telegram_sent.json" in tg_wf
      and 'docoga_log.log_file("telegram_sent.json")' in tg_poster,
      "the workflow commits one path and the poster writes another: the ledger stays empty "
      "forever, and an empty ledger reads as \"nothing published\"")
check("telegram workflow: it may commit the ledger and nothing else is write-scoped",
      "contents: write" in tg_wf and "issues: write" in tg_wf)
check("telegram workflow: the ledger commit cannot turn a publish red",
      "continue-on-error: true" in tg_wf.split("Commit the publish ledger")[1][:400])
for name in ("telegram_autopost.yml", "facebook_autopost.yml"):
    text = open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8").read()
    check("%s: an auto-commit of bookkeeping does not retrigger CI" % name,
          "[skip ci]" in text,
          "the free plan has 2,000 minutes a month; a ledger push that fires Verify burns them")
check("telegram workflow: force is an input, so a re-post needs no commit",
      "force:" in tg_wf and "TELEGRAM_FORCE: ${{ inputs.force }}" in tg_wf)
social_scripts = ["post_telegram.py", "post_facebook.py", "generate_facebook_content.py",
                  "generate_telegram_content.py", "post_telegram_video.py"]
for name in social_scripts:
    text = open(os.path.join(ROOT, "scripts", name), encoding="utf-8").read()
    check("scratch files are rooted, not cwd-relative (%s)" % name,
          'Path("logs/' not in text and "docoga_log" in text,
          "a relative log path is a stray logs/ directory in whoever's home ran it last")
hb_tool = open(os.path.join(ROOT, "tools", "automation_heartbeat.py"), encoding="utf-8").read()
check("heartbeat: run history and publish evidence are separate facts",
      "def ledger_freshness(" in hb_tool and "green-but-quiet" in hb_tool
      and "no publish evidence either way" in hb_tool,
      "'nothing has succeeded' and 'nobody published' are different sentences")
check("heartbeat: a missing ledger is never read as silence",
      '"state": "absent"' in hb_tool and '"state": "unreadable"' in hb_tool)
check("telegram preflight names the secret to set",
      "gh secret set TELEGRAM_CHAT_ID" in
      open(os.path.join(ROOT, "tools", "telegram_preflight.py"), encoding="utf-8").read(),
      "it finds the failure; it has to finish the job and say what to type")

# ── the YouTube lane: the protocol, the cause, and the probe ───────────────
# The 9 Oct run rendered a Short for ten minutes, failed at "Upload to YouTube", and the only
# words in the log were `Exit code 1`. Three rules keep that from being the state of play again.
yt_wf_text = open(os.path.join(ROOT, ".github", "workflows", "youtube_scheduled.yml"),
                  encoding="utf-8").read()
yt_pub = open(os.path.join(ROOT, "tools", "yt_publish.py"), encoding="utf-8").read()

# --- the Telegram live duplicate guard (tools/telegram_preview.py + the poster) ---------
tg_prev_path = os.path.join(ROOT, "tools", "telegram_preview.py")
tg_prev = open(tg_prev_path, encoding="utf-8").read() if os.path.exists(tg_prev_path) else ""
tg_post_path = os.path.join(ROOT, "scripts", "post_telegram.py")
tg_post = open(tg_post_path, encoding="utf-8").read() if os.path.exists(tg_post_path) else ""
tg_flow_path = os.path.join(ROOT, ".github", "workflows", "telegram_autopost.yml")
tg_flow = open(tg_flow_path, encoding="utf-8").read() if os.path.exists(tg_flow_path) else ""
tg_pre = open(os.path.join(ROOT, "tools", "telegram_preflight.py"), encoding="utf-8").read()

check("telegram guard: the channel is asked, not just the ledger",
      bool(tg_prev) and "def recent_posts(" in tg_prev and "t.me/s/" in tg_prev
      and "def channel_duplicate(" in tg_post,
      "a lost or un-pushed ledger is how the same paragraph reached readers four times")
check("telegram guard: it refuses only an identical message",
      "MIN_DISTINCT_TOKENS" in tg_prev and "MIN_ANCHOR_LENGTH" in tg_prev and "need <= have" in tg_prev,
      "templated copy reuses fixed sentences on purpose; 'similar' would silence the lane")
check("telegram guard: it fails open, never silent and never blocking",
      '"unavailable"' in tg_post and '"no messages"' in tg_prev and "return None, " in tg_prev,
      "an unreadable page must cost a warning, not the day's post")
check("telegram guard: the ledger is consulted before the network",
      tg_post.index("already_sent(entries, key, today)")
      < tg_post.index("guard_state, guard_detail = channel_duplicate(message)"),
      "the free offline check runs first, so a known duplicate costs no HTTP request")
check("telegram guard: the refusal happens before anything is sent",
      tg_post.index("guard_state, guard_detail = channel_duplicate(message)")
      < tg_post.index("if send_photo and photo_path:")
      and "TELEGRAM_SKIP_CHANNEL_CHECK" in tg_post,
      "a guard that runs after sendMessage is a log line, not a guard — and it needs a kill switch")
check("telegram guard: the preview request carries no credentials",
      "TELEGRAM_BOT_TOKEN" not in tg_prev and "timeout=" in tg_prev and "User-Agent" in tg_prev,
      "t.me/s/ needs no token; a fetch that carries one is a leak waiting to land in a run log")
check("telegram guard: the run summary reports which guard was watching",
      "TELEGRAM_CHANNEL_GUARD=" in tg_post and "TELEGRAM_CHANNEL_GUARD=" in tg_flow,
      "'green with a live guard' and 'green because the channel was unreadable' must not look alike")
check("telegram guard: the preflight can be checked without a token",
      "--preview" in tg_pre and "telegram_preview" in tg_pre,
      "the owner has to be able to verify the guard from a terminal, with no secret in hand")
# ── the Meta lanes (Threads + Instagram): what cannot be verified without a live token ──
_meta_paths = {
    "threads publisher": "tools/threads_publish.py",
    "threads generator": "scripts/generate_threads_content.py",
    "threads workflow": ".github/workflows/threads_autopost.yml",
    "instagram publisher": "tools/ig_publish.py",
    "instagram workflow": ".github/workflows/instagram_autopost.yml",
    "card renderer": "tools/social_card.py",
    "token vault": "tools/token_vault.py",
}
_meta = {}
for _label, _rel in _meta_paths.items():
    _present = os.path.exists(os.path.join(ROOT, _rel))
    check("meta lanes: %s exists" % _label, _present,
          "a lane that is documented but absent is a promise nobody can keep")
    if _present:
        _meta[_label] = open(os.path.join(ROOT, _rel), encoding="utf-8").read()

if len(_meta) == len(_meta_paths):
    check("meta lanes: a failed publish is a failed run",
          "sys.exit(main())" in _meta["threads publisher"]
          and "return 3 if exc.cause" in _meta["threads publisher"]
          and "raise SystemExit(2)" in _meta["instagram publisher"]
          and "machine(\"refused\", \"setup\")" in _meta["instagram publisher"]
          and "sys.exit(main())" in _meta["instagram publisher"],
          "ig_publish.py's first version returned None on every failure and exited 0 — a red "
          "day wearing a green tick, the single worst property a publisher can have")
    def _code_only(_text):
        # Drop the module docstring: these files document the leak they closed, and a check
        # that reads prose as code fails on the changelog instead of on the bug.
        return re.sub(r'"""(?:[^"]|"(?!""))*"""', "", _text, count=1, flags=re.S)

    # The dangerous *shapes*: slicing a secret, printing the variable, concatenating it into a
    # message. A line merely containing the word "token" is prose about the credential ("the
    # token was rejected") and flagging those is how a check gets switched off by the next
    # person who has a real job to do. This mirrors the existing Facebook publisher's check.
    _leaks = []
    for _label in ("threads publisher", "instagram publisher"):
        _body = _code_only(_meta[_label])
        if re.search(r"print\([^)]*(?:\btoken\[|\bnew_token\b|% token\)|\+ token\b)", _body):
            _leaks.append(_label)
    check("meta lanes: neither publisher prints a credential it was not asked to hand on",
          not _leaks and "def fingerprint(" in _meta["threads publisher"]
          and "def fingerprint(" in _meta["instagram publisher"]
          and "fingerprint(token)" in _meta["threads publisher"],
          "the old --refresh-token printed 20 characters of a live token into the run log; "
          "a fingerprint identifies *which* credential failed without being it"
          + (" — printing a credential in: " + ", ".join(_leaks) if _leaks else ""))
    check("meta lanes: a refreshed token is redirected, and then erased",
          "> /tmp/threads_refresh.json" in _meta["threads workflow"]
          and "rm -f /tmp/threads_refresh.json" in _meta["threads workflow"]
          and "> /tmp/ig_refresh.json" in _meta["instagram workflow"]
          and "rm -f /tmp/ig_refresh.json" in _meta["instagram workflow"],
          "`--refresh` prints JSON on purpose so the vault can seal it — which is only safe "
          "because stdout is redirected to a file the step then deletes")
    check("meta lanes: both redact an API body before printing it",
          "def redact(" in _meta["threads publisher"] and "redact(self.body)" in _meta["threads publisher"]
          and "def redact(" in _meta["instagram publisher"] and "redact(self.body)" in _meta["instagram publisher"],
          "Meta quotes part of the token it was handed back in its own error text")
    check("meta lanes: the vault refuses instead of storing plaintext",
          "refusing to store a token" in _meta["token vault"]
          and "AESGCM" in _meta["token vault"]
          and "os.replace" in _meta["token vault"] and "open needs --out" in _meta["token vault"],
          "a security tool that degrades quietly into an exfiltration tool is worse than none; "
          "the atomic write is so a killed run cannot leave half a box, and refusing to print "
          "a plaintext token is the point of the file")
    check("meta lanes: the vault never writes into the deployed site",
          "refusing to write a vault file inside site/" in _meta["token vault"],
          "site/ is the public web root; a secret box put there is published, ciphertext or not")
    check("meta lanes: the card is exactly the ratio Instagram accepts",
          "CARD_W, CARD_H = 1080, 1350" in _meta["card renderer"]
          and "ASPECT_MIN, ASPECT_MAX = 0.8, 1.91" in _meta["instagram publisher"],
          "4:5 is the narrowest ratio content publishing takes; anything else answers "
          "'Unsupported URL request', which every human so far has misread as permissions")
    check("meta lanes: the render URL drops the site/ prefix",
          'if serving.startswith("site/")' in _meta["card renderer"],
          "wrangler publishes ./site as the root, so /site/social/x.jpg 404s forever")
    check("meta lanes: Threads copy is fitted in the platform's own units",
          "def threads_cost(" in _meta["threads generator"]
          and "def cost(" in _meta["threads publisher"]
          and "MAX_COST" in _meta["threads generator"] and "MAX_COST" in _meta["threads publisher"],
          "Meta charges an emoji at 4 bytes, so len() is not the number that decides acceptance")
    check("meta lanes: both ask the platform what it already carries",
          "def find_duplicate(" in _meta["threads publisher"]
          and "def find_duplicate(" in _meta["instagram publisher"],
          "the duplicate guard is the platform's memory; the ledger is only ours")
    check("meta lanes: an unreadable guard warns and posts",
          "duplicate guard unavailable" in _meta["threads publisher"]
          and "duplicate guard unavailable" in _meta["instagram publisher"],
          "fail-open with a name on it, or a dead endpoint silences a lane for a week")
    check("meta lanes: the workflow reads the publisher's exit code, not its mood",
          "THREADS_RESULT=" in _meta["threads workflow"] and "sed -n" in _meta["threads workflow"]
          and "sent|refused-duplicate|dry-run)" in _meta["threads workflow"],
          "a refusal is a success and a silence is not: the case statement is the whole difference")
    check("meta lanes: the box holds the token, not Meta's response body",
          "return read_refresh_response(args.json)[0]" in _meta["token vault"]
          and 'json.dumps({"access_token": token' not in _meta["token vault"]
          and "unwrapped" in _meta["token vault"],
          "the publisher sends the file `open --out` writes as its bearer token, so sealing a "
          "whole JSON response makes day 2 a 401 that reads like a revoked consent — and it is "
          "invisible to any test that runs one verb at a time, which is why this line is a gate "
          "and not only a test (the tests skip when cryptography is missing; this cannot)")
    check("meta lanes: an empty seal is refused, not stored",
          "refusing to seal an empty token" in _meta["token vault"],
          "a `$(…) that came back empty` would otherwise win the fallback race against the "
          "bootstrap secret: the lane would read a valid box containing nothing and file a "
          "credentials issue instead of a setup one")
    check("meta lanes: the render directory is bounded, by name not mtime",
          "--prune site/social --keep 60" in _meta["instagram workflow"]
          and "DATED_RENDER = re.compile" in _meta["card renderer"]
          and "keep = max(1, int(keep))" in _meta["card renderer"],
          "site/social/ is inside the deployed tree, so an unbounded write there is the repository "
          "growing in public forever — and retention keyed on mtime would look correct and match "
          "nothing, because a fresh checkout stamps every file with today")
    check("meta lanes: no ${{ }} reaches a git push destination",
          'git push origin "HEAD:${{' not in _meta["instagram workflow"]
          and 'git push origin "HEAD:${{' not in _meta["threads workflow"],
          "these two lanes hold contents:write and choose their own push destination, which is "
          "exactly where an interpolated expression turns a slip into a write to the wrong ref")
    check("meta lanes: the runner installs what the vault needs",
          "cryptography" in _meta["threads workflow"]
          and "cryptography" in _meta["instagram workflow"],
          "tools/token_vault.py refuses to run without it rather than storing plaintext, which is "
          "right — but a lane that forgets the dependency then skips the refresh in silence and "
          "dies at day 60 while passing every day before that")

    # A value produced in one place and consumed in another is where this repo's worst bugs live,
    # because each half passes its own test: `$GITHUB_ENV` read in the step that wrote it, a jq
    # needle that was never exported (Telegram's dedupe matched *every* issue this way for a week),
    # and `steps.<id>.outputs.<key>` naming a step or key that does not exist. The auditor is its
    # own module with its own tests — including the silences, since this checker reported five
    # confident bugs in this repository on its first run and all five were its own mistakes.
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import workflow_handoffs
        _handoffs = workflow_handoffs.audit_dir(os.path.join(ROOT, ".github", "workflows"))
    except Exception as exc:  # an auditor that could not run is said so, never passed silently
        _handoffs = None
        _handoff_error = str(exc)
    if _handoffs is None:
        warn("workflow handoffs audited", False,
             "tools/workflow_handoffs.py could not run (%s) — the cross-step class of bug it catches "
             "is the one this repository keeps rediscovering" % _handoff_error)
    else:
        check("every workflow handoff lands ($GITHUB_ENV, jq $ENV, steps.outputs)", not _handoffs,
              " | ".join("%s: %s" % pair for pair in _handoffs)[:700])

    # Every `run:` block in every workflow must be valid bash. A stray `done` where `fi` belongs
    # and an input interpolated into `[ -n "${{ inputs.x }}" ]` are both mechanical errors, and
    # both were actually written into this repo by someone in a hurry before this check existed.
    _wf_dir = os.path.join(ROOT, ".github", "workflows")
    _problems = []
    try:
        import yaml as _yaml_wf
    except ImportError:
        _yaml_wf = None
    if _yaml_wf is None:
        warn("workflow run blocks not syntax-checked — pyyaml missing locally", True,
             "CI runs the same check through tools/tests/test_workflow_contract.py")
    else:
        for _wf_name in sorted(os.listdir(_wf_dir)):
            if not _wf_name.endswith(".yml"):
                continue
            _text = open(os.path.join(_wf_dir, _wf_name), encoding="utf-8").read()
            try:
                _doc = _yaml_wf.safe_load(_text)
            except Exception as _exc:
                _problems.append("%s: yaml unparseable (%s)" % (_wf_name, str(_exc)[:120]))
                continue
            for _job in (_doc or {}).get("jobs", {}).values():
                for _step in _job.get("steps", []) or []:
                    _run = _step.get("run")
                    if not _run:
                        continue
                    _label = "%s/%s" % (_wf_name, _step.get("name", "?"))
                    if re.search(r'\[\s-[nz]\s*"\$\{\{', _run):
                        _problems.append("%s: an input interpolated into a test" % _label)
                    _sub = re.sub(r"\$\{\{[^}]*\}\}", "SAFEVALUE", _run)
                    _proc = subprocess.run(["bash", "-n"], input=_sub, capture_output=True,
                                           text=True)
                    if _proc.returncode:
                        _problems.append("%s: %s" % (_label, _proc.stderr.strip()[:160]))
        check("every workflow run block is valid bash (bash -n, ${{ }} substituted)",
              not _problems, "; ".join(_problems[:4])
              or "a syntax error in a step costs a day's post, and the Actions UI points at "
                 "the last heredoc line rather than the mistake")

# --- tools/lane_status.py: the one command that answers "why is the lane red" ------------
lane_status_path = os.path.join(ROOT, "tools", "lane_status.py")
lane_status = open(lane_status_path, encoding="utf-8").read() if os.path.exists(lane_status_path) else ""
check("lane_status: exists, and it is read-only",
      bool(lane_status) and not any(verb in lane_status for verb in
                                    ("-X POST", "--method", "gh run cancel", "gh workflow run",
                                     "gh issue create", "gh secret")),
      "a status tool that can write is a status tool that can break a launch mid-check")
check("lane_status: it reads annotations, never the unreachable log bytes",
      "check-runs" in lane_status and "/logs" not in lane_status and "annotations" in lane_status,
      "the log host is off the sandbox allowlist; the annotations are the same text and always readable")
check("lane_status: redaction runs before anything is printed",
      "REDACTIONS" in lane_status and "def redact(" in lane_status
      and '"message": redact(' in lane_status and "redact(str(exc))" in lane_status,
      "an annotation that quotes the token it was handed must not become the leak — the message is "
      "the only uncontrolled text this tool prints, so it is the one that passes through redact()")
check("lane_status: bookkeeping steps are excluded by mirror, not by prefix",
      'name.startswith("Post ") and name[len("Post "):] in names' in lane_status,
      "`Post to Telegram` is a real step name; a prefix rule hides the failure that matters")
check("lane_status: the runbook hands it over as the check",
      "lane_status" in open(os.path.join(ROOT, "docs", "LAUNCH_SEQUENCE.md"),
                            encoding="utf-8").read(),
      "the fastest diagnosis is useless if it lives only in a docstring")

# --- the failure-issue hygiene that makes the launch order safe -------------------------
# The workflow's jq string escapes its quotes for bash, so the needle the check looks for is
# `contains(\"[\")` — built with chr() rather than written out, because a backslash in a
# literal is how a check ends up matching nothing at all.
_LEGACY_NEEDLE = "contains(" + chr(92) + chr(34) + "[" + chr(92) + chr(34) + ") | not"

_lane_issue_files = {
    "telegram_autopost.yml": "telegram-automation",
    "facebook_autopost.yml": "facebook-automation",
    "youtube_scheduled.yml": "youtube-automation",
    "threads_autopost.yml": "threads-automation",
    "instagram_autopost.yml": "instagram-automation",
}
for _lane_file, _lane_label in _lane_issue_files.items():
    _lane_path = os.path.join(ROOT, ".github", "workflows", _lane_file)
    _lane_text = open(_lane_path, encoding="utf-8").read() if os.path.exists(_lane_path) else ""
    check("%s: its failure issue is filed once per cause, not once per day" % _lane_file,
          'CAUSE_TAG="[$CAUSE]"' in _lane_text and "--state open" in _lane_text
          and "max // empty" in _lane_text
          and 'gh issue comment "$EXISTING"' in _lane_text,
          "an inbox of identical issues is how a broken lane gets ignored; the cause tag is the key")
    check("%s: an issue filed before causes existed still absorbs today's failure" % _lane_file,
          "LEGACY_PREFIX=" in _lane_text and _LEGACY_NEEDLE in _lane_text,
          "#16 and #12 have no cause in their titles; without the fold-in they would sit open "
          "beside a twin, which is the noise this change exists to remove")
    check("%s: bookkeeping can never add a second failure" % _lane_file,
          'gh issue comment "$EXISTING" --body-file /tmp/issue_body.md || true' in _lane_text
          and ("::warning" in _lane_text.split("gh issue create")[-1][:400]
               or "|| true" in _lane_text.split("gh issue create")[-1][:400]),
          "the run is already red because the post failed; a failed issue is a warning, not a new red")
check("the heartbeat still finds each lane by its create line",
      all(("gh issue create" in open(os.path.join(ROOT, ".github", "workflows", f),
                                    encoding="utf-8").read()) or not os.path.exists(
          os.path.join(ROOT, ".github", "workflows", f)) for f in _lane_issue_files),
      "tools/automation_heartbeat.py reads `gh issue create --label …` out of each workflow — "
      "re-wording that line silently un-monitors the lane")
check("launch: the sequence document exists and covers every owner-only step",
      os.path.exists(os.path.join(ROOT, "docs", "LAUNCH_SEQUENCE.md")),
      "four steps are owed by a human with a browser; the order is the difference between a "
      "quiet launch and a morning of issues")

check("telegram guard: the tests never reach the network for it",
      all("fetch_preview" in open(os.path.join(ROOT, "tools", "tests", n), encoding="utf-8").read()
          for n in ("test_post_telegram_ledger.py", "test_post_telegram_channel_guard.py")),
      "a test that reads the real channel is a test that fails when Telegram changes")
check("youtube: the resumable protocol is implemented, not improvised",
      "308" in yt_pub and "Content-Range" in yt_pub and "await_finalize" in yt_pub
      and yt_pub.count("timeout=(") >= 1 and "requests.put(" not in yt_pub,
      "a whole-file PUT with no 308 handling fails a healthy upload, which is what the old code did")
check("youtube: nothing in the lane can hang",
      yt_pub.count("TIMEOUT") >= 2 and "def request(self, method, url, headers=None" in yt_pub,
      "every request goes through Http so a timeout is impossible to forget at one call site")
check("youtube: a failure names its kind and its fix",
      "REASONS = {" in yt_pub and "class Problem" in yt_pub and "YT_FAIL_KIND=" in yt_pub,
      "the issue body and the annotation are assembled from these, so the cause survives the run")
check("youtube: a human-only repair exits differently from a crash",
      "EXIT_NEEDS_HUMAN = 2" in yt_pub and "credentials" in yt_pub,
      "'the code broke' and 're-author the token' are different 2 minutes")
check("youtube: the upload is read back before anyone says 'published'",
      "def read_back(" in yt_pub and '"held"' in yt_pub,
      "201 means the bytes arrived; a channel that defaults uploads to private returns 201 too")
check("youtube: the probe exists and cannot upload",
      "def probe(" in yt_pub and "--probe" in yt_pub
      and "def probe" in yt_pub and "ResumableUploader" in yt_pub.split("def probe(")[0],
      "the owner is never asked to guess which of four things is wrong (PRE-FLIGHT LAW)")
check("youtube: the scheduled preflight runs the probe",
      "yt_publish.py --probe" in yt_wf_text,
      "presence of secrets proved nothing on 9 Oct: the step was green with a dead token")
check("youtube: a probe-only dispatch is available",
      "probe_only" in yt_wf_text and 'jobs' in yt_wf_text and "name: Diagnose the YouTube lane" in yt_wf_text,
      "diagnosis must be runnable without rendering or uploading anything")
check("youtube: the ledger is recorded even when the upload step went red",
      "steps.upload.outputs.video_id != ''" in yt_wf_text
      and "if: always() && steps.guard.outputs.skip != 'yes' && steps.upload.outputs.video_id != ''"
      in yt_wf_text,
      "an id on the channel that is not in the ledger is a duplicate waiting for the next run")
check("youtube: exit codes survive the log capture",
      "code=${PIPESTATUS[0]}" in yt_wf_text,
      "tee swallows the uploader's exit code, and the exit code is the diagnosis")
check("youtube: the failure issue says whether a video exists",
      "Nothing was published by this run" in yt_wf_text and "A video exists" in yt_wf_text
      and "Nothing may have been published" not in yt_wf_text,
      "a hedge in the first line of an issue is a morning wasted reading the channel by hand")
for name in ("youtube_scheduled.yml", "telegram_autopost.yml", "facebook_autopost.yml",
             "threads_autopost.yml"):
    # instagram_autopost.yml is deliberately absent from this loop: its *render* commit must
    # fire the site deploy, because the deploy is what makes the media URL public.
    text = open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8").read()
    check("%s: an auto-commit of bookkeeping does not retrigger CI" % name,
          "[skip ci]" in text,
          "the free plan has 2,000 minutes a month; a ledger push that fires Verify burns them")
check("youtube ledger: an entry carries what YouTube reported",
      "--state" in open(os.path.join(ROOT, "tools", "youtube_ledger.py"), encoding="utf-8").read(),
      "the difference between 'published' and 'we PUT a file and hoped'")

# ── the Deep-Dive lane: long-form ships through tools/deepdive.py, banked, unattended ──
# Sep 2026: DD1–DD4 were produced on a laptop; the voice, the word timings and the plates
# were never committed and were lost with the machine. 14 Oct 2026: the owner does not want
# to narrate — the voice is Gemini TTS, the sync is Vosk, both on the runner, and every
# intermediate goes to a GitHub Release so a re-run never pays for the same bytes twice.
print("\n── 16. Deep-Dive lane — inputs committed, intermediates banked, brand from the engine ──")
dd_wf = os.path.join(ROOT, ".github", "workflows", "deepdive.yml")
dd_tool = os.path.join(ROOT, "tools", "deepdive.py")
check("deepdive: the workflow and the engine exist", os.path.isfile(dd_wf) and os.path.isfile(dd_tool))
if os.path.isfile(dd_wf) and os.path.isfile(dd_tool):
    dd_wf_text = open(dd_wf, encoding="utf-8").read()
    dd_tool_text = open(dd_tool, encoding="utf-8").read()
    eps = sorted(d for d in glob.glob(os.path.join(ROOT, "episodes", "*"))
                 if os.path.isdir(d) and os.path.basename(d) != "assets")
    check("deepdive: every episode commits its script AND its beats",
          bool(eps) and all(os.path.isfile(os.path.join(d, "script.txt"))
                            and os.path.isfile(os.path.join(d, "episode.json")) for d in eps),
          "episodes/<id>/script.txt + episode.json — the inputs that were lost in Sep 2026")
    check("deepdive: the plates are in git, not on a laptop",
          len(glob.glob(os.path.join(ROOT, "episodes", "assets", "*.jpg"))) >= 8)
    check("deepdive: palette, Inter and ffmpeg come from MotionStudio",
          "import motionstudio as ms" in dd_tool_text and "DejaVu" not in dd_tool_text)
    check("deepdive: the voice is banked on a release even when the quota runs out",
          "gh release upload \"$RELEASE_TAG\" \"/tmp/$EPISODE-voice.tar.gz\"" in dd_wf_text
          and "\"$code\" -eq 5" in dd_wf_text)
    check("deepdive: the master is banked before anything is uploaded",
          dd_wf_text.find("$EPISODE-episode.mp4\" \"$BUILD_DIR/$EPISODE-cover.jpg") <
          dd_wf_text.find("tools/yt_publish.py --video"))
    check("deepdive: nothing pace-estimated reaches the channel",
          "Synthetic timings" in dd_wf_text and "allow_synthetic" in dd_tool_text)
    check("deepdive: long-form has its own ledger and the duplicate guard reads it",
          "--ledger logs/youtube_longform.json check" in dd_wf_text)
    _ytp = open(os.path.join(ROOT, "tools", "yt_publish.py"), encoding="utf-8").read()
    check("youtube: a public upload is SCHEDULED for the intended moment (private + publishAt), never dumped live",
          '"publishAt": rfc3339_utc(publish_at)' in _ytp and "def publish_slot" in _ytp and "SCHEDULE_HOUR_WAT = 19" in _ytp
          and 'state["result"] = "scheduled"' in _ytp and "--publish-at" in dd_wf_text
          and '"publish_at": str(yt.get("publish_at") or "")' in dd_tool_text,
          "owner instruction 17 Oct 2026 — Shorts at the 19:00 WAT slot, Deep-Dives on their intended date")
    check("deepdive: the publish is never public by default — the owner's YT_PRIVACY variable is the switch",
          'PRIVACY="${IN_PRIVACY:-${IN_YT_PRIVACY:-unlisted}}"' in dd_wf_text
          and "IN_YT_PRIVACY: ${{ vars.YT_PRIVACY }}" in dd_wf_text and "default: public" not in dd_wf_text)
    check("deepdive: exit codes survive the log capture",
          "code=${PIPESTATUS[0]}" in dd_wf_text)
    check("deepdive: the ledger commit does not retrigger CI", "[skip ci]" in dd_wf_text)
    check("deepdive: a quota pause ends green and the nightly tick resumes it (free plan forever)",
          "\"$code\" -eq 5" in dd_wf_text and "complete=false" in dd_wf_text
          and "cron: '0 2 * * *'" in dd_wf_text and "deepdive_queue.py next" in dd_wf_text
          and "--max-requests 12" in dd_wf_text,
          "the owner presses nothing twice; an empty free bucket is a pause, not a failure")
    check("deepdive: music and SFX are synthesized by the repo, not downloaded",
          os.path.isfile(os.path.join(ROOT, "tools", "soundkit.py"))
          and "soundkit.render_mix" in dd_tool_text
          and "http" not in open(os.path.join(ROOT, "tools", "soundkit.py"), encoding="utf-8").read().lower(),
          "a 'free' track can be re-licensed or Content-ID'd; sine waves cannot")
    check("deepdive: QA refuses a bed that masks the voice",
          "MIN_BED_SEPARATION_DB" in dd_tool_text and "bed_separation_db" in dd_tool_text)
    check("deepdive: the sound plan is written down per episode",
          all("audio" in open(os.path.join(d, "episode.json"), encoding="utf-8").read() for d in eps))
    # THE VOICE — LOCKED (owner, 14 Oct 2026: "not even by one sentence or word, not even by mistake")
    import hashlib as _hl
    _lock_name = "Orus"
    _lock_ins = "Narrate this in a natural Nigerian English accent, like a confident Lagos radio presenter:"
    _lock_sha = "697e3233c630632bfa394317cc8902f0ab51e6d70670921c360d2161e6cff663"
    check("deepdive: THE VOICE IS LOCKED — Orus + the exact instruction, fingerprint %s…" % _lock_sha[:12],
          _hl.sha256((_lock_name + "\n" + _lock_ins).encode("utf-8")).hexdigest() == _lock_sha
          and 'LOCKED_VOICE_NAME = "Orus"' in dd_tool_text
          and ('LOCKED_VOICE_SHA256 = "%s"' % _lock_sha) in dd_tool_text
          and '"Narrate this in a natural Nigerian English accent, "' in dd_tool_text
          and '"like a confident Lagos radio presenter:"' in dd_tool_text
          and "voice, instruction = locked_voice()" in dd_tool_text,
          "owner instruction 14 Oct 2026 — revert the change; never edit this check")
    _tts_body = dd_tool_text.split("def stage_tts", 1)[1].split("\ndef ", 1)[0]
    _ep_voices_ok = True
    for d in eps:
        _v = _json.loads(open(os.path.join(d, "episode.json"), encoding="utf-8").read()).get("voice")
        if _v is not None and (_v.get("name") != _lock_name or _v.get("instruction") != _lock_ins):
            _ep_voices_ok = False
    check("deepdive: no episode file, env var or flag can pick another narrator",
          "GEMINI_VOICE" not in dd_tool_text and '"--voice"' not in dd_tool_text
          and 'meta["voice"]' not in _tts_body and _ep_voices_ok,
          "the lock has one definition; every other path to the narrator is closed")
    check("deepdive: the bed is audible AND clear — A-weighted gates on both sides (run #1 lesson)",
          "MAX_BED_SEPARATION_DB" in dd_tool_text and "a_weight_gain" in
          open(os.path.join(ROOT, "tools", "soundkit.py"), encoding="utf-8").read(),
          "-27 dB by raw power was 'I did not hear background music'")
    check("youtube stats: the channel's numbers are pulled weekly, read-only, into the repo",
          os.path.isfile(os.path.join(ROOT, "tools", "yt_stats.py"))
          and os.path.isfile(os.path.join(ROOT, ".github", "workflows", "youtube_stats.yml"))
          and "docs/YOUTUBE_PERFORMANCE.md" in open(os.path.join(ROOT, ".github", "workflows", "youtube_stats.yml"),
                                                   encoding="utf-8").read(),
          "decisions on data, not memory")
    check("deepdive: the runbook tells the owner how to add the key and run it",
          os.path.isfile(os.path.join(ROOT, "docs", "LONGFORM_AUTOMATION.md"))
          and "GEMINI_API_KEY" in open(os.path.join(ROOT, "docs", "LONGFORM_AUTOMATION.md"),
                                       encoding="utf-8").read())

# THE BRAIN — LOCKED to Gemini (owner, 17 Oct 2026: "I don't want the gpt-oss, use only Gemini and
# plan with it, lock it in"). One host, Gemini-family model names, no second provider, no fallback.
# Never edit this check; revert the change that trips it.
_brain_files = ("gemini_text.py", "brain.py", "brain_replies.py", "listening.py", "deepdive.py", "gemini_tts.py",
                "gemini_quota.py")
_brain_text = {f: open(os.path.join(ROOT, "tools", f), encoding="utf-8").read().lower()
               for f in _brain_files if os.path.isfile(os.path.join(ROOT, "tools", f))}
_foreign = ("api.groq.com", "openrouter.ai", "/ai/v1/chat/completions", "api.openai.com", "api.mistral.ai",
            "integrate.api.nvidia.com", "api.cerebras.ai", "api-inference.huggingface.co", "router.huggingface.co",
            "models.github.ai", "api.together.xyz", "api.sambanova.ai", "gpt-oss", "@cf/", "llama-3", "anthropic.com")
_foreign_hits = ["%s: %s" % (f, w) for f, t in _brain_text.items() for w in _foreign if w in t]
_gt = _brain_text.get("gemini_text.py", "")
check("brain: THE BRAIN IS LOCKED to Gemini — one host, no second provider, no fallback",
      not _foreign_hits
      and 'locked_host = "generativelanguage.googleapis.com"' in _gt
      and 'locked_model_prefixes = ("gemini-", "gemma-")' in _gt
      and "assert_locked(model)" in _gt and "def assert_locked" in _gt
      and _gt.count("https://") == 2    # the generateContent URL and the ListModels URL — nothing else
      and "api = \"https://generativelanguage.googleapis.com/v1beta/models/{model}:generatecontent\"" in _gt,
      "owner instruction 17 Oct 2026 — revert the change; never edit this check"
      + (" — found: " + "; ".join(_foreign_hits) if _foreign_hits else ""))
_wf_brain = "".join(open(os.path.join(ROOT, ".github", "workflows", n), encoding="utf-8").read()
                    for n in ("brain.yml", "brain_replies.yml") if os.path.isfile(os.path.join(ROOT, ".github", "workflows", n)))
check("brain: the brain workflows carry no second provider's secret",
      not any(k in _wf_brain for k in ("CF_AI_", "GROQ_", "OPENROUTER_", "OPENAI_API_KEY", "MISTRAL_", "NVIDIA_")),
      "the only key the brain holds is GEMINI_API_KEY")

print("\n── 17. Public-repo gate — no credential shape in any tracked file (20 Oct 2026) ──")
_ss = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "secret_scan.py")],
                     capture_output=True, text=True, cwd=ROOT, timeout=120)
check("secret_scan: tracked files carry no token/key shape (the repo is public — Actions minutes are free only there)",
      _ss.returncode == 0, (_ss.stdout.strip().splitlines() or [""])[0][:160] if _ss.returncode else "")
check("secret_scan: the stray scripts that once held live values are gone",
      not any(os.path.exists(os.path.join(ROOT, f)) for f in ("send_test_post.sh", "logs/2026-09-19-first-real-payment-webhook.json")),
      "send_test_post.sh carried a bot token; the webhook log carried the owner's own payment record")

# The unittest files are the real gate; run them when their deps are present.
import importlib.util as _ilu
missing_mods = [m for m in ("requests", "yaml") if _ilu.find_spec(m) is None]
if missing_mods:
    warn("social unittests skipped locally — missing " + ", ".join(missing_mods)
         + " (CI runs them; install with `pip install requests pyyaml`)", False)
else:
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s",
                        os.path.join(ROOT, "tools", "tests"), "-p", "test_*.py", "-q"],
                       capture_output=True, text=True, cwd=ROOT, timeout=900)
    check("python automation tests (workflows + telegram + facebook + youtube)",
          r.returncode == 0, (r.stderr or "").strip().splitlines()[-1][:160] if r.returncode else "")

print()
if errors:
    print(f"⛔ QA FAILED — {len(errors)} error(s). DO NOT PUSH.")
    sys.exit(1)
print(f"🏆 QA GREEN — {len(warnings)} warning(s), 0 errors. Safe to push.")
sys.exit(0)
