"""
Safety & Escalation Classifier

Two-layer approach:
1. FAST RULE-BASED LAYER – keyword/pattern matching, zero latency, zero API cost.
   Catches obvious high-risk cases before even calling the LLM.
2. LLM SIGNAL – the LLM itself returns an `escalation_reason` field which is
   checked post-generation; used when the rule layer misses nuanced cases.

Escalation triggers (rule-based):
- Financial fraud / unauthorized transactions
- Account compromise / credential theft
- Legal demands / regulatory complaints
- Physical safety threats
- Prompt injection / jailbreak attempts
- Content requesting personal data manipulation
- Truly out-of-scope requests (medical, legal advice, etc.)

Reply triggers (rule-based):
- Billing FAQ (what is the price?)
- Password reset guidance
- Feature how-to questions
- General platform questions
"""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import Optional, Tuple

from models import SupportTicket


class EscalationReason(str, Enum):
    FRAUD = "fraud_or_unauthorized_transaction"
    ACCOUNT_COMPROMISE = "account_compromise_or_security_breach"
    LEGAL_REGULATORY = "legal_or_regulatory_complaint"
    SAFETY_THREAT = "physical_safety_threat"
    PROMPT_INJECTION = "prompt_injection_or_jailbreak_attempt"
    SENSITIVE_DATA = "sensitive_personal_data_request"
    COMPLEX_BILLING = "complex_billing_dispute"
    GDPR_REQUEST = "gdpr_or_privacy_rights_request"
    OUT_OF_SCOPE = "out_of_scope_request"
    LLM_FLAGGED = "llm_flagged_high_risk"


# ─────────────────────────────────────────────────────────────────
# Rule patterns (compiled regexes for speed)
# ─────────────────────────────────────────────────────────────────

_FRAUD_PATTERNS = re.compile(
    r"\b(fraud|fraudulent|unauthori[sz]ed\s+(?:charge|transaction|payment|access)"
    r"|stolen\s+card|card\s+stolen|identity\s+theft|scam(?:med)?|phishing"
    r"|chargeback|dispute(?:d)?\s+(?:charge|transaction)|money\s+stolen"
    r"|didn['t]+ authoriz[es]|not\s+me|wasn['\s]+t\s+me)\b",
    re.I,
)

_ACCOUNT_COMPROMISE_PATTERNS = re.compile(
    r"\b(account\s+(hacked|compromised|taken\s+over|hijacked)"
    r"|hack(ed|er|ing)|credential\s+(theft|stolen|leak)"
    r"|password\s+stolen|someone\s+else\s+(logged|accessed)"
    r"|unauthorized\s+login|breach|data\s+leak)\b",
    re.I,
)

_LEGAL_PATTERNS = re.compile(
    r"\b(lawsuit|sue|suing|legal\s+action|attorney|lawyer|court|litigation"
    r"|gdpr|ccpa|data\s+protection\s+request|right\s+to\s+(?:erasure|access)"
    r"|regulatory\s+complaint|file\s+a\s+complaint)\b",
    re.I,
)

_SAFETY_PATTERNS = re.compile(
    r"\b(threat|threatening|violence|harm|kill|hurt|emergency|danger)\b",
    re.I,
)

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)?\s*instructions"
    r"|disregard\s+(all\s+)?(previous|prior|above)?\s*instructions"
    r"|you\s+are\s+now\s+(a\s+)?(?:dan|jailbroken|unrestricted)"
    r"|act\s+as\s+(?:an?\s+)?(?:evil|uncensored|unfiltered)"
    r"|pretend\s+you\s+(?:have\s+no|don['\s]+t\s+have)\s+(rules|restrictions)"
    r"|\[?system\]?\s*prompt"
    r"|reveal\s+(your\s+)?(?:system\s+prompt|instructions)"
    r"|bypass\s+(safety|filter|restriction))",
    re.I,
)

_SENSITIVE_DATA_PATTERNS = re.compile(
    r"\b(social\s+security\s+number|ssn|passport\s+number|bank\s+account\s+number"
    r"|full\s+card\s+number|cvv|pin\s+number|credit\s+card\s+details"
    r"|date\s+of\s+birth\s+and)\b",
    re.I,
)

_BILLING_DISPUTE_PATTERNS = re.compile(
    r"\b(refund|charge(?:d|back)|billed|overcharged|double[\s-]charged"
    r"|deducted|deduction|invoice\s+error|payment\s+failed)\b",
    re.I,
)

# Topics clearly outside all three knowledge bases
_OOS_PATTERNS = re.compile(
    r"\b(medical\s+advice|diagnosis|prescri(?:ption|be)|legal\s+advice"
    r"|tax\s+advice|investment\s+advice|crypto\s+(?:exchange|wallet)"
    r"|recipe|cook(?:ing)?|weather|flight|hotel)\b",
    re.I,
)


# ─────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────


def check_escalation(
    ticket: SupportTicket,
) -> Tuple[bool, Optional[EscalationReason]]:
    """
    Fast rule-based escalation check.

    Returns:
        (should_escalate: bool, reason: Optional[EscalationReason])
    """
    combined = f"{ticket.issue} {ticket.subject}".strip()

    # Priority-ordered checks
    if _INJECTION_PATTERNS.search(combined):
        return True, EscalationReason.PROMPT_INJECTION

    if _FRAUD_PATTERNS.search(combined):
        return True, EscalationReason.FRAUD

    if _ACCOUNT_COMPROMISE_PATTERNS.search(combined):
        return True, EscalationReason.ACCOUNT_COMPROMISE

    if _LEGAL_PATTERNS.search(combined):
        return True, EscalationReason.LEGAL_REGULATORY

    if _SAFETY_PATTERNS.search(combined):
        return True, EscalationReason.SAFETY_THREAT

    if _SENSITIVE_DATA_PATTERNS.search(combined):
        return True, EscalationReason.SENSITIVE_DATA

    # Billing disputes are only escalated for Visa (financial risk)
    if ticket.company == "Visa" and _BILLING_DISPUTE_PATTERNS.search(combined):
        return True, EscalationReason.COMPLEX_BILLING

    return False, None


def is_invalid_ticket(ticket: SupportTicket) -> bool:
    """
    Detect tickets that have no actionable content
    (empty, pure noise, or test messages).
    """
    combined = f"{ticket.issue} {ticket.subject}".strip()
    if not combined:
        return True
    # Very short and random-looking
    if len(combined) < 5:
        return True
    # All numbers / symbols
    if re.fullmatch(r"[^a-zA-Z]+", combined):
        return True
    return False


def build_escalation_response(reason: EscalationReason) -> str:
    """Return a user-facing escalation message for a given reason."""
    messages = {
        EscalationReason.FRAUD: (
            "Your ticket has been escalated to our specialized fraud and security team. "
            "They will contact you within 1 business day. "
            "If this is an urgent matter, please also contact your card issuer directly."
        ),
        EscalationReason.ACCOUNT_COMPROMISE: (
            "Your ticket has been escalated to our account security team. "
            "Please change your password immediately and enable two-factor authentication "
            "while we investigate. Our team will reach out shortly."
        ),
        EscalationReason.LEGAL_REGULATORY: (
            "Your inquiry requires review by our legal and compliance team. "
            "We have escalated this ticket accordingly and someone will respond within "
            "3 business days."
        ),
        EscalationReason.SAFETY_THREAT: (
            "This matter has been flagged for immediate attention by our Trust & Safety team. "
            "If you or someone else is in immediate danger, please contact local emergency services."
        ),
        EscalationReason.PROMPT_INJECTION: (
            "This ticket contains content that cannot be processed automatically. "
            "It has been escalated to a human agent for review."
        ),
        EscalationReason.SENSITIVE_DATA: (
            "For your protection, we cannot process requests involving sensitive personal "
            "financial information through this channel. Please contact our secure support "
            "line. This ticket has been escalated to a human agent."
        ),
        EscalationReason.COMPLEX_BILLING: (
            "Billing disputes require verification of your account and transaction details. "
            "This ticket has been escalated to our billing specialist team who will contact "
            "you within 2 business days."
        ),
        EscalationReason.GDPR_REQUEST: (
            "Your data rights request has been received and escalated to our Privacy team. "
            "We will respond within the legally mandated timeframe (typically 30 days)."
        ),
        EscalationReason.OUT_OF_SCOPE: (
            "This request falls outside the scope of our support services. "
            "A human agent will review your ticket and advise on next steps."
        ),
        EscalationReason.LLM_FLAGGED: (
            "Your ticket has been escalated to a human support agent for further review. "
            "We will respond as soon as possible."
        ),
    }
    return messages.get(reason, messages[EscalationReason.LLM_FLAGGED])
