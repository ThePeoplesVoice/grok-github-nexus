"""Voice Sense: session payload, stubs, token mint, public client hygiene."""

from __future__ import annotations

import json
import sys
import threading
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
VOICE = ROOT / "sense-to-code" / "voice-sense"
PUBLIC = VOICE / "public"
sys.path.insert(0, str(VOICE))

from session import (  # noqa: E402
    CLIENT_SECRETS_URL,
    MODEL,
    REALTIME_WS_URL,
    TOOLS,
    client_secret_request_body,
    function_call_output_event,
    public_config,
    response_create_event,
    session_update_event,
)
from tools import run_tool  # noqa: E402


def test_session_update_matches_docs():
    event = session_update_event()
    assert event["type"] == "session.update"
    session = event["session"]
    assert session["voice"] == "eve"
    assert session["turn_detection"] == {"type": "server_vad"}
    assert session["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert session["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24000}
    names = [t["name"] for t in session["tools"]]
    assert names == ["spawn_shape", "set_physics_param", "note_sensation_map"]
    for tool in session["tools"]:
        assert tool["type"] == "function"
        assert "parameters" in tool
    assert "one" in session["instructions"].lower()
    assert "personal" in session["instructions"].lower()
    assert "medical" not in session["instructions"].lower()


def test_client_secret_body_is_expires_after_only():
    body = client_secret_request_body()
    assert body == {"expires_after": {"seconds": 300}}


def test_realtime_url_uses_think_fast_2():
    assert MODEL == "grok-voice-think-fast-2.0"
    assert REALTIME_WS_URL == "wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0"
    assert CLIENT_SECRETS_URL == "https://api.x.ai/v1/realtime/client_secrets"


def test_function_call_output_and_response_create_shape():
    out = function_call_output_event("call_1", {"ok": True, "shape": "box"})
    assert out["type"] == "conversation.item.create"
    assert out["item"]["type"] == "function_call_output"
    assert out["item"]["call_id"] == "call_1"
    assert json.loads(out["item"]["output"])["shape"] == "box"
    assert response_create_event() == {"type": "response.create"}


def test_public_config_has_no_secret_fields():
    cfg = public_config()
    blob = json.dumps(cfg)
    assert "XAI_API_KEY" not in blob
    assert "Bearer" not in blob
    assert cfg["tools"] == [t["name"] for t in TOOLS]


def test_spawn_shape_stub():
    ok = run_tool("spawn_shape", {"shape": "sphere", "count": 2})
    assert ok == {"ok": True, "tool": "spawn_shape", "shape": "sphere", "count": 2}
    tower = run_tool("spawn_shape", {"shape": "tower", "count": 9})
    assert tower["count"] == 1
    bad = run_tool("spawn_shape", {"shape": "pyramid"})
    assert bad["ok"] is False


def test_set_physics_param_clamps():
    g = run_tool("set_physics_param", {"name": "gravity", "value": 12.5})
    assert g["ok"] is True
    assert g["value"] == 12.5
    hi = run_tool("set_physics_param", {"name": "bounciness", "value": 4})
    assert hi["value"] == 1.0
    assert hi["clamped"] is True
    bad = run_tool("set_physics_param", {"name": "mass", "value": 1})
    assert bad["ok"] is False


def test_note_sensation_map_is_not_a_dictionary_module():
    note = run_tool(
        "note_sensation_map",
        {
            "sensation": "volume",
            "maps_to": "impulse",
            "source": "world",
            "note": "short clap",
        },
    )
    assert note["ok"] is True
    assert note["dictionary"] == "chat-only"
    assert note["source"] == "world"


def test_unknown_tool():
    assert run_tool("delete_everything", {})["ok"] is False


def test_public_client_never_sees_api_key():
    for path in PUBLIC.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if path.name != "index.html":
            assert "XAI_API_KEY" not in text
        assert "process.env" not in text
        assert "Authorization" not in text
    app = (PUBLIC / "app.js").read_text(encoding="utf-8")
    assert "xai-client-secret." in app
    assert "function_call_output" in app
    assert "waitForPlaybackComplete" in app
    assert "response.create" in app
    index = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert "XAI_API_KEY" in index  # operator instruction only
    assert "xai-" not in index.lower() or "xai_api_key" in index.lower()


def _serve(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.setenv("VOICE_SENSE_HOST", "127.0.0.1")
    monkeypatch.setenv("VOICE_SENSE_PORT", "0")
    import server as voice_server

    httpd = voice_server.ThreadingHTTPServer(("127.0.0.1", 0), voice_server.VoiceSenseHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    return voice_server, httpd, host, port


def test_health_and_session_without_key(monkeypatch: pytest.MonkeyPatch):
    voice_server, httpd, host, port = _serve(monkeypatch)
    try:
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/health")
        health = json.loads(conn.getresponse().read().decode())
        assert health["ok"] is True
        assert health["has_key"] is False
        assert health["model"] == MODEL

        conn.request("GET", "/config")
        cfg = json.loads(conn.getresponse().read().decode())
        assert cfg["session_update"]["type"] == "session.update"

        conn.request("POST", "/session", body=b"", headers={"Content-Length": "0"})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        assert resp.status == 503
        assert "XAI_API_KEY" in body["error"]
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert voice_server.resolve_api_key() == ""


def test_tool_http_and_mint_payload(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_urlopen(req, timeout=20.0):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        captured["body"] = json.loads(req.data.decode())
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = json.dumps(
            {"value": "xai-realtime-client-secret-test", "expires_at": 1}
        ).encode()
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    monkeypatch.setenv("XAI_API_KEY", "xai-test-server-key")
    import server as voice_server

    httpd = voice_server.ThreadingHTTPServer(("127.0.0.1", 0), voice_server.VoiceSenseHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        with patch.object(voice_server, "urlopen", fake_urlopen):
            conn = HTTPConnection(host, port, timeout=5)
            conn.request("POST", "/session", body=b"", headers={"Content-Length": "0"})
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
            assert resp.status == 200
            assert body == {"value": "xai-realtime-client-secret-test", "expires_at": 1}
            assert captured["url"] == CLIENT_SECRETS_URL
            assert captured["auth"] == "Bearer xai-test-server-key"
            assert captured["body"] == {"expires_after": {"seconds": 300}}

            payload = json.dumps(
                {"name": "spawn_shape", "arguments": {"shape": "box"}}
            ).encode()
            conn.request(
                "POST",
                "/tool",
                body=payload,
                headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
            )
            tool_resp = json.loads(conn.getresponse().read().decode())
            assert tool_resp["ok"] is True
            assert tool_resp["shape"] == "box"
            conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_public_secret_payload_strips_unknown_fields():
    import server as voice_server

    slim = voice_server.public_secret_payload(
        {"value": "tok", "expires_at": 9, "api_key": "nope", "extra": 1}
    )
    assert slim == {"value": "tok", "expires_at": 9}
