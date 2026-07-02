import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

import llm

OK_BODY = json.dumps({"choices": [{"message": {"content": "hello"}}]}).encode()


class FakeResp:
    def __init__(self, payload=OK_BODY):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(code):
    return urllib.error.HTTPError("http://x/chat/completions", code, "boom", None, None)


class TestChatRetry(unittest.TestCase):
    def _chat(self, urlopen):
        with mock.patch("urllib.request.urlopen", side_effect=urlopen) as m, \
             mock.patch("time.sleep") as sleep, \
             redirect_stdout(io.StringIO()):
            result = llm.chat("http://x", "k", "m", [], temperature=0.2)
        return result, m, sleep

    def test_success_first_try(self):
        result, m, sleep = self._chat([FakeResp()])
        self.assertEqual(result, "hello")
        self.assertEqual(m.call_count, 1)
        sleep.assert_not_called()

    def test_retries_on_5xx_then_succeeds(self):
        result, m, sleep = self._chat([http_error(500), http_error(503), FakeResp()])
        self.assertEqual(result, "hello")
        self.assertEqual(m.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        # backoff doubles: 5s then 10s
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5, 10])

    def test_retries_on_connection_error(self):
        result, m, _ = self._chat([ConnectionResetError("reset"), FakeResp()])
        self.assertEqual(result, "hello")
        self.assertEqual(m.call_count, 2)

    def test_no_retry_on_4xx(self):
        with mock.patch("urllib.request.urlopen", side_effect=[http_error(400)]) as m:
            with self.assertRaises(urllib.error.HTTPError):
                llm.chat("http://x", "k", "m", [], temperature=0.2)
        self.assertEqual(m.call_count, 1)

    def test_raises_after_final_failure(self):
        errs = [urllib.error.URLError("down")] * (llm.RETRIES + 1)
        with mock.patch("urllib.request.urlopen", side_effect=errs) as m, \
             mock.patch("time.sleep"), redirect_stdout(io.StringIO()):
            with self.assertRaises(urllib.error.URLError):
                llm.chat("http://x", "k", "m", [], temperature=0.2)
        self.assertEqual(m.call_count, llm.RETRIES + 1)


if __name__ == "__main__":
    unittest.main()
