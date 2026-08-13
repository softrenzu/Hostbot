from enum import Enum
from dataclasses import dataclass


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyResult:
    decision: Decision
    reason: str


class PolicyEngine:
    """Server-side authorization rules for guest-facing operations."""

    def decide(self, action: str, *, stay_verified: bool = False) -> PolicyResult:
        if action in {"read_public_property", "ask_public_question"}:
            return PolicyResult(Decision.ALLOW, "public action")
        if action in {"read_private_property", "create_guest_ticket"}:
            return PolicyResult(
                Decision.ALLOW if stay_verified else Decision.DENY,
                "verified stay required",
            )
        return PolicyResult(Decision.DENY, "unknown action")


policy = PolicyEngine()
