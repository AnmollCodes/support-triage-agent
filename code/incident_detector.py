"""
incident_detector.py — Feature 7: Incident Outbreak Detector

Detects when multiple tickets in a batch share the same root cause,
indicating a platform-wide incident rather than isolated user issues.

Algorithm:
  1. Extract a "symptom fingerprint" from each ticket
     (company + product_area + dominant keywords)
  2. Cluster tickets with matching fingerprints
  3. For clusters of 2+ tickets: generate an IncidentReport
  4. Assign severity: SEV1 (3+ tickets, P0), SEV2 (2+ tickets, P1), SEV3 (pattern)
  5. Draft an auto-response template for the affected users
  6. Tag all tickets in the cluster with a shared incident_cluster_id

Why this matters:
  Without this, support agents handle 5 identical "assessment not loading"
  tickets individually instead of recognising they're all the same outage.
  This module catches outbreaks the moment 2 tickets arrive.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from models import (
    IncidentReport, IncidentSeverity, SupportTicket,
    TriageResult, UrgencyTier,
)


# ── Symptom extraction ────────────────────────────────────────────

_SYMPTOM_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("login_failure",       re.compile(r"\b(can['\s]+t\s+log\s*(in|out)|login\s+fail|sign\s+in\s+fail|invalid\s+credentials)\b", re.I)),
    ("submission_fail",     re.compile(r"\b(submission.*fail|code.*not\s+submit|submit.*error|run.*fail)\b", re.I)),
    ("assessment_down",     re.compile(r"\b(assessment.*not\s+(load|work|open)|test.*unavailable|assessment.*error)\b", re.I)),
    ("payment_fail",        re.compile(r"\b(payment.*fail|payment.*error|billing.*error|charge.*fail)\b", re.I)),
    ("api_down",            re.compile(r"\b(api.*fail|api.*error|all\s+requests.*fail|requests\s+failing)\b", re.I)),
    ("card_declined",       re.compile(r"\b(card.*declin|transaction.*fail|payment.*declin)\b", re.I)),
    ("interview_issue",     re.compile(r"\b(interview.*not\s+(work|load)|zoom.*fail|live\s+coding.*error)\b", re.I)),
    ("account_locked",      re.compile(r"\b(account.*locked|account.*blocked|access.*denied|locked\s+out)\b", re.I)),
    ("page_not_loading",    re.compile(r"\b(page.*not\s+load|page.*blank|infinite\s+spin|white\s+screen)\b", re.I)),
    ("slow_performance",    re.compile(r"\b(very\s+slow|extremely\s+slow|timing\s+out|timeout|taking\s+too\s+long)\b", re.I)),
    ("email_not_received",  re.compile(r"\b(email.*not\s+receiv|invitation.*not\s+arriv|no\s+email)\b", re.I)),
    ("resume_builder_down", re.compile(r"\b(resume\s+builder.*not|resume.*not\s+load)\b", re.I)),
    ("claude_not_responding", re.compile(r"\b(claude.*not\s+respond|claude.*stopped|claude.*down|not\s+generat)\b", re.I)),
]


def _extract_symptom_fingerprint(
    ticket: SupportTicket, result: TriageResult
) -> str:
    """
    Creates a reproducible fingerprint string representing the core symptom.
    Tickets with the same fingerprint are considered related incidents.
    """
    company = (ticket.company or "unknown").lower().replace(" ", "_")
    area    = (result.product_area or "general").lower().replace(" ", "_")
    text    = f"{ticket.subject} {ticket.issue}".lower()

    for symptom_name, pattern in _SYMPTOM_PATTERNS:
        if pattern.search(text):
            return f"{company}::{area}::{symptom_name}"

    # Fallback: use top 3 non-stop keywords from the issue
    tokens = re.findall(r"\b[a-z]{5,}\b", text)
    stopwords = {"about", "their", "there", "which", "these", "those",
                 "would", "could", "should", "please", "thank", "hello"}
    keywords = [t for t in tokens if t not in stopwords]
    top3 = sorted(set(keywords), key=keywords.count, reverse=True)[:3]
    return f"{company}::{area}::" + "_".join(top3) if top3 else f"{company}::{area}::general"


def _severity(ticket_count: int, has_p0: bool) -> IncidentSeverity:
    if has_p0 or ticket_count >= 3:
        return IncidentSeverity.SEV1
    elif ticket_count >= 2:
        return IncidentSeverity.SEV2
    return IncidentSeverity.SEV3


def _draft_auto_response(symptom: str, company: str, area: str) -> str:
    """Draft a canned mass-response for affected users."""
    company_display = company.title()
    area_display    = area.replace("_", " ").title()

    if "down" in symptom or "fail" in symptom or "error" in symptom:
        return (
            f"We are aware of an ongoing issue affecting {area_display} on {company_display}. "
            f"Our engineering team has been notified and is actively investigating. "
            f"We apologise for the inconvenience and will provide updates as soon as possible. "
            f"Please check status.{company.lower()}.com for real-time updates."
        )
    elif "login" in symptom or "account" in symptom:
        return (
            f"We are investigating reports of login and account access issues on {company_display}. "
            f"Our team is working on a resolution. As a workaround, please try clearing "
            f"your browser cache and cookies. We will update you shortly."
        )
    elif "payment" in symptom or "billing" in symptom:
        return (
            f"We are aware of payment and billing issues affecting {company_display} users. "
            f"No charges will be lost — our billing team is investigating and will process "
            f"any failed transactions once resolved. We apologise for the disruption."
        )
    else:
        return (
            f"We have identified a pattern of related issues on {company_display} "
            f"affecting {area_display}. Our team is actively investigating. "
            f"Thank you for your patience — we will follow up shortly with a resolution."
        )


def _cluster_id(fingerprint: str) -> str:
    """Generate a short human-readable cluster ID from a fingerprint."""
    h = hashlib.md5(fingerprint.encode()).hexdigest()[:6].upper()
    parts = fingerprint.split("::")
    company_abbr = parts[0][:3].upper() if parts else "UNK"
    return f"INC-{company_abbr}-{h}"


def detect_incidents(
    tickets: List[SupportTicket],
    results: List[TriageResult],
) -> Tuple[List[IncidentReport], Dict[int, str]]:
    """
    Main outbreak detection function.

    Returns:
        incidents       — list of IncidentReport objects (one per cluster)
        ticket_clusters — dict mapping ticket_index → cluster_id
    """
    # Group tickets by fingerprint
    fingerprint_map: Dict[str, List[int]] = defaultdict(list)
    fingerprints: Dict[int, str] = {}

    for i, (ticket, result) in enumerate(zip(tickets, results)):
        fp = _extract_symptom_fingerprint(ticket, result)
        fingerprint_map[fp].append(i)
        fingerprints[i] = fp

    incidents: List[IncidentReport] = []
    ticket_clusters: Dict[int, str] = {}

    for fingerprint, indices in fingerprint_map.items():
        if len(indices) < 2:
            continue  # Not an outbreak — isolated ticket

        # Determine severity
        has_p0 = any(
            results[i].urgency.tier == UrgencyTier.P0_CRITICAL
            for i in indices
        )
        sev = _severity(len(indices), has_p0)

        # Parse fingerprint parts
        parts   = fingerprint.split("::")
        company = parts[0].replace("_", " ").title() if len(parts) > 0 else "Unknown"
        area    = parts[1].replace("_", " ").title() if len(parts) > 1 else "General"
        symptom = parts[2] if len(parts) > 2 else "unknown_symptom"

        cid = _cluster_id(fingerprint)

        # Collect common symptoms from actual ticket text
        symptom_texts = []
        for i in indices:
            words = re.findall(r"\b[a-z]{5,}\b", tickets[i].issue.lower())
            symptom_texts.extend(words[:5])
        from collections import Counter
        common = [w for w, _ in Counter(symptom_texts).most_common(6)]

        report = IncidentReport(
            cluster_id=cid,
            title=f"[{sev.value}] {company} — {symptom.replace('_', ' ').title()} ({len(indices)} tickets)",
            ticket_indices=[i + 1 for i in indices],  # 1-indexed for humans
            company=company,
            product_area=area,
            severity=sev,
            ticket_count=len(indices),
            summary=(
                f"{len(indices)} tickets reporting '{symptom.replace('_', ' ')}' "
                f"for {company} / {area}. "
                f"First ticket: #{indices[0]+1}."
            ),
            common_symptoms=common,
            recommended_action=(
                "Escalate to on-call engineering team immediately."
                if sev == IncidentSeverity.SEV1 else
                "Notify product team and monitor for additional tickets."
                if sev == IncidentSeverity.SEV2 else
                "Log pattern; re-evaluate if count increases."
            ),
            auto_response_draft=_draft_auto_response(symptom, company, area),
        )
        incidents.append(report)

        for i in indices:
            ticket_clusters[i] = cid

    return incidents, ticket_clusters
