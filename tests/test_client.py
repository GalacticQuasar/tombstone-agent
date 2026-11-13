import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from openai import OpenAI

from tombstone import client as client_mod
from tombstone.client import Backend, OpenAIChatClient, SlotThrottle
from tombstone.messages import Message

OK = {
    "id": "x",
    "object": "chat.completion",
    "created": 0,
    "model": "m",
    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "hi"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}


@pytest.fixture
def make_client(monkeypatch):
    """Real SDK against a local server that replays (status, JSON body) pairs."""
    servers = []

    def make(bodies):
        sleeps = []
        monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
        responses = iter(bodies)

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["content-length"]))
                status, body = next(responses)
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/v1"
        c = OpenAIChatClient(Backend("t", url, "m"))
        c._client = OpenAI(base_url=url, api_key="k", max_retries=0)
        return c, sleeps

    yield make
    for server in servers:
        server.shutdown()
        server.server_close()


USER = [Message(role="user", content="q")]


def test_null_body_is_retried_with_backoff(make_client):
    c, sleeps = make_client([(200, None), (200, None), (200, OK)])
    assert c.complete(USER, []).message.content == "hi"
    assert sleeps == list(client_mod.RETRY_DELAYS[:2])


def test_429_is_retried(make_client):
    c, sleeps = make_client([(429, {"error": "slow"}), (200, OK)])
    assert c.complete(USER, []).usage.prompt == 3
    assert sleeps == [client_mod.RETRY_DELAYS[0]]


def test_gives_up_after_all_retries(make_client):
    bodies = [(200, None)] * (len(client_mod.RETRY_DELAYS) + 1)
    c, _ = make_client(bodies)
    with pytest.raises(RuntimeError, match="rate-limiting"):
        c.complete(USER, [])


def test_empty_400_is_retried(make_client):
    c, sleeps = make_client([(400, None), (200, OK)])
    assert c.complete(USER, []).message.content == "hi"
    assert sleeps == [client_mod.RETRY_DELAYS[0]]


def test_other_errors_are_not_retried(make_client):
    c, sleeps = make_client([(400, {"error": "bad"})])
    with pytest.raises(Exception, match="400"):
        c.complete(USER, [])
    assert sleeps == []


def test_throttle_spaces_requests_across_instances(monkeypatch, tmp_path):
    sleeps = []
    monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
    monkeypatch.setattr(client_mod.time, "time", lambda: 1000.0)
    monkeypatch.setattr(client_mod.tempfile, "gettempdir", lambda: str(tmp_path))
    # Separate instances stand in for separate processes: only the file is shared.
    for _ in range(3):
        SlotThrottle("b", 20).wait()
    assert sleeps == pytest.approx([0.0, 3.0, 6.0])
