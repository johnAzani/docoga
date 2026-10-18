"""tools/media_host.py — the Instagram Reels third door's hosting half (18 Oct 2026).

Hermetic: a fake `http` records every Cloudflare KV call and answers the worker's HEAD. The
properties pinned here are the ones that make the door safe and ₦0: chunking under KV's
25 MiB value ceiling, one TTL on every key, a 32-character unguessable name, a manifest the
worker can serve from, a HEAD poll that tolerates KV's propagation lag, and a delete that
removes the manifest before the bytes.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import media_host as mh  # noqa: E402

ENV = {"CLOUDFLARE_API_TOKEN": "cf-token-xyz", "CLOUDFLARE_ACCOUNT_ID": "acct123"}
NS = mh.namespace_id()


class FakeResp:
    def __init__(self, status, headers=None, body=b""):
        self.status, self.headers, self._body = status, headers or {}, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeHttp:
    """Records KV writes; answers HEAD on the worker from a script of statuses."""

    def __init__(self, head_statuses=(200,), size=None):
        self.calls = []
        self.store = {}
        self.heads = list(head_statuses)
        self.size = size

    def __call__(self, req):
        method, url = req.get_method(), req.full_url
        self.calls.append((method, url, dict(req.headers)))
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc == "api.cloudflare.com":
            key = urllib.parse.unquote(parsed.path.rsplit("/values/", 1)[1])
            if method == "PUT":
                self.store[key] = (req.data, urllib.parse.parse_qs(parsed.query))
                return FakeResp(200, body=b'{"success":true}')
            if method == "GET":
                if key not in self.store:
                    raise urllib.error.HTTPError(url, 404, "nf", {}, io.BytesIO(b'{"errors":[{"message":"key not found"}]}'))
                return FakeResp(200, body=self.store[key][0])
            if method == "DELETE":
                self.store.pop(key, None)
                return FakeResp(200, body=b'{"success":true}')
        if method == "HEAD":
            status = self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]
            if status != 200:
                raise urllib.error.HTTPError(url, status, "x", {}, io.BytesIO(b""))
            return FakeResp(200, {"Content-Length": str(self.size), "Content-Type": "video/mp4"})
        raise AssertionError("unexpected %s %s" % (method, url))



class MediaHost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "docoga_reel_20261019.mp4")
        self.body = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 300  # 76,824 bytes
        with open(self.video, "wb") as fh:
            fh.write(self.body)

    def test_put_chunks_under_the_kv_ceiling_with_one_ttl_and_a_manifest(self):
        fake = FakeHttp(size=len(self.body))
        with unittest.mock.patch.object(mh, "PART_BYTES", 30_000):
            r = mh.put(self.video, ttl_hours=48, verify_seconds=60, env=ENV, http=fake, sleeper=lambda s: None)
        self.assertEqual(r["parts"], 3)
        self.assertEqual(r["bytes"], len(self.body))
        self.assertTrue(r["live"])
        self.assertRegex(r["name"], r"^[A-Za-z0-9_-]{32}$")
        self.assertEqual(r["url"], "https://docoga-pass.johnazani.workers.dev/m/%s.mp4" % r["name"])
        parts = [fake.store["media:%s:%d" % (r["name"], i)][0] for i in range(3)]
        self.assertEqual(b"".join(parts), self.body, "the parts re-assemble to the file")
        self.assertTrue(all(len(p) <= 30_000 for p in parts))
        man = json.loads(fake.store["media:" + r["name"]][0])
        self.assertEqual(man["size"], len(self.body))
        self.assertEqual(man["parts"], 3)
        self.assertEqual(man["part_size"], 30_000)
        self.assertEqual(man["type"], "video/mp4")
        for key, (_, query) in fake.store.items():
            self.assertEqual(query.get("expiration_ttl"), [str(48 * 3600)], key)
        auth = {c[2].get("Authorization") for c in fake.calls if "api.cloudflare.com" in c[1]}
        self.assertEqual(auth, {"Bearer cf-token-xyz"})
        self.assertNotIn("cf-token-xyz", r["url"])
        puts = [c for c in fake.calls if c[0] == "PUT"]
        self.assertTrue(puts[-1][1].split("/values/")[1].startswith("media%3A" + r["name"]) and
                        "%3A" not in puts[-1][1].split("/values/")[1][len("media%3A" + r["name"]):],
                        "the manifest is written last, so a half-written Reel is never servable")

    def test_put_waits_through_kv_propagation_lag(self):
        fake = FakeHttp(head_statuses=(404, 404, 200), size=len(self.body))
        slept = []
        r = mh.put(self.video, verify_seconds=60, env=ENV, http=fake, sleeper=slept.append)
        self.assertTrue(r["live"])
        self.assertEqual(r["waited"], 10)
        self.assertEqual(slept, [5, 5])

    def test_put_reports_not_live_at_the_deadline_instead_of_hanging(self):
        fake = FakeHttp(head_statuses=(404,), size=len(self.body))
        r = mh.put(self.video, verify_seconds=15, env=ENV, http=fake, sleeper=lambda s: None)
        self.assertFalse(r["live"])
        self.assertEqual(r["status"], 404)

    def test_put_refuses_without_the_secrets_and_for_non_video_files(self):
        with self.assertRaises(mh.HostError) as cm:
            mh.put(self.video, env={}, http=FakeHttp())
        self.assertEqual(cm.exception.status, 2)
        text = os.path.join(self.tmp, "notes.txt")
        Path(text).write_text("hi")
        with self.assertRaises(mh.HostError) as cm:
            mh.put(text, env=ENV, http=FakeHttp())
        self.assertEqual(cm.exception.status, 5)
        fake_mp4 = os.path.join(self.tmp, "fake.mp4")
        Path(fake_mp4).write_bytes(b"not a video at all" * 10)
        with self.assertRaises(mh.HostError) as cm:
            mh.put(fake_mp4, env=ENV, http=FakeHttp())
        self.assertEqual(cm.exception.status, 5)

    def test_delete_removes_the_manifest_first_then_every_part(self):
        fake = FakeHttp(size=len(self.body))
        with unittest.mock.patch.object(mh, "PART_BYTES", 30_000):
            r = mh.put(self.video, verify_seconds=0, env=ENV, http=fake)
        before = len(fake.calls)
        n = mh.delete(r["name"], env=ENV, http=fake)
        self.assertEqual(n, 4)
        self.assertEqual(fake.store, {})
        deletes = [c[1] for c in fake.calls[before:] if c[0] == "DELETE"]
        self.assertTrue(deletes[0].endswith("media%3A" + r["name"]), deletes)

    def test_cli_prints_the_machine_lines_the_workflow_reads(self):
        fake = FakeHttp(size=len(self.body))
        out = io.StringIO()
        with unittest.mock.patch.dict(os.environ, ENV), \
                unittest.mock.patch.object(mh.urllib.request, "urlopen", lambda r, timeout=0: fake(r)), \
                unittest.mock.patch.object(mh.time, "sleep", lambda s: None), redirect_stdout(out):
            code = mh.main(["put", self.video, "--verify-seconds", "10"])
        text = out.getvalue()
        self.assertEqual(code, 0, text)
        for line in ("MEDIA_NAME=", "MEDIA_URL=https://docoga-pass.johnazani.workers.dev/m/",
                     "MEDIA_BYTES=%d" % len(self.body), "MEDIA_PARTS=1", "MEDIA_LIVE=yes"):
            self.assertIn(line, text)
        self.assertNotIn("cf-token-xyz", text)
        out = io.StringIO()
        with unittest.mock.patch.dict(os.environ, {}, clear=True), redirect_stdout(out):
            code = mh.main(["put", self.video])
        self.assertEqual(code, 2)
        self.assertIn("MEDIA_LIVE=no", out.getvalue())

    def test_the_worker_route_and_the_name_shape_agree_with_the_tool(self):
        """The worker's regex and the tool's names must match, or the URL 404s for ever."""
        src = (Path(__file__).resolve().parents[2] / "worker" / "index.js").read_text(encoding="utf-8")
        self.assertIn('/^\\/m\\/([A-Za-z0-9_-]{16,80})\\.(mp4|jpg|jpeg|png)$/', src)
        self.assertIn('"media:" + name', src)
        self.assertIn('"media:" + name + ":" + i', src)
        self.assertTrue(mh.NAME_RE.match(mh.new_name()))
        self.assertEqual(len(mh.new_name()), 32)



if __name__ == "__main__":
    unittest.main()
