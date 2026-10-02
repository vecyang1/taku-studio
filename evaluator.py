#!/usr/bin/env python3
"""Rule evaluation engine for Taku customer popups and widgets.

Implements the UI Observability Mandate:
"凡称可配置，必须可检查；凡有业务规则，必须能找到对账依据...
诊断器应调用真实执行逻辑，不能再复制一套'看起来正确'的算法。"

Evaluates targeting rules:
- Enabled state check (display_enabled)
- Page URL matching (eq, startsWith, wildcard, contains, notEq, notStartsWith, notWildcard, notContains, regex, endsWith)
- Condition combinators ('all' / AND vs 'any' / OR)
- Retrigger restrictions (max_triggers, interval_seconds)
- Delay settings (display_delay)
- Device targeting (desktop, mobile, tablet)
- Exit intent triggers
- Location targeting
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConditionResult:
    condition_id: str
    condition_type: str
    operator: str
    target_value: str
    actual_value: str
    matched: bool
    explanation: str


@dataclass
class EvaluationReport:
    popup_id: str
    display_enabled: bool
    display_type: str
    will_trigger: bool
    status_code: str  # "TRIGGERED", "SUPPRESSED_PAUSED", "RULES_NOT_MATCHED", "RETRIGGER_BLOCKED"
    summary: str
    delay_ms: int
    condition_match_mode: str  # "all" or "any"
    conditions_evaluated: List[ConditionResult] = field(default_factory=list)
    retrigger_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "popup_id": self.popup_id,
            "display_enabled": self.display_enabled,
            "display_type": self.display_type,
            "will_trigger": self.will_trigger,
            "status_code": self.status_code,
            "summary": self.summary,
            "delay_ms": self.delay_ms,
            "condition_match_mode": self.condition_match_mode,
            "conditions_evaluated": [
                {
                    "condition_id": c.condition_id,
                    "condition_type": c.condition_type,
                    "operator": c.operator,
                    "target_value": c.target_value,
                    "actual_value": c.actual_value,
                    "matched": c.matched,
                    "explanation": c.explanation,
                }
                for c in self.conditions_evaluated
            ],
            "retrigger_info": self.retrigger_info,
        }


def _match_wildcard(actual: str, pattern: str) -> bool:
    """Smart wildcard matching supporting glob wildcards (*, ?) and URL prefix normalization."""
    if not pattern:
        return True
    act = (actual or "").strip()
    pat = pattern.strip()

    # Direct exact match
    if act == pat:
        return True

    # Normalize protocol differences (http:// vs https://)
    act_no_proto = re.sub(r"^https?://", "", act, flags=re.IGNORECASE)
    pat_no_proto = re.sub(r"^https?://", "", pat, flags=re.IGNORECASE)

    if act_no_proto == pat_no_proto:
        return True

    # If pattern contains glob wildcards (*, ?)
    if "*" in pat or "?" in pat:
        if fnmatch.fnmatch(act, pat):
            return True
        if fnmatch.fnmatch(act_no_proto, pat_no_proto):
            return True
        return False

    # When no glob characters are provided, Taku wildcard functions as prefix/base match
    if act.startswith(pat) or act_no_proto.startswith(pat_no_proto):
        return True

    return False


def _match_operator(actual: str, operator: str, expected: str) -> bool:
    """Evaluate string condition across all Taku OpenAPI supported operators."""
    op = (operator or "").strip().lower()
    act = actual or ""
    exp = expected or ""

    if op in ("eq", "equals", "=="):
        return act == exp
    elif op in ("noteq", "not_equals", "!="):
        return act != exp
    elif op in ("startswith", "starts_with"):
        return act.startswith(exp)
    elif op in ("notstartswith", "not_starts_with"):
        return not act.startswith(exp)
    elif op in ("endswith", "ends_with"):
        return act.endswith(exp)
    elif op in ("notendswith", "not_ends_with"):
        return not act.endswith(exp)
    elif op in ("contains", "contain"):
        return exp in act
    elif op in ("notcontains", "not_contains"):
        return exp not in act
    elif op in ("wildcard",):
        return _match_wildcard(act, exp)
    elif op in ("notwildcard", "not_wildcard"):
        return not _match_wildcard(act, exp)
    elif op in ("regex", "matches"):
        try:
            return bool(re.search(exp, act))
        except re.error:
            return False
    return False


def evaluate_popup(
    popup: Dict[str, Any],
    url: str,
    device: str = "desktop",
    past_triggers_count: int = 0,
    seconds_since_last_trigger: Optional[float] = None,
    ignore_paused: bool = False,
    exit_intent: bool = False,
    location: Optional[str] = None,
) -> EvaluationReport:
    """Evaluate whether a Taku popup triggers for a given visitor context.

    Args:
        popup: Authoritative popup JSON retrieved from Taku API.
        url: Current visitor URL to evaluate against trigger conditions.
        device: Visitor device ('desktop', 'mobile', or 'tablet').
        past_triggers_count: How many times this user has triggered this popup in the current session/cookie.
        seconds_since_last_trigger: Elapsed seconds since the user last saw this popup.
        ignore_paused: If True, evaluates targeting rules even if display_enabled is False.
        exit_intent: Whether the visitor has triggered an exit intent gesture (e.g. mouse out).
        location: Optional visitor geographic country code or region (e.g. 'US', 'JP').
    """
    popup_id = str(popup.get("id", "unknown"))
    display_enabled = bool(popup.get("display_enabled", False))
    display_type = str(popup.get("display_type", "modal"))

    # 1. Base active check
    if not display_enabled and not ignore_paused:
        return EvaluationReport(
            popup_id=popup_id,
            display_enabled=False,
            display_type=display_type,
            will_trigger=False,
            status_code="SUPPRESSED_PAUSED",
            summary=f"Popup #{popup_id} is currently PAUSED (display_enabled=false).",
            delay_ms=0,
            condition_match_mode="none",
        )

    # 2. Extract configuration
    trigger_conf = popup.get("trigger_configuration") or {}
    config = popup.get("configuration") or {}

    delay_ms = int(trigger_conf.get("display_delay") or config.get("display_delay") or 0)

    # Extract conditions & match mode
    conditions = (
        trigger_conf.get("conditions")
        or config.get("conditions")
        or []
    )
    match_mode = (
        trigger_conf.get("conditions_match")
        or config.get("conditions_match")
        or "all"
    ).lower()

    # Retrigger rules
    retrigger = trigger_conf.get("retrigger") or {}
    retrigger_info = None
    if retrigger:
        max_triggers = retrigger.get("max_triggers")
        interval_seconds = retrigger.get("interval_seconds")
        retrigger_info = {
            "max_triggers": max_triggers,
            "interval_seconds": interval_seconds,
            "past_triggers_count": past_triggers_count,
            "seconds_since_last": seconds_since_last_trigger,
        }

        if max_triggers is not None and past_triggers_count >= int(max_triggers):
            return EvaluationReport(
                popup_id=popup_id,
                display_enabled=True,
                display_type=display_type,
                will_trigger=False,
                status_code="RETRIGGER_BLOCKED",
                summary=(
                    f"Retrigger limit exceeded: maximum allowed is {max_triggers}, "
                    f"user has seen it {past_triggers_count} times."
                ),
                delay_ms=delay_ms,
                condition_match_mode=match_mode,
                retrigger_info=retrigger_info,
            )

        if interval_seconds is not None and seconds_since_last_trigger is not None:
            if seconds_since_last_trigger < float(interval_seconds):
                return EvaluationReport(
                    popup_id=popup_id,
                    display_enabled=True,
                    display_type=display_type,
                    will_trigger=False,
                    status_code="RETRIGGER_BLOCKED",
                    summary=(
                        f"Retrigger cooldown active: requires {interval_seconds}s interval, "
                        f"only {int(seconds_since_last_trigger)}s elapsed."
                    ),
                    delay_ms=delay_ms,
                    condition_match_mode=match_mode,
                    retrigger_info=retrigger_info,
                )

    # 3. Evaluate each condition
    evaluated: List[ConditionResult] = []
    if not conditions:
        # No conditions specified -> matches any page by default
        return EvaluationReport(
            popup_id=popup_id,
            display_enabled=True,
            display_type=display_type,
            will_trigger=True,
            status_code="TRIGGERED",
            summary="All pages match (no targeting conditions defined).",
            delay_ms=delay_ms,
            condition_match_mode=match_mode,
            retrigger_info=retrigger_info,
        )

    for i, cond in enumerate(conditions):
        c_id = str(cond.get("id", f"cond-{i}"))
        c_type = cond.get("type", "page_url")
        c_op = cond.get("operator", "eq")
        c_val = str(cond.get("value", ""))

        actual_val = ""
        matched = False
        explanation = ""

        if c_type == "page_url":
            actual_val = url
            matched = _match_operator(url, c_op, c_val)
            explanation = (
                f"Page URL '{url}' {c_op} '{c_val}' -> {'MATCH' if matched else 'NO MATCH'}"
            )
        elif c_type == "device":
            # OpenAPI schema supports "device": "mobile"|"desktop" or "value": "mobile"
            target_device = (cond.get("device") or cond.get("value") or "").strip().lower()
            actual_val = (device or "desktop").strip().lower()
            if c_op in ("noteq", "not_equals", "!="):
                matched = actual_val != target_device
                explanation = f"Device '{actual_val}' notEq '{target_device}' -> {'MATCH' if matched else 'NO MATCH'}"
            else:
                matched = actual_val == target_device
                explanation = f"Device '{actual_val}' matches target '{target_device}' -> {'MATCH' if matched else 'NO MATCH'}"
        elif c_type == "exit_intent":
            actual_val = f"exit_intent={exit_intent}"
            matched = bool(exit_intent)
            explanation = (
                "Exit intent detected"
                if matched
                else "Exit intent condition required, but visitor did not trigger exit intent"
            )
        elif c_type == "location":
            if location is not None:
                actual_val = location
                matched = _match_operator(location, c_op, c_val)
                explanation = (
                    f"Visitor location '{location}' {c_op} '{c_val}' -> {'MATCH' if matched else 'NO MATCH'}"
                )
            else:
                actual_val = "unspecified"
                matched = True
                explanation = f"Location condition '{c_op} {c_val}' unconstrained in simulator (assumed pass)"
        else:
            actual_val = f"custom_{c_type}"
            matched = True
            explanation = f"Condition type '{c_type}' assumed passing"

        evaluated.append(
            ConditionResult(
                condition_id=c_id,
                condition_type=c_type,
                operator=c_op,
                target_value=c_val or cond.get("device", ""),
                actual_value=actual_val,
                matched=matched,
                explanation=explanation,
            )
        )

    # Combine results based on match_mode
    if match_mode == "any":
        overall_match = any(c.matched for c in evaluated)
    else:  # "all"
        overall_match = all(c.matched for c in evaluated)

    if overall_match:
        status_code = "TRIGGERED"
        summary = (
            f"All required conditions satisfied ({match_mode.upper()} match). "
            f"Will trigger after {delay_ms}ms delay."
        )
    else:
        status_code = "RULES_NOT_MATCHED"
        unmatched = [c.explanation for c in evaluated if not c.matched]
        summary = (
            f"Targeting rules did not match ({match_mode.upper()} mode). "
            f"Failing checks: {'; '.join(unmatched[:2])}"
        )

    return EvaluationReport(
        popup_id=popup_id,
        display_enabled=True,
        display_type=display_type,
        will_trigger=overall_match,
        status_code=status_code,
        summary=summary,
        delay_ms=delay_ms,
        condition_match_mode=match_mode,
        conditions_evaluated=evaluated,
        retrigger_info=retrigger_info,
    )
