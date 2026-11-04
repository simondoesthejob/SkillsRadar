"""A small local web app for labelling the gold set. Standard library only.

Run it with `python scripts/label_server.py`, then open http://127.0.0.1:8765. Labels are saved to
a file after every posting. It only listens on your own machine and refuses requests whose Host or
Origin is not itself, so a web page you happen to have open elsewhere cannot write labels.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from skillsradar.gold.review import review_posting, review_queue
from skillsradar.gold.split import split_of
from skillsradar.gold.store import STATUSES, LabelStore, read_jsonl
from skillsradar.skills.extractor import RulesExtractor
from skillsradar.skills.vocabulary import Vocabulary

STATIC = Path(__file__).with_name("static") / "labeller.html"
MAX_BODY = 100_000
MAX_NOTES = 2_000


class BadRequest(ValueError):
    pass


class LabelApp:
    """The app's logic, separate from HTTP so it can be tested directly."""

    def __init__(
        self,
        items: list[dict[str, Any]],
        store: LabelStore,
        vocab: Vocabulary,
        review_splits: tuple[str, ...] = ("dev",),
    ) -> None:
        self.items = items
        self.by_id = {i["id"]: i for i in items}
        self.ids = set(self.by_id)
        self.store = store
        self.vocab = vocab
        self.extractor = RulesExtractor(vocab)
        self.review_splits = review_splits

    def review(self, posting_id: str) -> dict[str, Any]:
        """The extractor's view of one labelled posting, unless it is in a split kept blind."""
        item = self.by_id.get(posting_id)
        if item is None:
            raise BadRequest("unknown posting id")
        label = self.store.all().get(posting_id)
        if not label or label.get("status") != "done":
            return {"available": False, "reason": "Label this posting first."}
        if split_of(posting_id) not in self.review_splits:
            return {
                "available": False,
                "reason": "Test-split posting: suggestions are hidden so the held-out score "
                "stays honest. Relabel it blind.",
            }
        result = review_posting(
            item, label["skills"], label.get("rejected", []), self.extractor, self.vocab
        )
        return {"available": True, **result}

    def queue(self) -> list[dict[str, Any]]:
        return review_queue(
            self.items, self.store.all(), self.extractor, self.vocab, self.review_splits
        )

    def state(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "labels": self.store.all(),
            "vocabulary": self.vocab.to_records(),
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        posting_id = payload.get("id")
        if posting_id not in self.ids:
            raise BadRequest("unknown posting id")
        skills = payload.get("skills", [])
        if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
            raise BadRequest("skills must be a list of strings")
        if len(skills) > 100:
            raise BadRequest("too many skills")
        status = payload.get("status", "done")
        if status not in STATUSES:
            raise BadRequest(f"status must be one of {STATUSES}")
        notes = str(payload.get("notes", ""))[:MAX_NOTES]

        def clean(key: str) -> list[str] | None:
            value = payload.get(key)
            if value is None:
                return None
            if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
                raise BadRequest(f"{key} must be a list of strings")
            return [self.vocab.canonical(s) or s for s in value[:100]]

        reviewed = payload.get("reviewed")
        if reviewed is not None and not isinstance(reviewed, bool):
            raise BadRequest("reviewed must be true or false")
        # Aliases become the canonical name; unknown skills are kept exactly as typed.
        canonical = [self.vocab.canonical(s) or s for s in skills]
        return self.store.upsert(
            posting_id,
            canonical,
            status,
            notes,
            rejected=clean("rejected"),
            review_added=clean("review_added"),
            reviewed=reviewed,
        )


def _make_handler(app: LabelApp, html: bytes, port: int) -> type[BaseHTTPRequestHandler]:
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # keep the terminal quiet
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            if self.headers.get("Host") not in allowed_hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or urlsplit(origin).netloc in allowed_hosts

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"error": "forbidden"})
            parts = urlsplit(self.path)
            path = parts.path
            if path == "/":
                return self._send(200, html, "text/html; charset=utf-8")
            if path == "/api/state":
                return self._json(200, app.state())
            if path == "/api/review":
                try:
                    posting_id = parse_qs(parts.query).get("id", [""])[0]
                    return self._json(200, app.review(posting_id))
                except BadRequest as exc:
                    return self._json(400, {"error": str(exc)})
            if path == "/api/review_queue":
                return self._json(200, app.queue())
            return self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"error": "forbidden"})
            if urlsplit(self.path).path != "/api/label":
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise BadRequest("bad body size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise BadRequest("expected an object")
                return self._json(200, app.save(payload))
            except (BadRequest, ValueError) as exc:
                return self._json(400, {"error": str(exc)})

    return Handler


def make_server(
    sample_path: Path,
    labels_path: Path,
    vocab: Vocabulary,
    port: int = 8765,
    review_splits: tuple[str, ...] = ("dev",),
) -> ThreadingHTTPServer:
    items = read_jsonl(sample_path)
    if not items:
        raise FileNotFoundError(
            f"{sample_path} is missing or empty. Run `python scripts/gold_sample.py` first."
        )
    app = LabelApp(items, LabelStore(labels_path), vocab, review_splits)
    server = ThreadingHTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
    actual_port = server.server_address[1]
    server.RequestHandlerClass = _make_handler(app, STATIC.read_bytes(), actual_port)
    return server
