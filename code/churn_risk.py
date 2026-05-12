"""
churn_risk.py — Feature 2: Business Impact & Churn Risk Scorer

Estimates revenue-at-risk and churn probability for every ticket.
This is what enterprise support teams pay $50k/year for in tools like
Gainsight, Totango, and ChurnZero.

Outputs per ticket:
  churn_risk_score   [0-100]   — probability user churns if issue unresolved
  revenue_at_risk    [str]     — estimated tier: Low / Medium / High / Critical
  business_impact    [str]     — human-readable impact statement
  retention_priority [str]     — action level: Monitor / Proactive / Urgent / Emergency
  churn_signals      [list]    — what drove the score
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List
from models import SupportTicket, TriageResult, TicketStatus, UrgencyTier


@dataclass
class ChurnRiskResult:
    churn_risk_score:   int    = 0        # 0-100
    revenue_at_risk:    str    = "Low"    # Low / Medium / High / Critical
    business_impact:    str    = ""
    retention_priority: str    = "Monitor"
    churn_signals:      List[str] = field(default_factory=list)


_COMPETITOR_PAT = re.compile(
    r"\b(switch(ing)?\s+to|moving\s+(to|away)|cancel(ling|ed)?|looking\s+for\s+alternative"
    r"|considering\s+other|evaluating\s+competitor|unhappy\s+with|disappointed\s+with"
    r"|last\s+chance|final\s+warning|no\s+longer\s+use|stop\s+using)\b", re.I
)
_BILLING_PAIN_PAT = re.compile(
    r"\b(overcharged|double\s+charged|wrong\s+amount|billing\s+error|invoice\s+wrong"
    r"|charged\s+twice|unexpected\s+charge|cancel\s+(my\s+)?subscription)\b", re.I
)
_ENTERPRISE_PAT = re.compile(
    r"\b(enterprise|our\s+team|our\s+company|our\s+organization|annual\s+contract"
    r"|multi.year|thousands?\s+of|hundreds?\s+of\s+users|large\s+team)\b", re.I
)
_REPEATED_PAT = re.compile(
    r"\b(again|third\s+time|multiple\s+times|still\s+not|weeks?\s+ago|months?\s+ago"
    r"|reported\s+(this|before)|already\s+contacted|follow\s+up)\b", re.I
)
_DEADLINE_PAT = re.compile(
    r"\b(urgent|asap|immediately|today|tonight|by\s+tomorrow|deadline|time\s+sensitive"
    r"|running\s+out\s+of\s+time|last\s+minute)\b", re.I
)
_EXECUTIVE_PAT = re.compile(
    r"\b(ceo|cto|cfo|vp|vice\s+president|director|head\s+of|manager|founder|owner)\b", re.I
)


def score_churn_risk(
    ticket: SupportTicket,
    result: TriageResult,
) -> ChurnRiskResult:
    text = f"{ticket.subject} {ticket.issue}".lower()
    signals: List[str] = []
    score = 0

    # Competitor/cancel signals (highest weight)
    if _COMPETITOR_PAT.search(text):
        score += 40
        signals.append("competitor_or_cancel_language")

    # Billing pain (very high churn driver)
    if _BILLING_PAIN_PAT.search(text):
        score += 25
        signals.append("billing_dissatisfaction")

    # Enterprise account (more revenue at risk)
    if _ENTERPRISE_PAT.search(text) or result.vip.is_vip:
        score += 20
        signals.append("enterprise_or_high_value_account")

    # Repeated issue (frustration compounding)
    if _REPEATED_PAT.search(text):
        score += 15
        signals.append("repeated_or_recurring_issue")

    # Deadline pressure (unresolved = immediate churn)
    if _DEADLINE_PAT.search(text):
        score += 10
        signals.append("deadline_or_time_pressure")

    # Executive sender (influence + visible churn)
    if _EXECUTIVE_PAT.search(text):
        score += 10
        signals.append("executive_contact")

    # Urgency tier boost
    tier_boost = {
        UrgencyTier.P0_CRITICAL: 15,
        UrgencyTier.P1_HIGH:     10,
        UrgencyTier.P2_MEDIUM:   5,
        UrgencyTier.P3_LOW:      0,
    }.get(result.urgency.tier, 0)
    if tier_boost:
        score += tier_boost
        signals.append(f"urgency_{result.urgency.tier.value}")

    # Escalated but expected reply → distrust signal
    if result.status == TicketStatus.ESCALATED:
        score += 5
        signals.append("requires_human_escalation")

    score = min(score, 100)

    # Tier buckets
    if score >= 70:
        revenue  = "Critical"
        priority = "Emergency"
        impact   = (
            "High churn risk detected. This account is likely to cancel if the issue "
            "is not resolved immediately. Assign a senior CSM and escalate now."
        )
    elif score >= 45:
        revenue  = "High"
        priority = "Urgent"
        impact   = (
            "Significant churn risk. Customer shows frustration signals that often "
            "precede cancellation. Prioritise resolution and proactive outreach."
        )
    elif score >= 20:
        revenue  = "Medium"
        priority = "Proactive"
        impact   = (
            "Moderate churn risk. Monitor closely and ensure timely resolution "
            "to prevent escalation into a high-risk situation."
        )
    else:
        revenue  = "Low"
        priority = "Monitor"
        impact   = "Low churn risk. Standard resolution timeline is appropriate."

    return ChurnRiskResult(
        churn_risk_score=score,
        revenue_at_risk=revenue,
        business_impact=impact,
        retention_priority=priority,
        churn_signals=signals,
    )
