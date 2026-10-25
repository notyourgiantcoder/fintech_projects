"""Guardrails around every agent run.

question --> policy check --> PII redaction --> injection scan --> agents
agents   --> grounding check (figures traced to tool results, no promised returns)
         --> disclaimer --> answer + check report shown to the user
"""

from .grounding import DISCLAIMER, GroundingReport, check_answer
from .injection import InjectionVerdict, scan, spotlight
from .pii import Redaction, luhn_valid, redact, verhoeff_valid
from .policy import PolicyDecision, check_request

__all__ = [
    "DISCLAIMER",
    "GroundingReport",
    "InjectionVerdict",
    "PolicyDecision",
    "Redaction",
    "check_answer",
    "check_request",
    "luhn_valid",
    "redact",
    "scan",
    "spotlight",
    "verhoeff_valid",
]
