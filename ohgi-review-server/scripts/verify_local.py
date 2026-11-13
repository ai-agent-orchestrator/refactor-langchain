"""Run a short localhost-only fake-mode check, then stop our own server."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "FAKE_LLM": "true", "FAKE_LLM_DELAY_SECONDS": "0.01",
           "PYTHONIOENCODING": "utf-8"}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    base = f"http://127.0.0.1:{port}"

    def request(path, method="GET", body=None):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(base + path, data=payload, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, response.read()
        except HTTPError as exc:
            return exc.code, exc.read()

    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                assert request("/docs")[0] == 200
                break
            except (URLError, TimeoutError):
                if server.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Local server failed to start")
                time.sleep(0.05)
        body = {"customerName": "Practice guest", "rating": 5, "content": "Kind service"}
        status, raw = request("/api/reviews", "POST", body)
        assert status == 201
        review_id = json.loads(raw)["reviewId"]
        assert request(f"/api/reviews/{review_id}")[0] == 200
        status, raw = request(f"/api/reviews/{review_id}/reply", "POST")
        assert status == 200 and json.loads(raw)["model"] == "fake-llm"
        assert request("/api/reviews", "POST", {**body, "rating": 6})[0] == 422
        assert request("/api/reviews/999")[0] == 404
        req = Request(base + f"/api/reviews/{review_id}/reply/stream", data=b"", method="POST")
        token_times = []
        events = []
        with urlopen(req, timeout=8) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if line.startswith("event: "):
                    event = line[7:]
                    events.append(event)
                    if event == "token":
                        token_times.append(time.monotonic())
        assert events[-1] == "done" and len(token_times) > 5, events
        assert token_times[-1] - token_times[0] > 0.05, "Tokens arrived as one buffered block"
    finally:
        server.terminate()
        try:
            logs, _ = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            logs, _ = server.communicate()
    assert "[reply] thread=MainThread" in logs, logs
    assert "[register] thread=AnyIO worker thread" in logs, logs
    assert "[find] thread=AnyIO worker thread" in logs, logs
    assert "[draft] attempts=0 thread=MainThread" in logs, logs
    assert "[review] passed=True attempts=0 thread=MainThread" in logs, logs
    assert logs.count("[model:create]") == 1, logs
    print("PASS: live localhost /docs 200; create 201; get/reply 200; rating 6 -> 422; missing -> 404")
    print("PASS: sync handlers -> AnyIO worker thread; async reply -> MainThread")
    print("PASS: model created once; draft/review on MainThread; incremental SSE tokens before done")
    print("Fake mode only. Server stopped. No real OpenAI calls or manual Postman checks.")


if __name__ == "__main__":
    main()
