"""kv_backup (30 Oct 2026): the one copy of every pass and receipt. Offline — the Cloudflare
API is a fake, the vault key is a test key; nothing here touches the live namespace."""
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import kv_backup as kb  # noqa: E402

TEST_KEY = "11" * 32   # hex, 32 bytes


def fake_store():
    return {
        "code:ABCD1234": {"value": json.dumps({"code": "ABCD1234", "email": "x@y.z", "exp": 4102444800000}), "expiration": None},
        "code:EFGH5678": {"value": json.dumps({"code": "EFGH5678", "email": "a@b.c", "exp": 1}), "expiration": 4102444800},
        "ref:FLW-1": {"value": "ABCD1234", "expiration": None},
        "team:t1": {"value": json.dumps({"id": "t1"}), "expiration": None},
        "ledger:r:R1": {"value": json.dumps({"state": "Lagos", "kind": "rent", "amount": 500000}), "expiration": None},
        "ledger:fp:deadbeef": {"value": "R1", "expiration": None},
        "adm:snap": {"value": json.dumps({"total": 2}), "expiration": None},
        "adm:sess:abc": {"value": "session", "expiration": 1900000000},
        "media:clip1": {"value": json.dumps({"parts": 1}), "expiration": None},
        "media:clip1:0": {"value": "\x00\x01binary", "expiration": None},
        "asset:email-banner": {"value": "\xff\xd8", "expiration": None},
        "debug:last-webhook-ts": {"value": "1730000000000", "expiration": None},
    }


class FakeApi:
    def __init__(self, store, deny=False, page=5):
        self.store, self.deny, self.page = store, deny, page
        self.calls = []

    def __call__(self, method, path, token, body=None, params=None):
        self.calls.append((method, path.split("/")[-1] if "/bulk" not in path else "bulk/get", params, body))
        if self.deny:
            raise kb.ApiError(403, 10000, "Authentication error")
        if path.endswith("/keys"):
            names = sorted(self.store)
            start = int((params or {}).get("cursor") or 0)
            chunk = names[start:start + self.page]
            nxt = start + self.page
            info = {"count": len(chunk), "cursor": str(nxt) if nxt < len(names) else ""}
            return {"success": True, "result": [{"name": n, **({"expiration": self.store[n]["expiration"]} if self.store[n]["expiration"] else {})} for n in chunk],
                    "result_info": info}
        if path.endswith("/bulk/get"):
            keys = body["keys"]
            if any(k.startswith("media:") and k[-1].isdigit() or k.startswith("asset:") for k in keys):
                raise kb.ApiError(400, 10021, "binary values are not supported")
            return {"success": True, "result": {"values": {k: {"value": self.store[k]["value"], "metadata": None} for k in keys if k in self.store}}}
        if "/values/" in path:
            name = kb.urllib.parse.unquote(path.split("/values/")[1])
            return self.store[name]["value"]
        if path.endswith("/bulk") and method == "PUT":
            for item in body:
                self.store[item["key"]] = {"value": item["value"], "expiration": item.get("expiration")}
            return {"success": True}
        raise AssertionError("unexpected call %s %s" % (method, path))


class BackupTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["SOCIAL_TOKEN_KEY"] = TEST_KEY
        os.environ["CLOUDFLARE_ACCOUNT_ID"] = "acct"
        os.environ["CLOUDFLARE_API_TOKEN"] = "tok"
        self._call = kb._call

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        kb._call = self._call

    def test_snapshot_keeps_the_business_records_and_skips_binary_and_sessions(self):
        api = FakeApi(fake_store())
        doc, keys = kb.snapshot("acct", "tok", call=api)
        self.assertEqual(len(keys), 12, "every key is listed across pages")
        names = set(doc["records"])
        for must in ("code:ABCD1234", "code:EFGH5678", "ref:FLW-1", "team:t1", "ledger:r:R1", "ledger:fp:deadbeef", "adm:snap", "media:clip1"):
            self.assertIn(must, names)
        for never in ("media:clip1:0", "asset:email-banner", "adm:sess:abc"):
            self.assertNotIn(never, names)
        self.assertEqual(doc["records"]["code:EFGH5678"]["expiration"], 4102444800, "a TTL travels with the record")
        self.assertEqual(doc["skipped"], 3)
        list_calls = [c for c in api.calls if c[1] == "keys"]
        self.assertEqual(len(list_calls), 3, "1,000-per-page listing follows the cursor")

    def test_backup_writes_an_encrypted_gzip_box_that_verify_opens_and_the_log_has_no_email(self):
        api = FakeApi(fake_store())
        kb._call = api
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "kv-latest.box"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = kb.main(["backup", "--out", str(out)])
            log = buf.getvalue()
            self.assertEqual(rc, 0, log)
            self.assertIn("KV_BACKUP=ok", log)
            self.assertNotIn("x@y.z", log)
            self.assertNotIn("ABCD1234", log)
            self.assertIn("| code: | 2 |", log)
            raw = out.read_text()
            self.assertNotIn("x@y.z", raw, "the box is ciphertext")
            self.assertNotIn("ABCD1234", raw)
            payload = json.loads(raw)
            self.assertEqual(payload["name"], "KV_BACKUP")
            self.assertEqual(payload["keys"], 9)
            doc, _ = kb.open_bytes(out)
            self.assertEqual(json.loads(doc["records"]["code:ABCD1234"]["value"])["email"], "x@y.z")
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(kb.main(["verify", "--file", str(out)]), 0)
            self.assertIn("KV_BACKUP_VERIFY=ok", buf.getvalue())
            # the wrong key cannot open it
            os.environ["SOCIAL_TOKEN_KEY"] = "22" * 32
            with self.assertRaises(Exception):
                kb.open_bytes(out)

    def test_a_token_without_kv_read_is_a_named_setup_problem_not_a_crash(self):
        kb._call = FakeApi(fake_store(), deny=True)
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = kb.main(["backup", "--out", str(Path(d) / "x.box")])
            self.assertEqual(rc, 3)
            self.assertIn("KV_BACKUP=missing-permission", buf.getvalue())
            self.assertIn("Workers KV Storage", buf.getvalue())
            self.assertFalse((Path(d) / "x.box").exists())

    def test_an_empty_namespace_never_overwrites_the_last_good_copy(self):
        kb._call = FakeApi({})
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "kv-latest.box"
            out.write_text("previous good copy")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = kb.main(["backup", "--out", str(out)])
            self.assertEqual(rc, 5)
            self.assertEqual(out.read_text(), "previous good copy")

    def test_no_vault_key_means_nothing_is_written(self):
        del os.environ["SOCIAL_TOKEN_KEY"]
        kb._call = FakeApi(fake_store())
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = kb.main(["backup", "--out", str(Path(d) / "x.box")])
            self.assertEqual(rc, 2)
            self.assertIn("KV_BACKUP=missing-key", buf.getvalue())
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_weekly_copies_are_kept_to_eight(self):
        kb._call = FakeApi(fake_store())
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            for i in range(10):
                (Path(d) / ("kv-weekly-2026-0%d-01.box" % (i % 9 + 1))).write_text("old") if i < 9 else None
            out = Path(d) / "kv-latest.box"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kb.main(["backup", "--out", str(out), "--weekly"]), 0)
            self.assertEqual(len(list(Path(d).glob("kv-weekly-*.box"))), kb.WEEKLY_KEEP)

    def test_restore_needs_the_word_and_round_trips_the_records(self):
        api = FakeApi(fake_store())
        kb._call = api
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "kv-latest.box"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kb.main(["backup", "--out", str(out)]), 0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(kb.main(["restore", "--file", str(out)]), 2)
            self.assertIn("--confirm RESTORE", buf.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kb.main(["restore", "--file", str(out), "--confirm", "RESTORE", "--dry-run"]), 0)
            self.assertFalse(any(c[0] == "PUT" for c in api.calls))
            # wipe the fake store and restore only the passes
            api.store.clear()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kb.main(["restore", "--file", str(out), "--confirm", "RESTORE", "--prefix", "code:"]), 0)
            self.assertEqual(sorted(api.store), ["code:ABCD1234", "code:EFGH5678"])
            self.assertEqual(api.store["code:EFGH5678"]["expiration"], 4102444800)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / ".github" / "workflows" / "kv_backup.yml"
        self.text = self.path.read_text(encoding="utf-8")
        self.doc = yaml.safe_load(self.text)

    def test_nightly_between_the_brain_and_the_deep_dive(self):
        on = self.doc.get("on") or self.doc.get(True)
        self.assertEqual([e["cron"] for e in on["schedule"]], ["45 1 * * *"])

    def test_it_reads_kv_with_the_deploy_token_and_seals_with_the_vault_key(self):
        self.assertIn("CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}", self.text)
        self.assertIn("SOCIAL_TOKEN_KEY: ${{ secrets.SOCIAL_TOKEN_KEY }}", self.text)
        self.assertIn("python3 tools/kv_backup.py backup", self.text)
        self.assertIn("python3 tools/kv_backup.py verify", self.text)
        runs = "\n".join(str(s.get("run") or "") for s in self.doc["jobs"]["backup"]["steps"])
        self.assertNotIn("kv_backup.py restore", runs, "restore is a human act, never scheduled")
        self.assertIn("git add -A logs/backup", self.text)
        self.assertEqual(self.doc["permissions"], {"contents": "write", "issues": "write"})

    def test_the_box_lives_outside_site_and_is_ignored_by_nothing(self):
        self.assertTrue(str(kb.OUT).startswith(str(ROOT / "logs")))
        self.assertNotIn("site", kb.OUT.parts)
        import subprocess
        rc = subprocess.run(["git", "check-ignore", "-q", "logs/backup/kv-latest.box"], cwd=ROOT).returncode
        self.assertEqual(rc, 1, "an ignored backup is a backup that never reaches main")

    def test_the_clock_knows_the_lane(self):
        sched = json.loads((ROOT / "workers" / "clock" / "schedule.json").read_text(encoding="utf-8"))
        self.assertIn("kv_backup.yml", [e["workflow"] for e in sched["entries"]])


if __name__ == "__main__":
    unittest.main()
