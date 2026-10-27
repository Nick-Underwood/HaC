"""
Home Assistant MCP Server — wraps HA REST API as MCP tools over SSE.

Env vars:
    HA_URL      - HA base URL (default: http://homeassistant:8123)
    HA_TOKEN    - HA long-lived access token (required)
    SERVER_PORT - HTTP port (default: 3000)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import uvicorn

HA_URL = os.environ.get("HA_URL", "http://homeassistant:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "3000"))

if not HA_TOKEN:
    raise SystemExit("HA_TOKEN required")

http = httpx.AsyncClient(
    base_url=f"{HA_URL}/api/",
    headers={"Authorization": f"Bearer {HA_TOKEN}"},
    timeout=30.0,
)


async def ha_get(path: str) -> Any:
    r = await http.get(path.lstrip("/"))
    r.raise_for_status()
    return r.json() if r.status_code != 204 else None


async def ha_post(path: str, **data: Any) -> Any:
    r = await http.post(path.lstrip("/"), json=data)
    r.raise_for_status()
    return r.json() if r.status_code != 204 else None


server = Server("home-assistant-mcp")


@server.list_tools()
async def list_tools() -> list[dict]:
    return [
        {"name": "ha_get_state", "description": "Get state of a HA entity",
         "inputSchema": {"type": "object", "properties": {"entity_id": {"type": "string"}},
                         "required": ["entity_id"]}},
        {"name": "ha_set_state", "description": "Set state of a HA entity directly",
         "inputSchema": {"type": "object", "properties": {"entity_id": {"type": "string"},
                         "state": {"type": "string"}, "attributes": {"type": "object"}},
                         "required": ["entity_id", "state"]}},
        {"name": "ha_call_service", "description": "Call a HA service",
         "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"},
                         "service": {"type": "string"}, "service_data": {"type": "object"}},
                         "required": ["domain", "service"]}},
        {"name": "ha_get_states", "description": "List HA states (optional filter prefix)",
         "inputSchema": {"type": "object", "properties": {"filter": {"type": "string"}},
                         "required": []}},
        {"name": "ha_get_config", "description": "Get HA configuration",
         "inputSchema": {"type": "object", "properties": {}, "required": []}},
        {"name": "ha_get_areas", "description": "List HA areas",
         "inputSchema": {"type": "object", "properties": {}, "required": []}},
        {"name": "ha_get_devices", "description": "List HA devices",
         "inputSchema": {"type": "object", "properties": {}, "required": []}},
        {"name": "ha_get_services", "description": "List available HA services",
         "inputSchema": {"type": "object", "properties": {}, "required": []}},
        {"name": "ha_fire_event", "description": "Fire a HA event",
         "inputSchema": {"type": "object", "properties": {"event_type": {"type": "string"},
                         "event_data": {"type": "object"}},
                         "required": ["event_type"]}},
    ]


@server.call_tool()
async def ha_get_state(args: dict) -> list[Any]:
    return [await ha_get(f"/states/{args['entity_id']}")]


@server.call_tool()
async def ha_set_state(args: dict) -> list[Any]:
    return [await ha_post("/states/" + args["entity_id"],
                          state=args["state"], attributes=args.get("attributes", {}))]


@server.call_tool()
async def ha_call_service(args: dict) -> list[Any]:
    return [await ha_post(f"/services/{args['domain']}/{args['service']}",
                          **args.get("service_data", {}))]


@server.call_tool()
async def ha_get_states(args: dict) -> list[Any]:
    all_states = await ha_get("/states") or []
    filt = args.get("filter", "")
    return [s for s in all_states if not filt or s.get("entity_id", "").startswith(filt)]


@server.call_tool()
async def ha_get_config(_: dict) -> list[Any]:
    return [await ha_get("/config")]


@server.call_tool()
async def ha_get_areas(_: dict) -> list[Any]:
    return [await ha_get("/areas")]


@server.call_tool()
async def ha_get_devices(_: dict) -> list[Any]:
    return [await ha_get("/devices")]


@server.call_tool()
async def ha_get_services(_: dict) -> list[Any]:
    return [await ha_get("/services")]


@server.call_tool()
async def ha_fire_event(args: dict) -> list[Any]:
    return [await ha_post("/events", event_type=args["event_type"],
                          **args.get("event_data", {}))]


app = FastAPI()
sse = SseServerTransport(f"http://0.0.0.0:{SERVER_PORT}/sse")


@app.post("/mcp")
async def handle_mcp(request: Request):
    await server.run(sse.connect_sse(request.headers, request.stream), request.headers)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "ha_url": HA_URL}


def main() -> None:
    print(f"HA MCP server starting on :{SERVER_PORT} (HA: {HA_URL})")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
