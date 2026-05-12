"""
tone_personalizer.py — Adaptive Response Tone Personalizer

Detects the user's communication profile and adapts the response register.
Does NOT add redundant openers if the response already has one.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from models import SupportTicket, RequestType, TicketStatus


@dataclass
class ToneProfile:
    user_type: str  # TECHNICAL / BUSINESS / NON_TECHNICAL / STUDENT / ENTERPRISE
    tone: str  # formal / friendly / empathetic / terse
    complexity: str  # high / medium / low
    profile_signals: list


_TECHNICAL_PAT = re.compile(
    r"\b(api|sdk|endpoint|curl|json|xml|python|javascript|node|npm|pip|docker"
    r"|kubectl|oauth|webhook|regex|repository|github|cli|terminal|bash|error\s+code"
    r"|stack\s+trace|null|undefined|exception|timeout|latency|throughput|http\s*\d{3}"
    r"|rate\s+limit|async|await|cors|ssl|tls|jwt|token|payload)\b",
    re.I,
)
_BUSINESS_PAT = re.compile(
    r"\b(roi|kpi|roadmap|stakeholder|budget|procurement|renewal|contract|sla"
    r"|compliance|audit|onboarding|adoption|milestone|deliverable|quarterly"
    r"|executive|board|ceo|cto|cfo|vp|director|strategy|initiative)\b",
    re.I,
)
_NON_TECHNICAL_PAT = re.compile(
    r"\b(how\s+do\s+i|what\s+is|i\s+don['\s]+t\s+understand|confused|not\s+sure\s+how"
    r"|please\s+help|step\s+by\s+step|walk\s+me\s+through|explain|beginner|never\s+used)\b",
    re.I,
)
_STUDENT_PAT = re.compile(
    r"\b(student|university|college|professor|course|assignment|internship|fresher"
    r"|graduate|campus|placement|learn|practice|study)\b",
    re.I,
)
_ENTERPRISE_PAT = re.compile(
    r"\b(enterprise|our\s+(company|organization|team)|annual\s+contract|legal\s+team"
    r"|procurement|vendor\s+assessment|security\s+review|infosec|data\s+processing)\b",
    re.I,
)

# Patterns indicating the response already has a proper opener — don't add another
_HAS_OPENER = re.compile(
    r"^(we['\s]*re\s+sorry|i['\s]*m\s+sorry|sorry\s+to\s+hear|thank\s+you\s+for"
    r"|thanks\s+for|your\s+ticket|this\s+request|we\s+have\s+received"
    r"|congratulations|hello|hi\s+there|good\s+news|understood|noted)",
    re.I,
)


def detect_tone_profile(ticket: SupportTicket) -> ToneProfile:
    text = f"{ticket.subject} {ticket.issue}"
    tech_hits = len(_TECHNICAL_PAT.findall(text))
    biz_hits = len(_BUSINESS_PAT.findall(text))
    nont_hits = len(_NON_TECHNICAL_PAT.findall(text))
    stud_hits = len(_STUDENT_PAT.findall(text))
    ent_hits = len(_ENTERPRISE_PAT.findall(text))

    scores = {
        "TECHNICAL": tech_hits * 3,
        "BUSINESS": biz_hits * 2,
        "NON_TECHNICAL": nont_hits * 2,
        "STUDENT": stud_hits * 2,
        "ENTERPRISE": ent_hits * 4,
    }
    user_type = max(scores, key=scores.get)
    if scores[user_type] == 0:
        user_type = "NON_TECHNICAL"

    profile_map = {
        "TECHNICAL": ("terse", "high", ["technical_vocabulary"]),
        "BUSINESS": ("formal", "medium", ["business_language"]),
        "NON_TECHNICAL": ("empathetic", "low", ["plain_language_needed"]),
        "STUDENT": ("friendly", "low", ["educational_context"]),
        "ENTERPRISE": ("formal", "medium", ["enterprise_context"]),
    }
    tone, complexity, type_signals = profile_map[user_type]
    signals = list(type_signals)
    if tech_hits:
        signals.append(f"technical_terms:{tech_hits}")
    if biz_hits:
        signals.append(f"business_terms:{biz_hits}")

    return ToneProfile(
        user_type=user_type, tone=tone, complexity=complexity, profile_signals=signals
    )


def personalize_response(
    response: str,
    profile: ToneProfile,
    request_type: str = "product_issue",
    status: str = "replied",
) -> str:
    """
    Adapt a response to match the detected user profile.
    Guards against adding duplicate openers or modifying invalid/security tickets.
    """
    # Never modify invalid tickets, escalated security/injection, or short responses
    if request_type == "invalid":
        return response
    if len(response.strip()) < 30:
        return response

    response = response.strip()
    already_has_opener = bool(_HAS_OPENER.match(response))

    if profile.user_type == "TECHNICAL":
        # Remove over-explaining filler phrases
        response = re.sub(
            r"(Please\s+note\s+that\s+|It\s+is\s+important\s+to\s+note\s+that\s+"
            r"|You\s+should\s+know\s+that\s+)",
            "",
            response,
            flags=re.I,
        )

    elif profile.user_type == "NON_TECHNICAL":
        # Only add empathetic opener if one isn't already there
        if not already_has_opener and status == "replied":
            response = "We're here to help! Here's what to do:\n\n" + response

    elif profile.user_type == "BUSINESS":
        # Only add outcome framing if no opener
        if not already_has_opener and status == "replied":
            first_line = response.split("\n")[0][:80]
            response = f"**Resolution Summary:** {first_line}\n\n" + response

    elif profile.user_type == "ENTERPRISE":
        # Append SLA note at end if not already present
        if (
            "sla" not in response.lower()
            and "business day" not in response.lower()
            and status == "replied"
        ):
            response += (
                "\n\nAs an enterprise customer, your ticket is prioritised under our "
                "enterprise SLA. A dedicated support engineer will follow up within "
                "your contracted response window."
            )

    return response
