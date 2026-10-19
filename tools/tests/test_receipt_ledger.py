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


if __name__ == "__main__":
    unittest.main()
