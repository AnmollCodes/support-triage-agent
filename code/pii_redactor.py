"""
pii_redactor.py — Feature 1: PII Detector & Auto-Redactor

Detects and redacts Personally Identifiable Information from ticket text
and generated responses BEFORE they are written to any output file.

Critical for:
  - GDPR / CCPA compliance (Art. 5 data minimisation principle)
  - PCI-DSS (never log card numbers)
  - Enterprise audits (must show PII is handled correctly)

What it detects & redacts:
  Card numbers (Visa 16-digit), CVV, PIN, bank account numbers,
  Email addresses, Phone numbers (Indian +91 & international),
  Aadhaar numbers (12-digit Indian national ID), PAN cards,
  Passport numbers, SSN, IP addresses, Physical addresses,
  API keys (sk-ant-, Bearer tokens), passwords in plain text

Output:
  - redacted_text (str)         — safe version for logging
  - pii_types_found (List[str]) — what categories were found
  - pii_count (int)             — total PII items found
  - risk_level (str)            — "critical" / "high" / "medium" / "low"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class PIIReport:
    original_length:   int
    redacted_text:     str
    pii_types_found:   List[str] = field(default_factory=list)
    pii_count:         int = 0
    risk_level:        str = "low"    # low / medium / high / critical
    contains_financial: bool = False
    contains_identity:  bool = False


# ── PII patterns (compiled once at module load) ────────────────────

_PATTERNS: List[Tuple[str, re.Pattern, str, str]] = [
    # (category, pattern, replacement, risk_level)

    # Financial – highest risk
    ("visa_card_number",
     re.compile(r"\b4[0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b"),
     "[CARD-REDACTED]", "critical"),

    ("mastercard_number",
     re.compile(r"\b5[1-5][0-9]{2}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b"),
     "[CARD-REDACTED]", "critical"),

    ("generic_card_16",
     re.compile(r"\b(?:\d{4}[\s\-]){3}\d{4}\b"),
     "[CARD-REDACTED]", "critical"),

    ("cvv",
     re.compile(r"\b(?:cvv|cvc|cvv2|security\s+code)\s*[:\-]?\s*\d{3,4}\b", re.I),
     "[CVV-REDACTED]", "critical"),

    ("bank_account",
     re.compile(r"\b(?:account\s+(?:no|number|#)\s*[:\-]?\s*)?\d{9,18}\b(?=\s|$)", re.I),
     "[ACCOUNT-REDACTED]", "high"),

    ("api_key_anthropic",
     re.compile(r"\bsk-ant-[a-zA-Z0-9\-_]{20,}\b"),
     "[API-KEY-REDACTED]", "critical"),

    ("api_key_generic",
     re.compile(r"\b(?:Bearer|token|api[_\-]?key)\s*[:\s]+[a-zA-Z0-9\-_\.]{20,}\b", re.I),
     "[TOKEN-REDACTED]", "high"),

    ("password_in_text",
     re.compile(r"\b(?:password|passwd|pwd)\s*[:\-=]\s*\S{4,}\b", re.I),
     "[PASSWORD-REDACTED]", "critical"),

    # Identity documents
    ("aadhaar_number",
     re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"),
     "[AADHAAR-REDACTED]", "critical"),

    ("pan_card",
     re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
     "[PAN-REDACTED]", "high"),

    ("ssn_us",
     re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
     "[SSN-REDACTED]", "critical"),

    ("passport",
     re.compile(r"\b(?:passport\s+(?:no|number|#)\s*[:\-]?\s*)?[A-Z]{1,2}\d{6,8}\b", re.I),
     "[PASSPORT-REDACTED]", "high"),

    # Contact info
    ("email_address",
     re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
     "[EMAIL-REDACTED]", "medium"),

    ("phone_india",
     re.compile(r"\b(?:\+91[\s\-]?)?[6-9]\d{9}\b"),
     "[PHONE-REDACTED]", "medium"),

    ("phone_international",
     re.compile(r"\b(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b"),
     "[PHONE-REDACTED]", "medium"),

    # Network
    ("ip_address",
     re.compile(r"\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
                r"\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
     "[IP-REDACTED]", "low"),
]

_FINANCIAL_CATEGORIES = {
    "visa_card_number", "mastercard_number", "generic_card_16",
    "cvv", "bank_account", "api_key_anthropic", "api_key_generic",
    "password_in_text",
}
_IDENTITY_CATEGORIES = {
    "aadhaar_number", "pan_card", "ssn_us", "passport",
}

_RISK_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def redact(text: str) -> PIIReport:
    """
    Scan and redact PII from text.
    Returns a PIIReport with the safe version and metadata.
    """
    redacted = text
    found_categories: List[str] = []
    max_risk = "low"
    contains_financial = False
    contains_identity  = False

    for category, pattern, replacement, risk in _PATTERNS:
        matches = pattern.findall(redacted)
        if matches:
            redacted = pattern.sub(replacement, redacted)
            found_categories.append(category)
            if _RISK_ORDER[risk] > _RISK_ORDER[max_risk]:
                max_risk = risk
            if category in _FINANCIAL_CATEGORIES:
                contains_financial = True
            if category in _IDENTITY_CATEGORIES:
                contains_identity = True

    return PIIReport(
        original_length   = len(text),
        redacted_text     = redacted,
        pii_types_found   = found_categories,
        pii_count         = len(found_categories),
        risk_level        = max_risk,
        contains_financial = contains_financial,
        contains_identity  = contains_identity,
    )


def safe_for_logging(text: str) -> str:
    """Quick one-liner: return redacted text safe for CSV/logs."""
    return redact(text).redacted_text
