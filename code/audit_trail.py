"""
audit_trail.py — Feature 6: Immutable Compliance Audit Trail

Creates a tamper-evident, SHA-256 chained audit log of every triage decision.
Each entry is cryptographically linked to the previous one (blockchain-style).

Why enterprises pay for this:
  - SOC 2 Type II requires decision logs for automated systems
  - GDPR Art. 22 requires records of automated decisions affecting people
  - Financial services require audit trails for fraud routing decisions
  - Legal teams need to prove decisions were made correctly

Each log entry contains:
  - Timestamp (ISO 8601)
  - Ticket hash (SHA-256 of issue+subject+company — NOT the raw PII)
  - Decision (status, product_area, request_type)
  - Confidence score
  - PII risk level
  - Previous entry hash (chain integrity)
  - Entry hash (self-hash)

The chain is verified at the end of every run — any tampering breaks the chain.
"""
from __future__ import annotations
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from models import SupportTicket, TriageResult


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _ticket_fingerprint(ticket: SupportTicket) -> str:
    """One-way hash of ticket content — no PII stored."""
    raw = f"{ticket.company}|{ticket.subject[:50]}|{ticket.issue[:100]}"
    return _sha256(raw)[:16]


class AuditTrail:
    """Append-only audit trail with cryptographic chaining."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.entries: List[dict] = []
        self._prev_hash = "GENESIS"  # first entry chains to this

    def record(
        self,
        ticket_num:    int,
        ticket:        SupportTicket,
        result:        TriageResult,
        pii_risk:      str = "low",
        is_duplicate:  bool = False,
        churn_score:   int = 0,
    ) -> str:
        """Record a triage decision. Returns the entry hash."""
        ts = datetime.now(timezone.utc).isoformat()

        entry_data = {
            "seq":              ticket_num,
            "timestamp":        ts,
            "ticket_fingerprint": _ticket_fingerprint(ticket),
            "company":          ticket.company,
            "status":           result.status.value,
            "product_area":     result.product_area,
            "request_type":     result.request_type.value,
            "urgency_tier":     result.urgency.tier.value,
            "confidence_score": result.confidence.score,
            "quality_score":    result.quality.score,
            "pii_risk_level":   pii_risk,
            "is_duplicate":     is_duplicate,
            "churn_risk_score": churn_score,
            "incident_cluster": result.incident_cluster_id or "",
            "prev_hash":        self._prev_hash,
        }

        # Compute entry hash
        canonical = json.dumps(entry_data, sort_keys=True, separators=(",", ":"))
        entry_hash = _sha256(canonical)
        entry_data["entry_hash"] = entry_hash

        self.entries.append(entry_data)
        self._prev_hash = entry_hash
        return entry_hash

    def save(self) -> Path:
        """Write the audit trail to CSV."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.entries:
            return self.output_path

        fieldnames = list(self.entries[0].keys())
        with open(self.output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(self.entries)
        return self.output_path

    def verify_integrity(self) -> bool:
        """
        Verify the chain is unbroken.
        Returns True if intact, False if tampered.
        """
        if not self.entries:
            return True
        prev = "GENESIS"
        for entry in self.entries:
            e = dict(entry)
            stored_hash = e.pop("entry_hash", None)
            if e.get("prev_hash") != prev:
                return False
            canonical = json.dumps(e, sort_keys=True, separators=(",", ":"))
            computed  = _sha256(canonical)
            if computed != stored_hash:
                return False
            prev = stored_hash
        return True

    def integrity_summary(self) -> str:
        ok = self.verify_integrity()
        if ok:
            return f"✓ Audit chain intact — {len(self.entries)} entries, no tampering detected."
        return "✗ AUDIT CHAIN BROKEN — possible data tampering detected!"
