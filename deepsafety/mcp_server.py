from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx


API_BASE = os.environ.get("DEEPSAFETY_API_BASE", "http://127.0.0.1:8000").rstrip("/")
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "deepsafety-mcp", "version": "1.0.1"}


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
    {
        "name": "get_service_catalog",
        "description": "Fetch the DeepSafety service catalog with equations, assumptions, constants, and references.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "call_api_path",
        "description": "Call any DeepSafety API path directly. Use this for newly added OpenAPI-aligned endpoints that are not yet exposed as dedicated MCP tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "path": {"type": "string"},
                "body": {"type": "object"},
            },
            "required": ["method", "path"],
        },
    },
    {
        "name": "define_scenario",
        "description": "Build a normalized scenario definition for realistic or worst-case screening.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_type": {"type": "string"},
                "classification": {"type": "string"},
                "inventory": {"type": "object"},
                "equipment": {"type": "object"},
                "failure_mode": {"type": "string"},
                "meteorology": {"type": "object"},
                "release_height_m": {"type": "number"},
                "topography": {"type": "string"},
                "release_duration_s": {"type": "number"},
                "conservative_mode": {"type": "boolean"},
            },
            "required": ["incident_type", "classification"],
        },
    },
    {
        "name": "list_scenario_templates",
        "description": "List prebuilt DeepSafety scenario templates.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "solve_source_model",
        "description": "Execute a DeepSafety source-term screening model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["model_type"],
        },
    },
    {
        "name": "solve_dispersion_model",
        "description": "Execute a DeepSafety dispersion screening model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["model_type"],
        },
    },
    {
        "name": "solve_fire_explosion_model",
        "description": "Execute a DeepSafety fire or explosion screening model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["model_type"],
        },
    },
    {
        "name": "solve_effect_model",
        "description": "Execute a DeepSafety toxic, thermal, or explosion effect model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["model_type"],
        },
    },
    {
        "name": "lookup_toxic_criteria",
        "description": "Fetch toxic effect criteria such as AEGL, ERPG, IDLH, TLV, PEL, and toxic endpoints from the DeepSafety starter registry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chemical": {"type": "string"},
                "criteria_names": {"type": "array"},
                "criteria_overrides": {"type": "object"},
            },
            "required": ["chemical"],
        },
    },
    {
        "name": "solve_prevention_response_model",
        "description": "Execute DeepSafety prevention, ignition, spray/mist, or emergency response screening models.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["model_type"],
        },
    },
    {
        "name": "solve_visualization",
        "description": "Build a DeepSafety visualization payload such as contours or time evolution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer_type": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["layer_type"],
        },
    },
    {
        "name": "get_impact_zones",
        "description": "Generate map-ready impact circles for fire or leak screening.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario_type": {"type": "string"},
                "source": {"type": "object"},
                "asset": {"type": "object"},
                "criteria": {"type": "array"},
                "constants": {"type": "object"},
            },
            "required": ["scenario_type", "source"],
        },
    },
    {
        "name": "analyze_sign",
        "description": "Classify a process-safety sign from OCR or manually entered sign text and return a leak-ready scenario seed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string"},
                "image_media_type": {"type": "string"},
                "observed_text": {"type": "string"},
                "locale": {"type": "string"},
                "site_context": {"type": "string"},
                "topography": {"type": "string"},
                "stability_class": {"type": "string"},
                "wind_speed_m_s": {"type": "number"},
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

        if name == "get_service_catalog":
            data = _call_api("GET", "/service-catalog")
            return _tool_result(data)

        if name == "call_api_path":
            method = str(arguments["method"]).upper()
            path = str(arguments["path"])
            if not path.startswith("/"):
                path = f"/{path}"
            data = _call_api(method, path, arguments.get("body"))
            return _tool_result(data)

        if name == "define_scenario":
            data = _call_api("POST", "/scenario-engine/define", arguments)
            return _tool_result(data)

        if name == "list_scenario_templates":
            data = _call_api("GET", "/scenario-library/templates")
            return _tool_result(data)

        if name == "solve_source_model":
            data = _call_api(
                "POST",
                "/source-models/solve",
                {"model_type": arguments["model_type"], "inputs": arguments.get("inputs", {})},
            )
            return _tool_result(data)

        if name == "solve_dispersion_model":
            data = _call_api(
                "POST",
                "/dispersion-models/solve",
                {"model_type": arguments["model_type"], "inputs": arguments.get("inputs", {})},
            )
            return _tool_result(data)

        if name == "solve_fire_explosion_model":
            data = _call_api(
                "POST",
                "/fire-explosion-models/solve",
                {"model_type": arguments["model_type"], "inputs": arguments.get("inputs", {})},
            )
            return _tool_result(data)

        if name == "solve_effect_model":
            data = _call_api(
                "POST",
                "/effect-models/solve",
                {"model_type": arguments["model_type"], "inputs": arguments.get("inputs", {})},
            )
            return _tool_result(data)

        if name == "lookup_toxic_criteria":
            data = _call_api(
                "POST",
                "/toxic-criteria/lookup",
                {
                    "model_type": "toxic_criteria_lookup",
                    "inputs": {
                        "chemical": arguments["chemical"],
                        "criteria_names": arguments.get("criteria_names"),
                        "criteria_overrides": arguments.get("criteria_overrides", {}),
                    },
                },
            )
            return _tool_result(data)

        if name == "solve_prevention_response_model":
            data = _call_api(
                "POST",
                "/prevention-response-models/solve",
                {"model_type": arguments["model_type"], "inputs": arguments.get("inputs", {})},
            )
            return _tool_result(data)

        if name == "solve_visualization":
            data = _call_api(
                "POST",
                "/visualization/solve",
                {"layer_type": arguments["layer_type"], "inputs": arguments.get("inputs", {})},
            )
            return _tool_result(data)

        if name == "get_impact_zones":
            data = _call_api(
                "POST",
                "/gis/impact-zones",
                {
                    "scenario_type": arguments["scenario_type"],
                    "source": arguments["source"],
                    "asset": arguments.get("asset", {}),
                    "criteria": arguments.get("criteria", []),
                    "constants": arguments.get("constants", {}),
                },
            )
            return _tool_result(data)

        if name == "analyze_sign":
            data = _call_api(
                "POST",
                "/signs/analyze",
                {
                    "image_base64": arguments.get("image_base64"),
                    "image_media_type": arguments.get("image_media_type"),
                    "observed_text": arguments.get("observed_text"),
                    "locale": arguments.get("locale"),
                    "site_context": arguments.get("site_context"),
                    "topography": arguments.get("topography"),
                    "stability_class": arguments.get("stability_class"),
                    "wind_speed_m_s": arguments.get("wind_speed_m_s"),
                },
            )
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
