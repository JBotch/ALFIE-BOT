"""A stand-in for OpenAI's Chat Completions endpoint, for tests. Never the real API."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOpenAI:
    def __init__(self, reply=None):
        self.reply = reply or {"speech": "Volcanoes are mountains that let out hot melted rock!",
                               "expression": "excited", "action": None}
        self.statuses = []  # HTTP codes to send first (e.g. [500, 429]), then 200
        self.delay_s = 0.0
        self.refuse = False
        self.requests = []  # (headers, body)
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                fake.requests.append((dict(self.headers), body))
                if fake.delay_s:
                    time.sleep(fake.delay_s)
                if fake.statuses:
                    code = fake.statuses.pop(0)
                    self._send(code, {"error": {"message": f"fake error {code}"}})
                    return
                message = {"role": "assistant", "content": json.dumps(fake.reply)}
                if fake.refuse:
                    message = {"role": "assistant", "content": None, "refusal": "I can't help with that."}
                self._send(200, {"model": body.get("model"), "choices": [{"message": message}],
                                 "usage": {"prompt_tokens": 1000, "completion_tokens": 100}})

            def _send(self, code, data):
                out = json.dumps(data).encode()
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)
                except OSError:
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
