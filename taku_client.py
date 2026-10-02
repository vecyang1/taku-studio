#!/usr/bin/env python3
"""Programmatic API client for Taku (https://api.taku.cool/v1).

Features:
- Zero-hardcoding credentials: Auto-resolves from explicit arg -> env var -> 1Password unattended.
- Diagnostic-First: Built-in `diagnose()` health verification.
- Full CRUD operations for Customer Popups.
- Strict error handling with typed exceptions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Add scripts directory to path for local imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import space_catalog


class TakuError(Exception):
    """Base exception for Taku API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TakuAuthError(TakuError):
    """Authentication or authorization failure (HTTP 401/403)."""


class TakuNotFoundError(TakuError):
    """Resource not found (HTTP 404)."""


class TakuValidationError(TakuError):
    """Validation or unprocessable entity error (HTTP 422)."""


def resolve_api_key(explicit_key: Optional[str] = None) -> Tuple[str, str]:
    """Resolve Taku API Key with unattended priority.

    Priority:
    1. Explicit key argument
    2. Environment variable TAKU_API_KEY
    3. 1Password unattended service account (vault: Agent Automation, item: urgynm2bf7prlggservkvbwoji)

    Returns:
        (api_key, source_description)
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip(), "explicit_argument"

    env_key = os.environ.get("TAKU_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip(), "env:TAKU_API_KEY"

    # Attempt unattended 1Password resolution via bridge_router
    op_scripts_dir = Path.home() / ".agents/skills/1password/scripts"
    if op_scripts_dir.exists() and str(op_scripts_dir) not in sys.path:
        sys.path.insert(0, str(op_scripts_dir))

    try:
        import bridge_router

        # Query item in Agent Automation vault by UUID
        res = bridge_router.run_command(
            [
                "op",
                "item",
                "get",
                "urgynm2bf7prlggservkvbwoji",
                "--vault",
                "Agent Automation",
                "--format",
                "json",
            ],
            timeout=20,
        )
        if int(res.get("returncode", 1)) == 0 and res.get("stdout"):
            item_data = json.loads(res["stdout"])
            fields = {
                f.get("label") or f.get("id"): f.get("value")
                for f in item_data.get("fields", [])
            }
            cred = fields.get("credential")
            if cred and str(cred).strip():
                return str(cred).strip(), "1password:urgynm2bf7prlggservkvbwoji"
    except Exception:
        pass

    raise TakuAuthError(
        "Could not resolve Taku API key. Please pass --api-key, set TAKU_API_KEY, "
        "or verify 1Password unattended access to item urgynm2bf7prlggservkvbwoji."
    )


class TakuClient:
    """Taku API Client wrapping https://api.taku.cool/v1."""

    DEFAULT_BASE_URL = "https://api.taku.cool/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        resolved_key, source = resolve_api_key(api_key)
        self.api_key = resolved_key
        self.key_source = source
        self.base_url = (base_url or os.environ.get("TAKU_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "TakuOpsClient/1.0",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise TakuError(f"HTTP request failed: {e}") from e

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 204:
            return {"status": "success", "status_code": 204}
        elif resp.status_code in (401, 403):
            raise TakuAuthError(
                f"Authentication failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        elif resp.status_code == 404:
            raise TakuNotFoundError(
                f"Resource not found ({resp.status_code}): {path}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        elif resp.status_code == 422:
            raise TakuValidationError(
                f"Validation failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        else:
            raise TakuError(
                f"Taku API error ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    def list_popups(
        self,
        space_id: int | str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """List popups for a given space."""
        space = space_catalog.resolve_space(space_id)
        params = {"space_id": str(space.space_id), "page": page, "per_page": per_page}
        data = self._request("GET", "/customer/popups", params=params)
        return data if isinstance(data, dict) else {"collection": data}

    def get_popup(self, popup_id: int | str) -> Dict[str, Any]:
        """Retrieve full details of a specific popup."""
        return self._request("GET", f"/customer/popups/{popup_id}")

    def create_popup(
        self,
        space_id: int | str,
        popup_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new popup in the specified space."""
        space = space_catalog.resolve_space(space_id)
        payload = dict(popup_payload)
        payload["space_id"] = str(space.space_id)
        return self._request("POST", "/customer/popups", json_data=payload)

    def update_popup(
        self,
        popup_id: int | str,
        popup_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing popup."""
        return self._request("PUT", f"/customer/popups/{popup_id}", json_data=popup_payload)

    def delete_popup(self, popup_id: int | str) -> Dict[str, Any]:
        """Delete an existing popup."""
        return self._request("DELETE", f"/customer/popups/{popup_id}")

    @staticmethod
    def extract_title(popup: Dict[str, Any]) -> str:
        """Extract a readable title/name from a popup object."""
        if popup.get("name"):
            return str(popup["name"])
        for v in popup.get("variations", []):
            for b in v.get("blocks", []):
                if b.get("block_type") == "rich_text" and b.get("content"):
                    first_line = b["content"].split("\n")[0].strip().replace("\\", "")
                    if first_line:
                        return first_line
        if popup.get("snippet"):
            return str(popup["snippet"])
        return f"Popup #{popup.get('id', 'unknown')}"

    def diagnose(self) -> Dict[str, Any]:
        """Diagnostic-First verification of API health, credentials, and spaces."""
        key_masked = f"...{self.api_key[-4:]}" if len(self.api_key) >= 4 else "***"
        results: Dict[str, Any] = {
            "status": "healthy",
            "base_url": self.base_url,
            "credential_source": self.key_source,
            "api_key_suffix": key_masked,
            "spaces": {},
        }

        try:
            for space in space_catalog.list_known_spaces():
                try:
                    popups_res = self.list_popups(space_id=space.space_id, page=1, per_page=10)
                    popups_list = popups_res.get("collection") or popups_res.get("data") or []
                    results["spaces"][str(space.space_id)] = {
                        "name": space.name,
                        "slug": space.slug,
                        "project_key": space.project_key,
                        "dashboard_url": space.dashboard_url,
                        "status": "connected",
                        "popup_count": len(popups_list),
                        "popups": [
                            {
                                "id": p.get("id"),
                                "title": self.extract_title(p),
                                "display_type": p.get("display_type"),
                                "display_enabled": p.get("display_enabled"),
                                "views_count": p.get("views_count", 0),
                                "created_at": p.get("created_at"),
                            }
                            for p in popups_list
                        ],
                    }
                except Exception as space_err:
                    results["status"] = "degraded"
                    results["spaces"][str(space.space_id)] = {
                        "name": space.name,
                        "slug": space.slug,
                        "status": "error",
                        "error": str(space_err),
                    }
        except Exception as e:
            results["status"] = "unhealthy"
            results["error"] = str(e)

        return results
