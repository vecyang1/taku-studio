#!/usr/bin/env python3
"""Comprehensive unit tests for Taku Studio trigger and audience evaluator.

Verifies:
- All 8 OpenAPI supported operators (eq, startsWith, wildcard, contains, notEq, notStartsWith, notWildcard, notContains)
- Wildcard edge cases: glob matching (*, ?), prefix matching, protocol normalization (http vs https)
- Realistic campaign configurations (Modal, Announcement Banner, Multi-condition any/all)
- Device targeting with OpenAPI schema property 'device'
- Exit intent trigger conditions
- Location targeting conditions
- Retrigger limits and interval cooldown logic
"""

import sys
from pathlib import Path
import pytest

STUDIO_DIR = Path(__file__).resolve().parent.parent
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))

from evaluator import evaluate_popup, _match_operator, _match_wildcard


class TestEvaluatorOperators:
    def test_equality_operators(self):
        assert _match_operator("https://example.com/test", "eq", "https://example.com/test")
        assert not _match_operator("https://example.com/test", "eq", "https://example.com/other")

        assert _match_operator("desktop", "notEq", "mobile")
        assert not _match_operator("mobile", "notEq", "mobile")

    def test_prefix_operators(self):
        assert _match_operator("https://example.com/blog/1", "startsWith", "https://example.com/blog")
        assert not _match_operator("https://example.com/store", "startsWith", "https://example.com/blog")

        assert _match_operator("https://example.com/store", "notStartsWith", "https://example.com/blog")
        assert not _match_operator("https://example.com/blog/1", "notStartsWith", "https://example.com/blog")

    def test_contains_operators(self):
        assert _match_operator("https://example.com/product/123", "contains", "product")
        assert not _match_operator("https://example.com/blog/123", "contains", "product")

        assert _match_operator("https://example.com/blog/123", "notContains", "product")
        assert not _match_operator("https://example.com/product/123", "notContains", "product")

    def test_wildcard_operator_logic(self):
        # Exact and prefix matching without glob characters
        assert _match_wildcard("http://store.example.com/", "http://store.example.com/")
        assert _match_wildcard("http://store.example.com/shop", "http://store.example.com/")
        
        # Protocol normalization (https visiting http rule)
        assert _match_wildcard("https://store.example.com/shop", "http://store.example.com/")
        assert _match_wildcard("http://store.example.com/shop", "https://store.example.com/")

        # Glob wildcard matching
        assert _match_wildcard("https://example.com/products/summer-shoe", "https://example.com/products/*")
        assert not _match_wildcard("https://example.com/about", "https://example.com/products/*")

        # notWildcard
        assert _match_operator("https://other.com/test", "notWildcard", "https://example.com/*")
        assert not _match_operator("https://example.com/test", "notWildcard", "https://example.com/*")

    def test_regex_operator(self):
        assert _match_operator("https://example.com/items/999", "regex", r"/items/\d+")
        assert not _match_operator("https://example.com/items/abc", "regex", r"/items/\d+")


class TestPopupEvaluations:
    def test_paused_popup_suppressed(self):
        popup = {
            "id": "1001",
            "display_enabled": False,
            "configuration": {
                "conditions": [
                    {"type": "page_url", "operator": "startsWith", "value": "https://app.example.com/"}
                ]
            }
        }
        res = evaluate_popup(popup, "https://app.example.com/prompt")
        assert not res.will_trigger
        assert res.status_code == "SUPPRESSED_PAUSED"

    def test_paused_popup_with_ignore_paused(self):
        popup = {
            "id": "1001",
            "display_enabled": False,
            "configuration": {
                "conditions": [
                    {"type": "page_url", "operator": "startsWith", "value": "https://app.example.com/"}
                ]
            }
        }
        res = evaluate_popup(popup, "https://app.example.com/prompt", ignore_paused=True)
        assert res.will_trigger
        assert res.status_code == "TRIGGERED"

    def test_popup_matches_url(self):
        popup = {
            "id": "1001",
            "display_enabled": True,
            "trigger_configuration": {"display_delay": 7000},
            "configuration": {
                "conditions": [
                    {"type": "page_url", "operator": "startsWith", "value": "https://app.example.com/"}
                ],
                "conditions_match": "all"
            }
        }
        res = evaluate_popup(popup, "https://app.example.com/prompt")
        assert res.will_trigger
        assert res.status_code == "TRIGGERED"
        assert res.delay_ms == 7000
        assert len(res.conditions_evaluated) == 1
        assert res.conditions_evaluated[0].matched

        res_fail = evaluate_popup(popup, "https://different-domain.com/page")
        assert not res_fail.will_trigger
        assert res_fail.status_code == "RULES_NOT_MATCHED"

    def test_wildcard_root_url_rule(self):
        popup = {
            "id": "1002",
            "display_enabled": True,
            "display_type": "banner",
            "trigger_configuration": {
                "conditions": [
                    {
                        "type": "page_url",
                        "value": "http://store.example.com/",
                        "operator": "wildcard"
                    }
                ],
                "display_delay": 0,
                "conditions_match": "all"
            }
        }
        # Exact match
        r1 = evaluate_popup(popup, "http://store.example.com/")
        assert r1.will_trigger
        assert r1.status_code == "TRIGGERED"
        assert r1.display_type == "banner"

        # Subpath match
        r2 = evaluate_popup(popup, "https://store.example.com/product/custom-item")
        assert r2.will_trigger
        assert r2.status_code == "TRIGGERED"

        # Non-matching domain
        r3 = evaluate_popup(popup, "https://unrelated-domain.com/product")
        assert not r3.will_trigger
        assert r3.status_code == "RULES_NOT_MATCHED"

    def test_multi_conditions_any_match(self):
        popup = {
            "id": "1003",
            "display_enabled": True,
            "trigger_configuration": {
                "retrigger": {"max_triggers": 1, "interval_seconds": 300},
                "conditions": [
                    {"type": "page_url", "value": "http://store.example.com/", "operator": "eq"},
                    {"type": "page_url", "value": "product", "operator": "contains"},
                    {"type": "page_url", "value": "blog", "operator": "contains"},
                    {"type": "page_url", "value": "post", "operator": "contains"}
                ],
                "display_delay": 7000,
                "conditions_match": "any"
            }
        }
        res1 = evaluate_popup(popup, "http://store.example.com/")
        assert res1.will_trigger
        assert res1.status_code == "TRIGGERED"

        res2 = evaluate_popup(popup, "http://store.example.com/product/sample")
        assert res2.will_trigger
        assert res2.status_code == "TRIGGERED"

        res3 = evaluate_popup(popup, "http://store.example.com/about-us")
        assert not res3.will_trigger
        assert res3.status_code == "RULES_NOT_MATCHED"

        # Retrigger limit exceeded
        res4 = evaluate_popup(popup, "http://store.example.com/product/item", past_triggers_count=1)
        assert not res4.will_trigger
        assert res4.status_code == "RETRIGGER_BLOCKED"

        # Retrigger cooldown active
        res5 = evaluate_popup(
            popup,
            "http://store.example.com/product/item",
            past_triggers_count=0,
            seconds_since_last_trigger=120.0
        )
        assert not res5.will_trigger
        assert res5.status_code == "RETRIGGER_BLOCKED"

    def test_device_condition_schema(self):
        popup = {
            "id": "5001",
            "display_enabled": True,
            "trigger_configuration": {
                "conditions": [
                    {"type": "device", "device": "mobile"}
                ],
                "conditions_match": "all"
            }
        }
        r_mobile = evaluate_popup(popup, "https://example.com", device="mobile")
        assert r_mobile.will_trigger
        assert r_mobile.status_code == "TRIGGERED"

        r_desktop = evaluate_popup(popup, "https://example.com", device="desktop")
        assert not r_desktop.will_trigger
        assert r_desktop.status_code == "RULES_NOT_MATCHED"

    def test_exit_intent_condition(self):
        popup = {
            "id": "5002",
            "display_enabled": True,
            "trigger_configuration": {
                "conditions": [
                    {"type": "exit_intent"}
                ],
                "conditions_match": "all"
            }
        }
        r_exit = evaluate_popup(popup, "https://example.com", exit_intent=True)
        assert r_exit.will_trigger
        assert r_exit.status_code == "TRIGGERED"

        r_no_exit = evaluate_popup(popup, "https://example.com", exit_intent=False)
        assert not r_no_exit.will_trigger
        assert r_no_exit.status_code == "RULES_NOT_MATCHED"

    def test_location_condition(self):
        popup = {
            "id": "5003",
            "display_enabled": True,
            "trigger_configuration": {
                "conditions": [
                    {"type": "location", "operator": "eq", "value": "US"}
                ],
                "conditions_match": "all"
            }
        }
        r_us = evaluate_popup(popup, "https://example.com", location="US")
        assert r_us.will_trigger
        assert r_us.status_code == "TRIGGERED"

        r_uk = evaluate_popup(popup, "https://example.com", location="GB")
        assert not r_uk.will_trigger
        assert r_uk.status_code == "RULES_NOT_MATCHED"
