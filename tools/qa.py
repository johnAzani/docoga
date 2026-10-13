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
  9. Dependency-light test suites: worker unit suite + full-app jsdom suite
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
import gzip as _gzip
_idx_gz = len(_gzip.compress(idx.encode(), 9))
check("index.html gzipped payload under 48 KB (real page weight)",
      _idx_gz <= 48 * 1024, f"{_idx_gz} bytes gzipped")
check("index.html raw size sane (corruption tripwire, 40–200 KB)",
      40000 <= len(idx.encode()) <= 200000, f"{len(idx.encode())} bytes raw")

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
# 9b. full-app DOM suite — executes the real index.html in jsdom.
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
    check("Telegram's white-on-transparent hero is not offered to Facebook",
          "official-logo-white" not in gen.split("FB_PHOTO_IMAGES")[1].split("]")[0])
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
          and daily.index("import generate_short_video as shorts") > daily.index("def reel_topic"),
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
    growth_hb = open(os.path.join(ROOT, "docs", "GROWTH_ENGINE.md"), encoding="utf-8").read()
    check("the heartbeat is written down where the owner looks",
          "automation-heartbeat" in readme_hb and "automation-heartbeat" in growth_hb,
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
for name in ("youtube_scheduled.yml", "telegram_autopost.yml", "facebook_autopost.yml"):
    text = open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8").read()
    check("%s: an auto-commit of bookkeeping does not retrigger CI" % name,
          "[skip ci]" in text,
          "the free plan has 2,000 minutes a month; a ledger push that fires Verify burns them")
check("youtube ledger: an entry carries what YouTube reported",
      "--state" in open(os.path.join(ROOT, "tools", "youtube_ledger.py"), encoding="utf-8").read(),
      "the difference between 'published' and 'we PUT a file and hoped'")

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
