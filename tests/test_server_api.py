#!/usr/bin/env python3
"""Unit and contract tests for Taku Studio server API endpoints using AioHTTPTestCase."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

STUDIO_DIR = Path(__file__).resolve().parent.parent
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))

import server


class TestServerAPI(AioHTTPTestCase):
    async def get_application(self):
        return server.create_app()

    async def test_health_endpoint(self):
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "Taku Studio"

    async def test_spaces_endpoint_with_primary_domains(self):
        resp = await self.client.request("GET", "/api/spaces")
        assert resp.status == 200
        data = await resp.json()
        assert "spaces" in data
        assert len(data["spaces"]) >= 1

        first_space = data["spaces"][0]
        assert "space_id" in first_space
        assert "primary_domain" in first_space
        assert "project_key" in first_space
        assert "embed_snippet" in first_space

    async def test_snippet_endpoint(self):
        # Resolve dynamic first space ID from server
        spaces_resp = await self.client.request("GET", "/api/spaces")
        spaces_data = await spaces_resp.json()
        target_space = spaces_data["spaces"][0]
        sid = target_space["space_id"]

        resp = await self.client.request("GET", f"/api/snippet/{sid}?popup_id=1001")
        assert resp.status == 200
        data = await resp.json()
        assert data["space_id"] == sid
        assert target_space["project_key"] in data["embed_snippet"]
        assert "https://ui.taku.cool/feed/" in data["feed_url"]

    async def test_simulate_endpoint_wildcard_and_exit_intent(self):
        payload = {
            "popup": {
                "id": "1002",
                "display_enabled": True,
                "display_type": "banner",
                "trigger_configuration": {
                    "conditions": [
                        {"type": "page_url", "operator": "wildcard", "value": "http://store.example.com/"},
                        {"type": "exit_intent"}
                    ],
                    "conditions_match": "all"
                }
            },
            "url": "https://store.example.com/product/123",
            "device": "desktop",
            "exit_intent": True
        }
        resp = await self.client.request("POST", "/api/simulate", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["will_trigger"] is True
        assert data["status_code"] == "TRIGGERED"
        assert data["display_type"] == "banner"

        # Non-matching URL
        payload["url"] = "https://other.com/page"
        resp_fail = await self.client.request("POST", "/api/simulate", json=payload)
        assert resp_fail.status == 200
        data_fail = await resp_fail.json()
        assert data_fail["will_trigger"] is False
        assert data_fail["status_code"] == "RULES_NOT_MATCHED"

    async def test_toggle_popup_unidirectional_contract(self):
        with patch("server.get_taku_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.update_popup.return_value = {"status": "success"}
            mock_client.get_popup.return_value = {
                "id": "1001",
                "space_id": "1001",
                "display_enabled": True,
                "name": "Test Popup"
            }
            mock_client.extract_title.return_value = "Test Popup"
            mock_get_client.return_value = mock_client

            resp = await self.client.request("POST", "/api/popups/1001/toggle", json={"display_enabled": True})
            assert resp.status == 200
            data = await resp.json()
            assert data["display_enabled"] is True
            # Verify write occurred, followed by re-fetch
            mock_client.update_popup.assert_called_once_with("1001", {"display_enabled": True})
            mock_client.get_popup.assert_called_once_with("1001")

    async def test_create_popup_unidirectional_contract(self):
        with patch("server.get_taku_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.create_popup.return_value = {"id": "9999", "status": "created"}
            mock_client.get_popup.return_value = {
                "id": "9999",
                "space_id": "1001",
                "name": "New Promo Campaign",
                "display_enabled": True,
                "display_type": "modal"
            }
            mock_client.extract_title.return_value = "New Promo Campaign"
            mock_get_client.return_value = mock_client

            create_payload = {
                "name": "New Promo Campaign",
                "display_type": "modal"
            }
            resp = await self.client.request("POST", "/api/spaces/1001/popups", json=create_payload)
            assert resp.status == 201
            data = await resp.json()
            assert data["id"] == "9999"
            assert data["extracted_title"] == "New Promo Campaign"
            mock_client.create_popup.assert_called_once_with("1001", create_payload)
            mock_client.get_popup.assert_called_once_with("9999")

    async def test_delete_popup_endpoint(self):
        with patch("server.get_taku_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.delete_popup.return_value = {"status": "success", "status_code": 204}
            mock_get_client.return_value = mock_client

            resp = await self.client.request("DELETE", "/api/popups/9999")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"
            mock_client.delete_popup.assert_called_once_with("9999")
