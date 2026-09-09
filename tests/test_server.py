import json
import threading
import unittest
from urllib import error, request

from flip7.server import HeliosHandler, set_match
from flip7.live import LiveMatch
from http.server import ThreadingHTTPServer
import random


class TestServerSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_match(LiveMatch(["Pilot", "Engineer"], rng=random.Random(99)))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), HeliosHandler)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _get(self, path):
        with request.urlopen(self.base + path, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _post(self, path, body=None):
        data = json.dumps(body or {}).encode()
        req = request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode())
        except error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_health_and_state(self):
        code, health = self._get("/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(health.get("ok"))
        code, state = self._get("/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(state.get("title"), "Reactor Overload")
        self.assertIn("players", state)

    def test_static_index(self):
        with request.urlopen(self.base + "/", timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode()
            self.assertIn("Helios", body)
            self.assertIn("REACTOR", body)

    def test_new_match_post(self):
        code, state = self._post("/api/new", {"players": ["A", "B"], "seed": 1})
        self.assertEqual(code, 200)
        self.assertEqual(len(state["players"]), 2)
        self.assertEqual(state["players"][0]["name"], "A")


if __name__ == "__main__":
    unittest.main()
