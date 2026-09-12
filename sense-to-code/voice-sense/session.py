"""Session payload for xAI Speech-to-Speech. Matches published docs only."""

from __future__ import annotations

import json
from typing import Any

# Flagship voice model (docs also accept grok-voice-latest).
MODEL = "grok-voice-think-fast-2.0"
REALTIME_WS_URL = f"wss://api.x.ai/v1/realtime?model={MODEL}"
CLIENT_SECRETS_URL = "https://api.x.ai/v1/realtime/client_secrets"
TOKEN_TTL_SECONDS = 300
VOICE = "eve"
PCM_RATE = 24000

INSTRUCTIONS = (
    "You map spoken intent to Sense Lab tools. "
    "The room may be noisy; act on clear intent and ignore background chatter. "
    "Call a tool when the operator wants a shape spawned, a physics value changed, "
    "or a sensation named onto a lab parameter. "
    "If you need clarification, ask one short question, then wait. "
    "Keep speech brief. Confirm what the tool did. "
    "Do not ask for personal data."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "spawn_shape",
        "description": "Add a primitive or a tower to the Sense Lab plate.",
        "parameters": {
            "type": "object",
            "properties": {
                "shape": {
                    "type": "string",
                    "enum": ["sphere", "box", "cylinder", "tower"],
                    "description": "What to spawn.",
                },
                "count": {
                    "type": "integer",
                    "description": "How many to add. Default 1. Tower ignores count.",
                    "minimum": 1,
                    "maximum": 8,
                },
            },
            "required": ["shape"],
        },
    },
    {
        "type": "function",
        "name": "set_physics_param",
        "description": "Set a world prior on the plate: gravity, bounciness, or friction.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": ["gravity", "bounciness", "friction"],
                    "description": "Which prior to change.",
                },
                "value": {
                    "type": "number",
                    "description": "New value. Gravity is m/s^2; others are 0–1.",
                },
            },
            "required": ["name", "value"],
        },
    },
    {
        "type": "function",
        "name": "note_sensation_map",
        "description": (
            "Note a sensation-to-parameter mapping on the local stage. "
            "This is not a dictionary module. Named posteriors stay in chat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sensation": {
                    "type": "string",
                    "description": "Felt channel, e.g. volume or pitch.",
                },
                "maps_to": {
                    "type": "string",
                    "description": "Lab parameter, e.g. impulse, gravity, color.",
                },
                "source": {
                    "type": "string",
                    "enum": ["self", "world", "unknown"],
                    "description": "Who produced it.",
                },
                "note": {
                    "type": "string",
                    "description": "One short operator line. No personal data.",
                },
            },
            "required": ["sensation", "maps_to"],
        },
    },
]


def session_update_event() -> dict[str, Any]:
    """Client event sent after the WebSocket opens."""
    return {
        "type": "session.update",
        "session": {
            "voice": VOICE,
            "instructions": INSTRUCTIONS,
            "turn_detection": {"type": "server_vad"},
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": PCM_RATE}},
                "output": {"format": {"type": "audio/pcm", "rate": PCM_RATE}},
            },
            "tools": TOOLS,
        },
    }


def client_secret_request_body() -> dict[str, Any]:
    """POST /v1/realtime/client_secrets body. Docs: expires_after only."""
    return {"expires_after": {"seconds": TOKEN_TTL_SECONDS}}


def function_call_output_event(call_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """conversation.item.create after response.function_call_arguments.done."""
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(result),
        },
    }


def response_create_event() -> dict[str, Any]:
    """Ask the agent to continue after tool outputs (and after playback)."""
    return {"type": "response.create"}


def public_config() -> dict[str, Any]:
    """Browser-safe config. No API key."""
    return {
        "model": MODEL,
        "realtime_url": REALTIME_WS_URL,
        "session_update": session_update_event(),
        "tools": [tool["name"] for tool in TOOLS],
    }
