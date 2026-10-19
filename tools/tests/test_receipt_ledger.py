"""Receipt ledger (19 Oct 2026) — the contract between the site, the worker and the deploy.

The worker's own behaviour is tested in workers/ledger/test.mjs (node --test, run by `npm test`).
These checks hold the seams: what the site sends, that the ledger shares the payment worker's KV
namespace only under its own prefix, and that the deploy path mirrors the clock's.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = (ROOT / "site/index.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers/ledger/index.js").read_text(encoding="utf-8")
PASS_TOML = (ROOT / "worker/wrangler.toml").read_text(encoding="utf-8")
LEDGER_TOML = (ROOT / "workers/ledger/wrangler.toml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy-ledger.yml").read_text(encoding="utf-8")
ADMIN = (ROOT / "site/admin.html").read_text(encoding="utf-8")


class SiteSendsOnlyTheIndexFields(unittest.TestCase):
    def test_the_register_body_carries_no_name_address_or_phone(self):
        m = re.search(r"LEDGER_URL\+'/api/register'[\s\S]*?body:JSON\.stringify\(\{([^}]*)\}\)", SITE)
        self.assertIsNotNone(m, "registerReceipt must post a literal object so this test can read its keys")
        keys = [k.strip().split(":")[0] for k in m.group(1).split(",")]
        self.assertEqual(sorted(keys), ["amount", "date", "fp", "from", "kind", "state", "to"])
        for forbidden in ("r_from", "r_issuer", "r_prop", "r_phone"):
            self.assertNotIn(forbidden, m.group(1))

    def test_the_code_is_opt_out_and_the_state_select_exists(self):
        self.assertIn('id="r_verify" checked', SITE)
        self.assertIn('id="r_state"', SITE)
        self.assertIn("never names, addresses or phones", SITE)

    def test_printing_never_waits_longer_than_the_bound(self):
        self.assertIn("setTimeout(()=>ctl.abort(),3500)", SITE)
        self.assertIn("if(!receiptWantsCode()) return;", SITE)

    def test_the_fingerprint_is_computed_client_side_with_webcrypto(self):
        self.assertIn("crypto.subtle.digest('SHA-256'", SITE)
        self.assertIn("function receiptCanonical(f){", SITE)
        self.assertIn("function receiptCanonical(f){", WORKER)


class LedgerSharesTheNamespaceSafely(unittest.TestCase):
    def test_same_kv_namespace_id_as_the_payment_worker(self):
        pass_id = re.search(r'id = "([0-9a-f]{32})"', PASS_TOML).group(1)
        self.assertIn('id = "%s"' % pass_id, LEDGER_TOML)

    def test_every_ledger_key_and_list_is_prefixed(self):
        for call in re.findall(r"env\.KV\.(?:get|put)\(([^,\)]+)", WORKER):
            self.assertTrue(call.strip().startswith('"ledger:'), call)
        for call in re.findall(r"env\.KV\.list\(\{([^}]*)\}", WORKER):
            self.assertIn('prefix: "ledger:', call)

    def test_the_payment_worker_never_lists_without_a_prefix(self):
        pw = (ROOT / "worker/index.js").read_text(encoding="utf-8")
        for call in re.findall(r"env\.KV\.list\(\{([^}]*)\}", pw):
            self.assertIn("prefix:", call)

    def test_the_record_shape_has_no_personal_field(self):
        m = re.search(r"record: \{ v: 1, ([^}]*)\}", WORKER)
        self.assertIsNotNone(m)
        self.assertEqual(sorted(k.split(":")[0].strip() for k in m.group(1).split(",")), ["amt", "d", "fp", "from", "kind", "st", "to"])


class DeployMirrorsTheClock(unittest.TestCase):
    def test_tests_run_before_deploy_and_only_ledger_paths_trigger(self):
        self.assertIn("node --test test.mjs", DEPLOY)
        self.assertIn('- "workers/ledger/**"', DEPLOY)
        self.assertNotIn("worker/index.js", DEPLOY)
        self.assertIn("--keep-vars", DEPLOY)
        self.assertIn("redact_deploy_log.py", DEPLOY)
        self.assertIn("LEDGER_DEPLOY=", DEPLOY)

    def test_the_package_test_runs_the_ledger_suite(self):
        pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("node --test workers/ledger/test.mjs", pkg["scripts"]["test"])


class DashboardReadsTheLedger(unittest.TestCase):
    """The owner sees registrations on his dashboard without the payments worker learning anything."""

    def test_admin_reads_the_same_ledger_url_the_receipts_write_to(self):
        a = re.search(r'const LEDGER_URL\s*=\s*"([^"]+)"', ADMIN)
        b = re.search(r'const LEDGER_URL\s*=\s*"([^"]+)"', SITE)
        self.assertTrue(a and b and a.group(1) == b.group(1), (a and a.group(1), b and b.group(1)))
        self.assertIn("LEDGER_URL+'/api/stats'", ADMIN)

    def test_the_payment_worker_is_not_involved(self):
        pass_worker = (ROOT / "worker/index.js").read_text(encoding="utf-8")
        for needle in ("docoga-ledger", "ledger:r:", "ledger:fp:", "/api/stats"):
            self.assertNotIn(needle, pass_worker, "the dashboard must read docoga-ledger directly; worker/index.js stays out of it")

    def test_stats_expose_index_cells_and_the_publication_threshold(self):
        self.assertIn('cells[cell] = (cells[cell] || 0) + 1', WORKER)
        self.assertIn("publish_at: 30", WORKER)
        for el in ("ledger-kpis", "ledger-cells", "ledger-states", "ledger-note"):
            self.assertIn('id="%s"' % el, ADMIN)


class QrOnThePaper(unittest.TestCase):
    """Step 2: the QR is drawn by the worker (no page weight) and allow-listed by the page before it is inlined."""

    def test_the_encoder_is_ours_and_pinned_to_the_python_reference(self):
        qr = (ROOT / "workers/ledger/qr.js").read_text(encoding="utf-8")
        self.assertIn("export function svg(", qr)
        self.assertIn("0x11D", qr, "GF(256) with the QR polynomial")
        fixtures = json.loads((ROOT / "workers/ledger/qr_fixtures.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(fixtures), 50)
        self.assertEqual(sorted({f["version"] for f in fixtures}), [1, 2, 3, 4, 5, 6])
        self.assertEqual(sorted({f["mask"] for f in fixtures}), list(range(8)))
        self.assertIn('import { svg as qrSvg } from "./qr.js"', WORKER)
        self.assertIn('qr: qrSvg(verifyUrl(env, code), QR_PX)', WORKER)

    def test_the_page_allow_lists_the_svg_and_never_trusts_the_network(self):
        self.assertIn("const QR_SAFE=/^<svg xmlns=", SITE)
        self.assertIn("QR_SAFE.test(j.qr||'')?j.qr:''", SITE)
        self.assertNotIn("innerHTML=j.qr", SITE)
        # nothing in the QR strip is user text; the only dynamic parts are the code and the SVG
        self.assertIn("receiptVerify.qr?'<span style=\"flex:0 0 auto;line-height:0\">'+receiptVerify.qr+'</span>'", SITE)


class TheShortAddress(unittest.TestCase):
    """Step 3 (owner's tap, 19 Oct 2026 2:50pm): docoga.com.ng/v/* → docoga-ledger. Paper, QR and worker agree."""

    def test_public_url_is_the_site_and_the_paper_prints_the_same_path(self):
        m = re.search(r'PUBLIC_URL = "([^"]+)"', LEDGER_TOML)
        self.assertEqual(m.group(1), "https://docoga.com.ng")
        c = re.search(r'const LEDGER_CHECK="([^"]+)"', SITE)
        self.assertEqual("https://" + c.group(1), m.group(1) + "/v/")
        self.assertIn("esc(LEDGER_CHECK)+esc(receiptVerify.code)", SITE)
        self.assertNotIn("LEDGER_URL.replace('https://','')", SITE, "the workers.dev address must no longer be printed")

    def test_the_deploy_probes_the_route_from_outside(self):
        self.assertIn("https://docoga.com.ng/v/DR-0000-0000", DEPLOY)
        self.assertIn("LEDGER_ROUTE=", DEPLOY)


if __name__ == "__main__":
    unittest.main()
