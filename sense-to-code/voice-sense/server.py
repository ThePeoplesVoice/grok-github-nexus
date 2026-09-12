#!/usr/bin/env python3
"""Thin Voice Sense server: mint ephemeral tokens, serve the browser client.

The browser never sees XAI_API_KEY. Tokens come from
POST https://api.x.ai/v1/realtime/client_secrets
and the client authenticates the realtime WebSocket with
sec-websocket-protocol: xai-client-secret.<token>
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
sys.path.insert(0, str(HERE))

from session import (  # noqa: E402
    CLIENT_SECRETS_URL,
    client_secret_request_body,
    public_config,
)
from tools import run_tool  # noqa: E402

HOST = os.environ.get("VOICE_SENSE_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_SENSE_PORT", "8081"))


def resolve_api_key() -> str:
    return (os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY") or "").strip()


def mint_client_secret(api_key: str, timeout: float = 20.0) -> tuple[int, dict[str, Any]]:
    """POST /v1/realtime/client_secrets. Returns (status, body)."""
    body = json.dumps(client_secret_request_body()).encode("utf-8")
    req = Request(
        CLIENT_SECRETS_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"error": raw[:400]}
        return exc.code, parsed if isinstance(parsed, dict) else {"error": str(parsed)}
    except URLError as exc:
        return 502, {"error": f"could not reach xAI client_secrets: {exc.reason}"}
    except TimeoutError:
        return 504, {"error": "xAI client_secrets timed out"}


def public_secret_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Pass through documented fields only. Never echo the API key."""
    out: dict[str, Any] = {}
    if "value" in body:
        out["value"] = body["value"]
    if "expires_at" in body:
        out["expires_at"] = body["expires_at"]
    if "error" in body:
        out["error"] = body["error"]
    if "value" not in out and "error" not in out:
        out["error"] = body.get("message") or "unexpected client_secrets response"
    return out


class VoiceSenseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def log_message(self, fmt: str, *log_args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % log_args))

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 32_000:
            return {"_error": "payload too large"}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"_error": "invalid json"}
        return data if isinstance(data, dict) else {"_error": "json object required"}

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/health":
            self._json(
                200,
                {
                    "ok": True,
                    "has_key": bool(resolve_api_key()),
                    "model": public_config()["model"],
                },
            )
            return
        if self.path.split("?", 1)[0] == "/config":
            self._json(200, public_config())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/session":
            key = resolve_api_key()
            if not key:
                self._json(503, {"error": "XAI_API_KEY is not set on the server"})
                return
            status, body = mint_client_secret(key)
            self._json(status, public_secret_payload(body))
            return
        if path == "/tool":
            data = self._read_json()
            if "_error" in data:
                self._json(400, {"ok": False, "error": data["_error"]})
                return
            name = str(data.get("name") or "")
            arguments = data.get("arguments")
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                self._json(400, {"ok": False, "error": "arguments must be an object"})
                return
            self._json(200, run_tool(name, arguments))
            return
        self._json(404, {"error": "not found"})


def main() -> None:
    if not PUBLIC.is_dir():
        raise SystemExit(f"missing public dir: {PUBLIC}")
    server = ThreadingHTTPServer((HOST, PORT), VoiceSenseHandler)
    has_key = bool(resolve_api_key())
    print(f"Voice Sense  http://{HOST}:{PORT}")
    print(f"XAI_API_KEY  {'set' if has_key else 'MISSING — POST /session will 503'}")
    print("Browser talks to xAI over WebSocket with an ephemeral token only.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstop")
        server.server_close()


if __name__ == "__main__":
    main()
