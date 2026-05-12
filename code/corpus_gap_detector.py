"""
corpus_gap_detector.py — Feature 5: Corpus Gap Detector

Identifies when a ticket asks about something NOT covered in the
knowledge base. This is critical for:
  - Alerting content teams to write missing docs
  - Preventing hallucinated responses (low retrieval = low confidence)
  - Routing to human agents when docs are absent

Algorithm:
  1. Check if top retrieved score is below a threshold
  2. Check if retrieved docs are off-topic (wrong company, different area)
  3. Suggest a doc title that SHOULD exist but doesn't
  4. Track all gap topics over a batch run for the analytics dashboard

Gap detection saves support teams from sending back AI-fabricated answers
on topics where no grounded documentation exists.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from models import CorpusGapSignal, RetrievedDoc, SupportTicket


# Minimum retrieval score to consider "covered"
_COVERAGE_THRESHOLD   = 0.35
# If top doc is from WRONG company, treat as gap
_WRONG_COMPANY_PENALTY = 0.15

# Topic → suggested doc title mapping
_TOPIC_DOC_SUGGESTIONS = {
    # HackerRank
    r"(plagiarism|cheat|copy)": "Plagiarism Detection in HackerRank Assessments",
    r"(api\s+key|hackerrank\s+api)": "HackerRank API Authentication & Keys",
    r"(proctoring|proctor|webcam|camera)": "Proctoring Settings and Camera Requirements",
    r"(time\s+limit|extend\s+time)": "Configuring Assessment Time Limits",
    r"(invite|invitation|email.*candidate)": "Sending Assessment Invitations to Candidates",
    r"(question\s+type|mcq|multiple\s+choice)": "Types of Questions in HackerRank",
    r"(anti.cheat|tab.switch|copy.paste)": "Anti-Cheat & Proctoring Features",
    r"(custom\s+test|create.*test)": "Creating a Custom Assessment on HackerRank",
    r"(score\s+report|download\s+report)": "Downloading Candidate Score Reports",
    r"(feedback|interview\s+feedback)": "Leaving Feedback After an Interview",
    r"(cancel\s+test|withdraw\s+test)": "Cancelling or Withdrawing an Assessment",
    # Claude
    r"(projects?\s+feature|claude\s+project)": "Using Projects in Claude.ai",
    r"(artifact|artifacts)": "Claude Artifacts Feature Guide",
    r"(memory|remember\s+me|personali[sz])": "Claude Memory and Personalization",
    r"(plugin|tool\s+use|function\s+call)": "Tool Use and Function Calling in Claude API",
    r"(fine.tun|custom\s+model)": "Custom Model Options with Claude",
    r"(hipaa|soc\s*2|compliance|audit)": "Claude Compliance and Certifications (HIPAA, SOC2)",
    r"(context\s+window|token\s+limit)": "Claude Context Window and Token Limits",
    r"(image.*generat|dall|midjourney)": "Claude Image Generation Capabilities",
    r"(voice|speech|audio)": "Claude Voice and Audio Features",
    # Visa
    r"(emi|equated\s+monthly)": "Visa Card EMI Options in India",
    r"(reward|cashback|point)": "Visa Rewards and Cashback Programs",
    r"(upi|unified\s+payment)": "Visa and UPI Integration",
    r"(contactless|tap\s+to\s+pay|nfc)": "Contactless Payment with Visa",
    r"(virtual\s+card|digital\s+card)": "Visa Virtual Card for Online Payments",
    r"(forex|foreign\s+exchange)": "Visa Foreign Exchange Rates and Fees",
    r"(mobile\s+wallet|google\s+pay|apple\s+pay)": "Visa in Mobile Wallets",
}

_COMPILED_SUGGESTIONS = [
    (re.compile(pat, re.I), title)
    for pat, title in _TOPIC_DOC_SUGGESTIONS.items()
]


def detect_corpus_gap(
    ticket: SupportTicket,
    docs: List[RetrievedDoc],
    effective_company: Optional[str],
) -> CorpusGapSignal:
    """
    Analyse retrieval quality and detect knowledge base gaps.
    """
    if not docs:
        return CorpusGapSignal(
            gap_detected=True,
            max_retrieval_score=0.0,
            gap_description="No documents retrieved — topic may be entirely outside corpus.",
            suggested_doc_title=_suggest_doc_title(ticket),
        )

    top_score = docs[0].score
    top_company = docs[0].chunk.source

    # Apply wrong-company penalty
    effective_score = top_score
    if effective_company and top_company != effective_company:
        effective_score = max(0.0, top_score - _WRONG_COMPANY_PENALTY)

    if effective_score < _COVERAGE_THRESHOLD:
        description_parts = []
        if top_score < _COVERAGE_THRESHOLD:
            description_parts.append(
                f"Best retrieval score {top_score:.3f} < threshold {_COVERAGE_THRESHOLD}"
            )
        if top_company != effective_company and effective_company:
            description_parts.append(
                f"Top doc is from {top_company}, but ticket is for {effective_company}"
            )
        description = "; ".join(description_parts)

        return CorpusGapSignal(
            gap_detected=True,
            max_retrieval_score=round(top_score, 3),
            gap_description=description,
            suggested_doc_title=_suggest_doc_title(ticket),
        )

    return CorpusGapSignal(
        gap_detected=False,
        max_retrieval_score=round(top_score, 3),
    )


def _suggest_doc_title(ticket: SupportTicket) -> str:
    """Suggest what doc SHOULD be written to cover this gap."""
    text = f"{ticket.subject} {ticket.issue}"
    for pattern, title in _COMPILED_SUGGESTIONS:
        if pattern.search(text):
            return title
    company = ticket.company or "General"
    return f"[{company}] New support article needed for: {ticket.subject or ticket.issue[:60]}"


def summarise_gaps(gaps: List[Tuple[int, CorpusGapSignal]]) -> dict:
    """
    Aggregate gap signals across a batch run.
    Returns a summary dict for the analytics dashboard.
    """
    if not gaps:
        return {"total_gaps": 0, "suggested_articles": [], "coverage_rate": 1.0}

    total = len(gaps)
    gap_count = sum(1 for _, g in gaps if g.gap_detected)
    suggested = list({g.suggested_doc_title for _, g in gaps
                      if g.gap_detected and g.suggested_doc_title})

    return {
        "total_tickets":    total,
        "total_gaps":       gap_count,
        "coverage_rate":    round(1 - gap_count / max(total, 1), 3),
        "suggested_articles": suggested[:10],
        "avg_top_score":    round(
            sum(g.max_retrieval_score for _, g in gaps) / max(total, 1), 3
        ),
    }
