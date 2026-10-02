#!/usr/bin/env python3
"""Space catalog and helper functions for Taku (taku.cool) multi-space environments.

Provides Single Source of Truth (SSOT) mappings for customer spaces,
public project keys, script embed snippets, and feed URLs.
Supports loading custom spaces from .spaces.json or environment variables.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SpaceInfo:
    space_id: int
    name: str
    slug: str
    project_key: str
    dashboard_url: str = ""
    primary_domain: str = ""
    account_id: int = 101

    @property
    def embed_snippet(self) -> str:
        return (
            f'<script src="https://cdn.taku.cool/js/latest.js"></script>\n'
            f'<script>\n'
            f"  window.Taku('news:boot', {{\n"
            f"    api_public_key: '{self.project_key}'\n"
            f"  }});\n"
            f"</script>"
        )

    def feed_url(self, popup_id: int | str) -> str:
        return f"https://ui.taku.cool/feed/{self.project_key}/{popup_id}"


DEFAULT_DEMO_SPACES: Dict[int, SpaceInfo] = {
    1001: SpaceInfo(
        space_id=1001,
        name="Demo E-Commerce Store",
        slug="demo-store",
        project_key="demo_pk_9a8b7c6d5e4f3a2b1c0d",
        dashboard_url="https://dashboard.taku.cool/accounts/demo/spaces/1001/api",
        primary_domain="",
    ),
    1002: SpaceInfo(
        space_id=1002,
        name="Demo SaaS Platform",
        slug="demo-saas",
        project_key="demo_pk_1f2e3d4c5b6a7b8c9d0e",
        dashboard_url="https://dashboard.taku.cool/accounts/demo/spaces/1002/api",
        primary_domain="",
    ),
    1003: SpaceInfo(
        space_id=1003,
        name="Demo Digital Media Hub",
        slug="demo-media",
        project_key="demo_pk_3b4c5d6e7f8a9b0c1d2e",
        dashboard_url="https://dashboard.taku.cool/accounts/demo/spaces/1003/api",
        primary_domain="",
    ),
}


def _load_spaces() -> tuple[Dict[int, SpaceInfo], Dict[str, int]]:
    """Load spaces from configuration file, env vars, or defaults."""
    spaces: Dict[int, SpaceInfo] = {}
    alias_map: Dict[str, int] = {}

    # Check for custom spaces file (priority: env var > local .spaces.json)
    custom_path = os.environ.get("TAKU_SPACES_FILE")
    if not custom_path:
        local_config = Path(__file__).resolve().parent / ".spaces.json"
        if local_config.exists():
            custom_path = str(local_config)

    raw_items = []
    if custom_path and Path(custom_path).exists():
        try:
            with open(custom_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_items = data.get("spaces", data if isinstance(data, list) else [])
        except Exception:
            raw_items = []
    elif os.environ.get("TAKU_SPACES_JSON"):
        try:
            data = json.loads(os.environ["TAKU_SPACES_JSON"])
            raw_items = data.get("spaces", data if isinstance(data, list) else [])
        except Exception:
            raw_items = []

    if raw_items:
        for item in raw_items:
            sid = int(item["space_id"])
            sinfo = SpaceInfo(
                space_id=sid,
                name=item.get("name", f"Space {sid}"),
                slug=item.get("slug", f"space-{sid}"),
                project_key=item.get("project_key", ""),
                dashboard_url=item.get("dashboard_url", ""),
                primary_domain=item.get("primary_domain", ""),
                account_id=int(item.get("account_id", 0)),
            )
            spaces[sid] = sinfo
            alias_map[str(sid)] = sid
            if sinfo.slug:
                alias_map[sinfo.slug.lower()] = sid
                alias_map[sinfo.slug.lower().replace("-", "_")] = sid
                alias_map[sinfo.slug.lower().replace("-", "")] = sid
            for alias in item.get("aliases", []):
                alias_map[alias.lower()] = sid
        return spaces, alias_map

    # Fallback to default demo spaces
    for sid, sinfo in DEFAULT_DEMO_SPACES.items():
        spaces[sid] = sinfo
        alias_map[str(sid)] = sid
        alias_map[sinfo.slug] = sid
        alias_map[sinfo.slug.replace("-", "_")] = sid

    return spaces, alias_map


KNOWN_SPACES, ALIAS_MAP = _load_spaces()


def reload_spaces():
    """Reload spaces dynamically from disk or environment."""
    global KNOWN_SPACES, ALIAS_MAP
    KNOWN_SPACES, ALIAS_MAP = _load_spaces()


def resolve_space(identifier: str | int | None) -> SpaceInfo:
    """Resolve an identifier (ID integer, ID string, or slug alias) to SpaceInfo."""
    if not KNOWN_SPACES:
        reload_spaces()

    default_sid = next(iter(KNOWN_SPACES.keys()))
    if identifier is None or identifier == "":
        return KNOWN_SPACES[default_sid]

    if isinstance(identifier, int):
        if identifier in KNOWN_SPACES:
            return KNOWN_SPACES[identifier]
        return SpaceInfo(
            space_id=identifier,
            name=f"Custom Space {identifier}",
            slug=f"space-{identifier}",
            project_key="",
            dashboard_url="",
        )

    cleaned = str(identifier).strip().lower()
    if cleaned in ALIAS_MAP:
        return KNOWN_SPACES[ALIAS_MAP[cleaned]]

    try:
        numeric_id = int(cleaned)
        if numeric_id in KNOWN_SPACES:
            return KNOWN_SPACES[numeric_id]
        return SpaceInfo(
            space_id=numeric_id,
            name=f"Custom Space {numeric_id}",
            slug=f"space-{numeric_id}",
            project_key="",
            dashboard_url="",
        )
    except ValueError:
        raise ValueError(
            f"Unknown space identifier '{identifier}'. Known aliases: {list(ALIAS_MAP.keys())}"
        )


def list_known_spaces() -> List[SpaceInfo]:
    """Return all configured spaces."""
    return list(KNOWN_SPACES.values())
