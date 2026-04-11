from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx


API_BASE = os.environ.get("DEEPSAFETY_API_BASE", "http://127.0.0.1:8000").rstrip("/")
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "deepsafety-mcp", "version": "0.1.0"}


TOOLS = [
    {
        "name": "list_models",
        "description": "List implemented and planned DeepSafety consequence-analysis models.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_planned": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "get_model",
        "description": "Fetch a single model definition including equations and default constants.",
        "inputSchema": {
            "type": "object",
            "properties": {"model_id": {"type": "string"}},
            "required": ["model_id"],
        },
    },
    {
        "name": "calculate_model",
        "description": "Execute a DeepSafety calculation model directly through the HTTP API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_id": {"type": "string"},
                "inputs": {"type": "object"},
                "constants": {"type": "object"},
            },
            "required": ["model_id"],
        },
    },
    {
        "name": "evaluate_gis_scenario",
        "description": "Run a GIS screening scenario with a source pin and receptor pins.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario_type": {"type": "string"},
                "model_id": {"type": "string"},
                "source": {"type": "object"},
                "receptors": {"type": "array"},
                "inputs": {"type": "object"},
                "constants": {"type": "object"},
            },
            "required": ["scenario_type", "source"],
        },
    },
    {
        "name": "list_constants",
        "description": "List all default constants or the defaults for a single model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_id": {"type": "string"},
            },
        },
    },
]


def _send(message: dict[str, Any]) -> None:
    body = json.dumps(message).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, Any] | None:
    content_length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())

    if content_length is None:
        return None

    payload = sys.stdin.buffer.read(content_length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def _call_api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    with httpx.Client(timeout=30.0) as client:
        response = client.request(method, f"{API_BASE}{path}", json=payload)
        response.raise_for_status()
        return response.json()


def _tool_result(data: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, indent=2),
            }
        ],
        "structuredContent": data,
    }


def _tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def _handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "list_models":
            include_planned = str(arguments.get("include_planned", True)).lower()
            data = _call_api("GET", f"/models?include_planned={include_planned}")
            return _tool_result(data)

        if name == "get_model":
            data = _call_api("GET", f"/models/{arguments['model_id']}")
            return _tool_result(data)

        if name == "calculate_model":
            data = _call_api(
                "POST",
                f"/models/{arguments['model_id']}/calculate",
                {
                    "inputs": arguments.get("inputs", {}),
                    "constants": arguments.get("constants", {}),
                },
            )
            return _tool_result(data)

        if name == "evaluate_gis_scenario":
            data = _call_api(
                "POST",
                "/gis/scenarios/evaluate",
                {
                    "scenario_type": arguments["scenario_type"],
                    "model_id": arguments.get("model_id"),
                    "source": arguments["source"],
                    "receptors": arguments.get("receptors", []),
                    "inputs": arguments.get("inputs", {}),
                    "constants": arguments.get("constants", {}),
                },
            )
            return _tool_result(data)

        if name == "list_constants":
            model_id = arguments.get("model_id")
            path = f"/constants/{model_id}" if model_id else "/constants"
            data = _call_api("GET", path)
            return _tool_result(data)
    except httpx.HTTPStatusError as exc:
        return _tool_error(
            f"HTTP error {exc.response.status_code} from DeepSafety API: {exc.response.text}"
        )
    except Exception as exc:  # pragma: no cover - defensive MCP boundary handling.
        return _tool_error(str(exc))

    return _tool_error(f"Unknown tool '{name}'.")


def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = message.get("params", {})
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _handle_tool_call(
                params.get("name", ""),
                params.get("arguments", {}),
            ),
        }

    if request_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found."},
        }

    return None


def main() -> None:
    while True:
        message = _read_message()
        if message is None:
            break
        response = _handle_message(message)
        if response is not None:
            _send(response)
