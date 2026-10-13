"""Provider-free regressions for the read-only deployment authentication gate."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('cfcheck', Path(__file__).resolve().parents[1] / 'verify_cloudflare_token.py')
cfcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfcheck)
ACCOUNT = 'a' * 32
ACTIVE = (200, {'success': True, 'result': {'status': 'active', 'id': 'private-id'}})
REJECT = (403, {'success': False, 'errors': [{'code': 1000, 'message': 'private-value'}]})
READ = (200, {'success': True, 'result': [{'id': 'private-id'}]})


class TokenCheckTests(unittest.TestCase):
    def run_check(self, replies, success, expected_calls, token='private-token', account=ACCOUNT):
        calls = []
        def fetch(path, supplied):
            calls.append(path)
            reply = replies[len(calls)-1]
            if isinstance(reply, Exception):
                raise reply
            code, body = reply
            return code, json.dumps(body) if not isinstance(body, bytes) else body
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            if success:
                cfcheck.verify(token, account, fetch)
            else:
                with self.assertRaises(cfcheck.CheckFailed):
                    cfcheck.verify(token, account, fetch)
        self.assertEqual(calls, expected_calls)
        for private in ('private-token', 'private-value', 'private-id', ACCOUNT):
            self.assertNotIn(private, out.getvalue())
        return out.getvalue()

    def test_active_user_requires_account_read(self):
        out = self.run_check([ACTIVE, READ], True, ['/user/tokens/verify', f'/accounts/{ACCOUNT}/workers/scripts'])
        self.assertIn('verification path=user', out)

    def test_account_token_fallback_requires_affirmative_active_and_account_read(self):
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                out = self.run_check([(status, REJECT[1]), ACTIVE, READ], True,
                    ['/user/tokens/verify', f'/accounts/{ACCOUNT}/tokens/verify', f'/accounts/{ACCOUNT}/workers/scripts'])
                self.assertIn('verification path=account', out)
                self.assertIn('API error codes 1000', out)

    def test_no_fallback_for_inactive_malformed_server_or_transport(self):
        for reply in ((200, {'success': True, 'result': {'status': 'expired'}}),
                      (200, {'success': False}), (403, b'not-json'), (403, []),
                      (403, {'success': False, 'errors': []}),
                      (429, REJECT[1]), (500, REJECT[1]), cfcheck.CheckFailed('network')):
            with self.subTest(reply=reply):
                self.run_check([reply], False, ['/user/tokens/verify'])

    def test_invalid_account_token_and_account_access_fail_closed(self):
        self.run_check([REJECT, REJECT], False, ['/user/tokens/verify', f'/accounts/{ACCOUNT}/tokens/verify'])
        self.run_check([ACTIVE, REJECT], False, ['/user/tokens/verify', f'/accounts/{ACCOUNT}/workers/scripts'])
        self.run_check([ACTIVE, (200, {'success': True, 'result': {}})], False,
                       ['/user/tokens/verify', f'/accounts/{ACCOUNT}/workers/scripts'])

    def test_missing_or_malformed_configuration_never_requests(self):
        for token, account in (('', ACCOUNT), ('private-token\n', ACCOUNT), ('private-token', 'bad')):
            self.run_check([], False, [], token, account)
