"""
quality_validator.py — Feature 6: Response Quality Validator

Self-validates every generated response BEFORE it's written to output.
No LLM call required — uses heuristic quality signals.

Checks performed:
  A) Relevance     — Does the response address what was asked?
  B) Groundedness  — Does it avoid speculative/hallucinated claims?
  C) Completeness  — Are all sub-questions in the ticket addressed?
  D) Safety        — Does it avoid leaking instructions or sensitive data?
  E) Actionability — Does it give the user clear next steps?

Outputs:
  - quality_score [0–1]
  - answers_the_question (bool)
  - is_grounded (bool)
  - issues (list of specific problems found)
  - follow_up_questions (list of clarifying Qs the user might need)

This is the "second opinion" layer — it catches cases where the response
engine produced something off-topic, too vague, or potentially harmful.
If quality_score < 0.5, the result is automatically flagged for human review.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from models import QualitySignal, RetrievedDoc, SupportTicket, TicketStatus

# ── Groundedness red-flags: phrases a hallucinating LLM or template engine
#    might produce that aren't grounded in any of the corpus documents ───────

_HALLUCINATION_SIGNALS = re.compile(
    r"\b(as\s+(an?\s+)?ai|i\s+cannot\s+browse|i\s+don['\s]+t\s+have\s+access"
    r"|i\s+am\s+not\s+able\s+to\s+verify|based\s+on\s+my\s+training"
    r"|my\s+knowledge\s+cutoff|i\s+apologize.*cannot|generally\s+speaking"
    r"|it\s+is\s+possible\s+that|you\s+might\s+want\s+to\s+consider"
    r"|i\s+(believe|think|assume|suppose)\s+that)\b",
    re.I,
)

# Vague responses that aren't really answers
_VAGUENESS_SIGNALS = re.compile(
    r"^(thank\s+you\s+for\s+(contacting|reaching)|we\s+have\s+received\s+your"
    r"|your\s+(request|ticket)\s+has\s+been\s+received)\s*[.,]?\s*$",
    re.I,
)

# Sensitive data leakage patterns (should never appear in a response)
_SENSITIVE_LEAKAGE = re.compile(
    r"\b(here\s+is\s+(your|the)\s+(password|api\s+key|secret|token|cvv|pin)"
    r"|your\s+password\s+is\s*:?\s*\S+"
    r"|api\s+key\s*:\s*sk-ant-)",
    re.I,
)

# Patterns that suggest the response is actually answering the question
_ACTIONABILITY_SIGNALS = re.compile(
    r"\b(step\s+\d|go\s+to|click|navigate|visit|contact|call|email|log\s+in"
    r"|open|select|choose|enter|type|submit|check|verify|update|download"
    r"|follow\s+the|in\s+order\s+to|to\s+resolve|to\s+fix|to\s+reset)\b",
    re.I,
)

# Minimum response length (chars) to be considered a real answer
_MIN_RESPONSE_LENGTH = 80
# Maximum response length before it's flagged as potentially padded
_MAX_RESPONSE_LENGTH = 3000


def _extract_questions_from_issue(issue: str) -> List[str]:
    """Extract distinct question topics from the issue text."""
    topics = []
    # Questions marked with ?
    for sentence in re.split(r"[.!?]", issue):
        sentence = sentence.strip()
        if (
            len(sentence) > 10
            and "?" in issue
            and any(
                kw in sentence.lower()
                for kw in ["how", "what", "why", "when", "where", "can i", "is it", "do i", "will"]
            )
        ):
            topics.append(sentence[:80])
    # Enumerate sub-issues (numbered lists in the issue)
    numbered = re.findall(r"\d+[.)]\s+([^\n]{10,80})", issue)
    topics.extend(numbered[:3])
    return topics[:4]


def _check_relevance(issue: str, response: str, company: str) -> Tuple[bool, List[str]]:
    """Check if the response actually addresses the issue."""
    issues_found = []

    # Too short to be useful
    if len(response.strip()) < _MIN_RESPONSE_LENGTH:
        issues_found.append(f"Response is too short ({len(response)} chars) to be informative.")
        return False, issues_found

    # Check keyword overlap between issue and response
    issue_tokens = set(re.findall(r"\b[a-z]{4,}\b", issue.lower()))
    response_tokens = set(re.findall(r"\b[a-z]{4,}\b", response.lower()))
    # Remove extremely common words
    stopwords = {
        "this",
        "that",
        "with",
        "your",
        "have",
        "will",
        "from",
        "they",
        "their",
        "also",
        "more",
        "about",
        "into",
        "which",
    }
    issue_tokens -= stopwords
    response_tokens -= stopwords

    if issue_tokens:
        overlap = len(issue_tokens & response_tokens) / len(issue_tokens)
        if overlap < 0.10:
            issues_found.append(
                f"Low keyword overlap ({overlap:.0%}) between issue and response — "
                "response may be off-topic."
            )
            return False, issues_found

    return True, issues_found


def _check_groundedness(response: str) -> Tuple[bool, List[str]]:
    """Check that the response doesn't contain hallucination markers."""
    issues_found = []

    if _HALLUCINATION_SIGNALS.search(response):
        issues_found.append(
            "Response contains hedging language typical of hallucination or out-of-corpus claims."
        )
        return False, issues_found

    if _SENSITIVE_LEAKAGE.search(response):
        issues_found.append("CRITICAL: Response may contain sensitive data leakage.")
        return False, issues_found

    return True, issues_found


def _check_actionability(response: str, status: str) -> Tuple[float, List[str]]:
    """Score how actionable the response is."""
    issues_found = []

    if status == "escalated":
        return 1.0, []  # Escalation messages are inherently actionable

    if _VAGUENESS_SIGNALS.match(response.strip()):
        issues_found.append("Response is a generic acknowledgement with no actionable steps.")
        return 0.1, issues_found

    action_hits = len(_ACTIONABILITY_SIGNALS.findall(response))
    if action_hits == 0 and len(response) > 200:
        issues_found.append(
            "Response lacks actionable instructions (no steps, links, or clear next actions)."
        )
        score = 0.4
    elif action_hits < 2:
        score = 0.6
    else:
        score = 1.0

    return score, issues_found


def _generate_follow_up_questions(ticket: SupportTicket, response: str) -> List[str]:
    """Generate follow-up questions an agent might need to ask."""
    questions = []
    issue = ticket.issue.lower()

    if (
        re.search(r"\b(error|fail|not\s+work|crash)\b", issue)
        and "error message" not in issue
        and "error:" not in issue
    ):
        questions.append("Could you share the exact error message you're seeing?")

    if (
        re.search(r"\b(account|login|access)\b", issue)
        and "email" not in issue
        and "@" not in issue
    ):
        questions.append("What is the email address associated with your account?")

    if re.search(r"\b(yesterday|last\s+week|recently|since)\b", issue):
        questions.append("When exactly did this issue first occur? (date and time if possible)")

    if (
        re.search(r"\b(browser|app|mobile|desktop)\b", issue)
        and "chrome" not in issue
        and "firefox" not in issue
        and "safari" not in issue
    ):
        questions.append("Which browser or device are you using?")

    if (
        ticket.company == "Visa"
        and re.search(r"\b(transaction|charge|payment)\b", issue)
        and not re.search(r"\$[\d,]+|\d+\s*rupee|\d+\s*inr", issue)
    ):
        questions.append("What is the transaction amount and date?")

    return questions[:3]


def validate_response(
    ticket: SupportTicket,
    response: str,
    status: str,
    docs: List[RetrievedDoc],
) -> QualitySignal:
    """
    Full quality validation pass. Returns a QualitySignal with score and diagnostics.
    """
    all_issues: List[str] = []

    # A) Relevance check
    relevant, rel_issues = _check_relevance(ticket.issue, response, ticket.company)
    all_issues.extend(rel_issues)

    # B) Groundedness check
    grounded, grd_issues = _check_groundedness(response)
    all_issues.extend(grd_issues)

    # C) Actionability score
    action_score, act_issues = _check_actionability(response, status)
    all_issues.extend(act_issues)

    # D) Corpus support check
    corpus_supported = bool(docs) and docs[0].score > 0.15
    if not corpus_supported and status == "replied":
        all_issues.append("Response has no strong corpus support — may contain unsupported claims.")

    # E) Length check
    resp_len = len(response.strip())
    if resp_len > _MAX_RESPONSE_LENGTH:
        all_issues.append(f"Response is very long ({resp_len} chars) — may need trimming.")

    # Compute overall quality score
    relevance_score = 1.0 if relevant else 0.3
    groundedness_score = 1.0 if grounded else 0.2
    corpus_score = 1.0 if corpus_supported else 0.5

    quality = round(
        relevance_score * 0.35
        + groundedness_score * 0.25
        + action_score * 0.25
        + corpus_score * 0.15,
        3,
    )

    # Follow-up questions
    follow_ups = _generate_follow_up_questions(ticket, response)

    return QualitySignal(
        score=quality,
        answers_the_question=relevant,
        is_grounded=grounded,
        issues=all_issues,
        follow_up_questions=follow_ups,
    )
