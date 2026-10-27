"""A stand-in Ollama server for tests: the same HTTP endpoints, canned answers."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self, models=("qwen3:0.6b",), reply=None):
        self.models = list(models)
        self.reply = reply or {"speech": "Beep boop! Hello there.", "expression": "happy", "action": None}
        self.mode = "ok"  # ok, text, broken, error, slow, no_think, think_tags
        self.slow_s = 3.0
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, data, code=200):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/version":
                    self._json({"version": "0.12.0-fake"})
                elif self.path == "/api/tags":
                    self._json({"models": [{"name": m, "size": 500_000_000} for m in fake.models]})
                elif self.path == "/api/ps":
                    self._json({"models": [{"name": m, "size": 900_000_000} for m in fake.models[:1]]})
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                fake.requests.append((self.path, body))
                if self.path == "/api/generate":
                    self._json({"done": True})
                    return
                if self.path != "/api/chat":
                    self._json({"error": "not found"}, 404)
                    return
                if body.get("model") not in fake.models:
                    self._json({"error": f"model '{body.get('model')}' not found"}, 404)
                    return
                if fake.mode == "no_think" and "think" in body:
                    self._json({"error": f"\"{body['model']}\" does not support thinking"}, 400)
                    return
                if fake.mode == "error":
                    self._json({"error": "out of memory"}, 500)
                    return
                content = {"text": "Hello! I am a robot.", "broken": '{"speech": "Hi", "expression":'}.get(
                    fake.mode, json.dumps(fake.reply))
                if fake.mode == "think_tags":
                    content = "<think>Let me think.</think>" + content
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for i in range(0, len(content), 8):
                    chunk = {"message": {"role": "assistant", "content": content[i:i + 8]}, "done": False}
                    try:
                        self.wfile.write((json.dumps(chunk) + "\n").encode())
                        self.wfile.flush()
                    except OSError:
                        return
                    if fake.mode == "slow":
                        time.sleep(fake.slow_s / max(1, len(content) / 8))
                done = {"message": {"role": "assistant", "content": ""}, "done": True,
                        "prompt_eval_count": 120, "eval_count": 24}
                self.wfile.write((json.dumps(done) + "\n").encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @property
    def chats(self):
        return [body for path, body in self.requests if path == "/api/chat"]
