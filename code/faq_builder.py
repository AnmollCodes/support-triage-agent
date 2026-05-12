"""
faq_builder.py — Feature 5: Auto-FAQ Knowledge Base Builder

Every time the agent successfully answers a ticket with high confidence,
it generates a draft FAQ entry. Over time, this builds a self-healing
knowledge base that fills documentation gaps automatically.

Output:
  - faq_entries.json  — structured FAQ entries with Q, A, product area, tags
  - Human-editable markdown  — direct paste into support docs

This is the compounding value feature: every ticket processed makes the
next batch faster and better. Like GitHub Copilot, but for support knowledge.
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from models import SupportTicket, TriageResult, TicketStatus


@dataclass
class FAQEntry:
    question: str
    answer: str
    product: str
    product_area: str
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0
    source_ticket: int = 0  # 1-indexed


_QUESTION_PREFIXES = [
    r"how\s+(do\s+i|can\s+i|to)",
    r"what\s+(is|are|happens)",
    r"why\s+(is|does|can['\s]+t|won['\s]+t)",
    r"can\s+i",
    r"where\s+(do\s+i|can\s+i|is)",
    r"when\s+(will|does|is)",
    r"is\s+(it|there|the)",
]
_QUESTION_PAT = re.compile(r"(?:" + "|".join(_QUESTION_PREFIXES) + r")\s+.{10,120}", re.I)

_TAG_PATTERNS = {
    "password-reset": re.compile(r"\b(password|reset|forgot)\b", re.I),
    "billing": re.compile(r"\b(bill|payment|charge|invoice|refund)\b", re.I),
    "account-access": re.compile(r"\b(login|access|account|sign\s+in)\b", re.I),
    "api": re.compile(r"\b(api|sdk|endpoint|token)\b", re.I),
    "assessment": re.compile(r"\b(test|assessment|challenge|submission)\b", re.I),
    "fraud-security": re.compile(r"\b(fraud|security|stolen|unauthorized)\b", re.I),
    "privacy": re.compile(r"\b(gdpr|data|privacy|delete|crawl)\b", re.I),
    "mobile": re.compile(r"\b(mobile|ios|android|app)\b", re.I),
    "travel": re.compile(r"\b(travel|abroad|foreign|card)\b", re.I),
}


def _extract_question(ticket: SupportTicket) -> str:
    """Extract or synthesise the canonical question from a ticket."""
    issue = ticket.issue.strip()
    subject = ticket.subject.strip()

    # Direct question in issue
    m = _QUESTION_PAT.search(issue)
    if m:
        q = m.group(0).strip().rstrip(".!,")
        return q[0].upper() + q[1:] + "?"

    # Use subject as question
    if subject and len(subject) > 8:
        s = subject.rstrip("?")
        return f"How do I resolve: {s}?"

    # Synthesise from first sentence of issue
    first = re.split(r"[.!?\n]", issue)[0].strip()
    if len(first) > 15:
        return f"What to do when: {first[:100]}?"

    return f"Support question about {ticket.company}: {issue[:80]}?"


def _extract_tags(ticket: SupportTicket, result: TriageResult) -> List[str]:
    text = f"{ticket.issue} {ticket.subject}".lower()
    tags = [result.product_area, ticket.company.lower()]
    for tag, pat in _TAG_PATTERNS.items():
        if pat.search(text):
            tags.append(tag)
    return list(set(t for t in tags if t))


def build_faq_entry(
    ticket: SupportTicket,
    result: TriageResult,
    ticket_num: int,
    confidence_threshold: float = 0.65,
) -> Optional[FAQEntry]:
    """
    Generate an FAQ entry if the ticket was confidently answered.
    Returns None if confidence is too low or ticket was escalated.
    """
    # Only create FAQs for high-confidence replies
    if result.status == TicketStatus.ESCALATED:
        return None
    if result.confidence.score < confidence_threshold:
        return None
    if result.request_type.value == "invalid":
        return None

    question = _extract_question(ticket)
    answer = result.response
    tags = _extract_tags(ticket, result)

    # Trim overly long answers for FAQ format
    if len(answer) > 800:
        # Keep first 800 chars, end at a sentence boundary
        truncated = answer[:800]
        last_period = max(truncated.rfind("."), truncated.rfind("\n"))
        if last_period > 400:
            answer = (
                truncated[: last_period + 1] + "\n\n*[See full support article for more details.]*"
            )

    return FAQEntry(
        question=question,
        answer=answer,
        product=ticket.company,
        product_area=result.product_area,
        tags=tags,
        confidence=result.confidence.score,
        source_ticket=ticket_num,
    )


def save_faq_entries(entries: List[FAQEntry], output_dir: Path) -> None:
    """Save FAQ entries as both JSON and Markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON (machine-readable)
    json_path = output_dir / "faq_entries.json"
    data = [
        {
            "question": e.question,
            "answer": e.answer,
            "product": e.product,
            "product_area": e.product_area,
            "tags": e.tags,
            "confidence": e.confidence,
            "source_ticket": e.source_ticket,
        }
        for e in entries
    ]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Markdown (human-editable)
    md_path = output_dir / "faq_draft.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Auto-Generated FAQ Draft\n")
        f.write(f"*Generated from {len(entries)} support tickets. Review before publishing.*\n\n")

        # Group by product
        by_product: dict = {}
        for e in entries:
            by_product.setdefault(e.product, []).append(e)

        for product, product_entries in sorted(by_product.items()):
            f.write(f"## {product}\n\n")
            for e in product_entries:
                f.write(f"### {e.question}\n\n")
                f.write(f"**Category:** {e.product_area}  ")
                f.write(f"**Tags:** {', '.join(e.tags[:4])}  ")
                f.write(f"**Confidence:** {e.confidence:.0%}\n\n")
                f.write(f"{e.answer}\n\n")
                f.write("---\n\n")
