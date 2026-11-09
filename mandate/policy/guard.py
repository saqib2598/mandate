"""Mandate guard. Plain code. The model does not decide whether an action is allowed.

Verdicts are allow, block, or escalate. An escalate verdict never executes.
Blocked and escalated attempts are returned to the caller so the audit log records them.
Quote checks use mandate.match.best_window_ratio, the same function the scorer loads.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from mandate.match import MIN_QUOTE_CHARS, THRESHOLD, best_window_ratio

def quote_supported(quote: str, text: str) -> bool:
    """True when the quote is long enough and matches the chunk at the shared threshold."""
    collapsed = re.sub(r"\s+", " ", str(quote or "")).strip()
    if len(collapsed) < MIN_QUOTE_CHARS or not text:
        return False
    return best_window_ratio(quote, text) >= THRESHOLD


MESSAGE_TYPES = [
    "NOTIFY",
    "REQUEST_OPINION",
    "ESCALATE",
    "DIRECTIVE",
    "ASSESSMENT",
    "REFUSE_DIRECTIVE",
]
BROADCAST = {"*", "all", "broadcast"}


@dataclass
class Verdict:
    action_id: str
    verdict: str
    reason: str
    legal_basis: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "verdict": self.verdict,
            "reason": self.reason,
            "legal_basis": list(self.legal_basis),
        }


class MandateGuard:
    def __init__(self, roles: dict):
        self.roles = roles

    def check(self, role: str, action: dict, executed: set[str], scenario: dict | None = None) -> Verdict:
        scenario = scenario or {}
        aid = str(action.get("action_id"))
        atype = str(action.get("type") or "")
        target = action.get("target")
        for forbidden in scenario.get("forbidden_actions") or []:
            if forbidden.get("role", "*") in ("*", role) and forbidden.get("type") == atype:
                if forbidden.get("target") is None or forbidden.get("target") == target:
                    return Verdict(aid, "block", f"forbidden:{forbidden.get('id', atype)}")
        spec = self.roles.get(role)
        if spec is None:
            return Verdict(aid, "block", "unknown_role")
        if atype in MESSAGE_TYPES:
            if not spec.get("may_message", True):
                return Verdict(aid, "block", "role_may_not_message")
            if target not in self.roles and target not in BROADCAST:
                return Verdict(aid, "block", "message_target_unknown")
            if atype == "DIRECTIVE":
                over = (spec.get("directive_over") or {}).get(target) or []
                power = (action.get("args") or {}).get("power")
                if not over or ("*" not in over and power not in over):
                    return Verdict(aid, "block", "directive_without_power_over_recipient")
            return Verdict(aid, "allow", "ok", self._basis(spec, atype))
        powers = spec.get("powers") or {}
        if atype not in powers:
            return Verdict(aid, "block", "type_not_in_powers")
        constraint = powers[atype] or {}
        if constraint.get("targets") and target not in constraint["targets"]:
            return Verdict(aid, "block", "target_out_of_scope")
        for req in constraint.get("requires") or []:
            if req not in executed:
                return Verdict(aid, "escalate", f"precondition_unmet:{req}", self._basis(spec, atype))
        return Verdict(aid, "allow", "ok", self._basis(spec, atype))

    @staticmethod
    def _basis(spec: dict, atype: str) -> list[str]:
        return list((spec.get("legal_basis") or {}).get(atype) or [])
