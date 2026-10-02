#!/usr/bin/env python3
"""Taku Studio Production Server (`server.py`).

Provides:
- First-Principles Unidirectional Data Flow (Read = Taku API -> Store -> Render; Write = UI -> Taku API -> Authoritative Re-read -> Render)
- Zero-drift live API synchronization
- Server-Sent Events (SSE) push channel for live notifications
- Embedded Trigger & Audience Evaluation engine
- High-fidelity sandbox frame and static UI serving
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aiohttp import web

# Configure paths
CURRENT_DIR = Path(__file__).resolve().parent
TAKU_OPS_DIR = Path.home() / ".gemini/antigravity/skills/taku-ops/scripts"

for p in (CURRENT_DIR, TAKU_OPS_DIR):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    import space_catalog
    from taku_client import TakuAuthError, TakuClient, TakuError, TakuNotFoundError
except ImportError as e:
    raise RuntimeError(f"Failed to import taku-ops client modules: {e}") from e

from evaluator import evaluate_popup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("taku-studio")

STATIC_DIR = CURRENT_DIR / "static"


class EventBroadcaster:
    """Manages active SSE client connections and broadcasts live events."""

    def __init__(self) -> None:
        self._connections: Set[web.Response] = set()

    async def register(self, response: web.Response) -> None:
        self._connections.add(response)
        logger.info(f"SSE client connected. Active: {len(self._connections)}")

    async def unregister(self, response: web.Response) -> None:
        self._connections.discard(response)
        logger.info(f"SSE client disconnected. Active: {len(self._connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        if not self._connections:
            return
        payload = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        dead: Set[web.Response] = set()
        for resp in list(self._connections):
            try:
                await resp.write(payload.encode("utf-8"))
            except Exception:
                dead.add(resp)
        for d in dead:
            self._connections.discard(d)


broadcaster = EventBroadcaster()


_CLIENT: Optional[TakuClient] = None


def get_taku_client() -> TakuClient:
    """Retrieve cached Taku API client instance with unattended auth."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = TakuClient()
    return _CLIENT


# ---------------- API Routes ----------------


async def api_health(request: web.Request) -> web.Response:
    """Basic service health check."""
    return web.json_response({"status": "ok", "app": "Taku Studio", "version": "1.0.0"})


async def api_diagnose(request: web.Request) -> web.Response:
    """Deep live diagnostic against Taku API and spaces."""
    loop = asyncio.get_event_loop()
    client = get_taku_client()
    report = await loop.run_in_executor(None, client.diagnose)
    await broadcaster.broadcast("diagnose_checked", {"status": report.get("status")})
    return web.json_response(report)


async def api_list_spaces(request: web.Request) -> web.Response:
    """List configured customer spaces."""
    spaces = space_catalog.list_known_spaces()
    data = []
    for s in spaces:
        data.append(
            {
                "space_id": s.space_id,
                "name": s.name,
                "slug": s.slug,
                "project_key": s.project_key,
                "primary_domain": getattr(s, "primary_domain", ""),
                "dashboard_url": s.dashboard_url,
                "embed_snippet": s.embed_snippet,
            }
        )
    return web.json_response({"spaces": data})


async def api_list_popups(request: web.Request) -> web.Response:
    """List popups for a space with authoritative Taku API query."""
    space_id = request.match_info["space_id"]
    page = int(request.query.get("page", 1))
    per_page = int(request.query.get("per_page", 50))

    loop = asyncio.get_event_loop()
    client = get_taku_client()
    try:
        res = await loop.run_in_executor(
            None,
            lambda: client.list_popups(space_id=space_id, page=page, per_page=per_page),
        )
        popups_list = res.get("collection") or res.get("data") or []
        enriched = []
        for p in popups_list:
            item = dict(p)
            item["extracted_title"] = client.extract_title(p)
            enriched.append(item)
        return web.json_response({"space_id": space_id, "popups": enriched, "total": len(enriched)})
    except TakuError as err:
        return web.json_response({"error": str(err)}, status=err.status_code or 500)
    except Exception as err:
        logger.exception(f"Unexpected error in api_list_popups: {err}")
        return web.json_response({"error": f"Internal error: {err}"}, status=500)


async def api_get_popup(request: web.Request) -> web.Response:
    """Get single popup authoritative details."""
    popup_id = request.match_info["popup_id"]
    loop = asyncio.get_event_loop()
    client = get_taku_client()
    try:
        data = await loop.run_in_executor(None, lambda: client.get_popup(popup_id))
        item = data.get("data", data)
        item["extracted_title"] = client.extract_title(item)
        return web.json_response(item)
    except TakuNotFoundError:
        return web.json_response({"error": f"Popup {popup_id} not found"}, status=404)
    except TakuError as err:
        return web.json_response({"error": str(err)}, status=err.status_code or 500)
    except Exception as err:
        logger.exception(f"Unexpected error in api_get_popup: {err}")
        return web.json_response({"error": f"Internal error: {err}"}, status=500)


async def api_toggle_popup(request: web.Request) -> web.Response:
    """Toggle popup enabled state and immediately re-read authoritative record."""
    popup_id = request.match_info["popup_id"]
    body = await request.json()
    new_state = bool(body.get("display_enabled", False))

    loop = asyncio.get_event_loop()
    client = get_taku_client()
    try:
        # Write to API
        await loop.run_in_executor(
            None,
            lambda: client.update_popup(popup_id, {"display_enabled": new_state}),
        )
        # Re-read authoritative state (Unidirectional data flow invariant)
        fresh_data = await loop.run_in_executor(None, lambda: client.get_popup(popup_id))
        authoritative = fresh_data.get("data", fresh_data)
        authoritative["extracted_title"] = client.extract_title(authoritative)

        await broadcaster.broadcast(
            "popup_toggled",
            {
                "popup_id": popup_id,
                "display_enabled": authoritative.get("display_enabled"),
                "timestamp": time.time(),
            },
        )
        return web.json_response(authoritative)
    except TakuError as err:
        return web.json_response({"error": str(err)}, status=err.status_code or 500)
    except Exception as err:
        logger.exception(f"Unexpected error in api_toggle_popup: {err}")
        return web.json_response({"error": f"Internal error: {err}"}, status=500)


async def api_update_popup(request: web.Request) -> web.Response:
    """Update popup configuration, write to API, and re-read authoritative state."""
    popup_id = request.match_info["popup_id"]
    payload = await request.json()

    loop = asyncio.get_event_loop()
    client = get_taku_client()
    try:
        await loop.run_in_executor(
            None,
            lambda: client.update_popup(popup_id, payload),
        )
        fresh_data = await loop.run_in_executor(None, lambda: client.get_popup(popup_id))
        authoritative = fresh_data.get("data", fresh_data)
        authoritative["extracted_title"] = client.extract_title(authoritative)

        await broadcaster.broadcast(
            "popup_updated",
            {
                "popup_id": popup_id,
                "title": authoritative.get("extracted_title"),
                "timestamp": time.time(),
            },
        )
        return web.json_response(authoritative)
    except TakuError as err:
        return web.json_response({"error": str(err)}, status=err.status_code or 500)
    except Exception as err:
        logger.exception(f"Unexpected error in api_update_popup: {err}")
        return web.json_response({"error": f"Internal error: {err}"}, status=500)


async def api_create_popup(request: web.Request) -> web.Response:
    """Create a new popup in space and return authoritative state."""
    space_id = request.match_info["space_id"]
    payload = await request.json()

    loop = asyncio.get_event_loop()
    client = get_taku_client()
    try:
        created = await loop.run_in_executor(
            None,
            lambda: client.create_popup(space_id, payload),
        )
        created_id = created.get("id") or (created.get("data", {})).get("id")
        if created_id:
            fresh = await loop.run_in_executor(None, lambda: client.get_popup(created_id))
            authoritative = fresh.get("data", fresh)
        else:
            authoritative = created
        authoritative["extracted_title"] = client.extract_title(authoritative)

        await broadcaster.broadcast(
            "popup_created",
            {
                "space_id": space_id,
                "popup_id": created_id,
                "timestamp": time.time(),
            },
        )
        return web.json_response(authoritative, status=201)
    except TakuError as err:
        return web.json_response({"error": str(err)}, status=err.status_code or 500)
    except Exception as err:
        logger.exception(f"Unexpected error in api_create_popup: {err}")
        return web.json_response({"error": f"Internal error: {err}"}, status=500)


async def api_delete_popup(request: web.Request) -> web.Response:
    """Delete a popup."""
    popup_id = request.match_info["popup_id"]
    loop = asyncio.get_event_loop()
    client = get_taku_client()
    try:
        res = await loop.run_in_executor(None, lambda: client.delete_popup(popup_id))
        await broadcaster.broadcast(
            "popup_deleted",
            {"popup_id": popup_id, "timestamp": time.time()},
        )
        return web.json_response(res if isinstance(res, dict) else {"status": "success", "popup_id": popup_id})
    except TakuError as err:
        return web.json_response({"error": str(err)}, status=err.status_code or 500)
    except Exception as err:
        logger.exception(f"Unexpected error in api_delete_popup: {err}")
        return web.json_response({"error": f"Internal error: {err}"}, status=500)


async def api_simulate_trigger(request: web.Request) -> web.Response:
    """Evaluate audience conditions and trigger rules against a popup."""
    body = await request.json()
    popup = body.get("popup")
    url = body.get("url", "")
    device = body.get("device", "desktop")
    past_triggers = int(body.get("past_triggers_count", 0))
    ignore_paused = bool(body.get("ignore_paused", False))
    exit_intent = bool(body.get("exit_intent", False))
    location = body.get("location")
    seconds_since = body.get("seconds_since_last_trigger")
    if seconds_since is not None:
        seconds_since = float(seconds_since)

    if not popup:
        return web.json_response({"error": "Missing 'popup' payload"}, status=400)

    report = evaluate_popup(
        popup=popup,
        url=url,
        device=device,
        past_triggers_count=past_triggers,
        seconds_since_last_trigger=seconds_since,
        ignore_paused=ignore_paused,
        exit_intent=exit_intent,
        location=location,
    )
    return web.json_response(report.to_dict())


async def api_get_snippet(request: web.Request) -> web.Response:
    """Get embed snippet and feed URL for space and optional popup."""
    space_id = request.match_info["space_id"]
    popup_id = request.query.get("popup_id", "3118")
    space = space_catalog.resolve_space(space_id)
    return web.json_response(
        {
            "space_id": space.space_id,
            "name": space.name,
            "slug": space.slug,
            "project_key": space.project_key,
            "embed_snippet": space.embed_snippet,
            "feed_url": space.feed_url(popup_id),
            "script_cdn": "https://cdn.taku.cool/js/latest.js",
        }
    )


async def api_sse_events(request: web.Request) -> web.StreamResponse:
    """Server-Sent Events (SSE) live push stream."""
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)
    await broadcaster.register(response)

    # Initial ping
    init_msg = f"event: connected\ndata: {json.dumps({'time': time.time(), 'message': 'Taku Live Stream Connected'})}\n\n"
    try:
        await response.write(init_msg.encode("utf-8"))
    except Exception:
        await broadcaster.unregister(response)
        return response

    try:
        while True:
            await asyncio.sleep(25)
            # Heartbeat ping
            heartbeat = f": heartbeat {time.time()}\n\n"
            try:
                await response.write(heartbeat.encode("utf-8"))
            except Exception:
                break
    except (asyncio.CancelledError, ConnectionResetError, Exception):
        pass
    finally:
        await broadcaster.unregister(response)

    return response


# ---------------- Web Pages ----------------


async def index_handler(request: web.Request) -> web.Response:
    """Serve the primary Taku Studio single-page application."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return web.Response(text="index.html not found", status=404)
    return web.FileResponse(index_file)


async def preview_sandbox_handler(request: web.Request) -> web.Response:
    """Serve realistic popup sandbox iframe."""
    sandbox_file = STATIC_DIR / "preview_sandbox.html"
    if not sandbox_file.exists():
        return web.Response(text="preview_sandbox.html not found", status=404)
    return web.FileResponse(sandbox_file)


def create_app() -> web.Application:
    """Assemble and configure the aiohttp application."""
    app = web.Application()

    # API endpoints
    app.router.add_get("/api/health", api_health)
    app.router.add_get("/api/diagnose", api_diagnose)
    app.router.add_get("/api/spaces", api_list_spaces)
    app.router.add_get("/api/spaces/{space_id}/popups", api_list_popups)
    app.router.add_get("/api/popups/{popup_id}", api_get_popup)
    app.router.add_post("/api/popups/{popup_id}/toggle", api_toggle_popup)
    app.router.add_put("/api/popups/{popup_id}", api_update_popup)
    app.router.add_post("/api/spaces/{space_id}/popups", api_create_popup)
    app.router.add_delete("/api/popups/{popup_id}", api_delete_popup)
    app.router.add_post("/api/simulate", api_simulate_trigger)
    app.router.add_get("/api/snippet/{space_id}", api_get_snippet)
    app.router.add_get("/api/events", api_sse_events)

    # UI Pages
    app.router.add_get("/", index_handler)
    app.router.add_get("/preview-sandbox.html", preview_sandbox_handler)
    app.router.add_get("/preview_sandbox.html", preview_sandbox_handler)

    # Static assets
    if STATIC_DIR.exists():
        app.router.add_static("/static/", path=str(STATIC_DIR), name="static")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Taku Studio Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    app = create_app()
    logger.info(f"Starting Taku Studio at http://{args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
