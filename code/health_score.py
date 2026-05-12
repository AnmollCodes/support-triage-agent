"""
health_score.py — Feature 8: Customer Health Score Engine

Computes a 0-100 composite "Customer Health Score" for each ticket
by combining 6 weighted signals. Mirrors enterprise CSM tools like
Gainsight CS, Salesforce Health Cloud, and Totango.

Score breakdown:
  Sentiment score     (25%) — positive=100, neutral=60, frustrated=30, angry=10
  Urgency score       (20%) — P3=100, P2=60, P1=25, P0=5
  Confidence score    (15%) — agent confidence in resolution
  Quality score       (15%) — response quality (was question answered?)
  Churn risk          (15%) — inverse: 100 - churn_risk_score
  VIP/strategic value (10%) — VIP accounts weighted higher

Output:
  health_score:  int   [0-100]
  health_label:  str   ["Healthy", "At Risk", "Critical", "Red Alert"]
  health_color:  str   ["green", "yellow", "orange", "red"]
  health_summary: str  — one-line explanation
"""

from __future__ import annotations
from dataclasses import dataclass
from models import Sentiment, SupportTicket, TriageResult, UrgencyTier
from churn_risk import ChurnRiskResult


@dataclass
class HealthScoreResult:
    health_score: int = 100
    health_label: str = "Healthy"
    health_color: str = "green"
    health_summary: str = ""
    component_scores: dict = None

    def __post_init__(self):
        if self.component_scores is None:
            self.component_scores = {}


_SENTIMENT_SCORE = {
    Sentiment.POSITIVE: 100,
    Sentiment.NEUTRAL: 65,
    Sentiment.FRUSTRATED: 30,
    Sentiment.DISTRESSED: 20,
    Sentiment.ANGRY: 5,
}
_URGENCY_SCORE = {
    UrgencyTier.P3_LOW: 100,
    UrgencyTier.P2_MEDIUM: 60,
    UrgencyTier.P1_HIGH: 25,
    UrgencyTier.P0_CRITICAL: 5,
}


def compute_health_score(
    ticket: SupportTicket,
    result: TriageResult,
    churn: ChurnRiskResult,
) -> HealthScoreResult:

    sentiment_s = _SENTIMENT_SCORE.get(result.sentiment.sentiment, 65)
    urgency_s = _URGENCY_SCORE.get(result.urgency.tier, 60)
    confidence_s = int(result.confidence.score * 100)
    quality_s = int(result.quality.score * 100)
    churn_s = 100 - churn.churn_risk_score  # inverse churn risk
    vip_s = 60 if result.vip.is_vip else 90  # VIP = more scrutiny needed

    # Weighted composite
    score = int(
        sentiment_s * 0.25
        + urgency_s * 0.20
        + confidence_s * 0.15
        + quality_s * 0.15
        + churn_s * 0.15
        + vip_s * 0.10
    )
    score = max(0, min(100, score))

    if score >= 75:
        label, color = "Healthy", "green"
        summary = f"Customer appears satisfied. Standard follow-up is appropriate."
    elif score >= 50:
        label, color = "At Risk", "yellow"
        summary = f"Some dissatisfaction signals detected. Proactive outreach recommended."
    elif score >= 25:
        label, color = "Critical", "orange"
        summary = f"High dissatisfaction. Assign CSM immediately and prioritise resolution."
    else:
        label, color = "Red Alert", "red"
        summary = f"Severe distress signals. Escalate to senior support and executive sponsor."

    return HealthScoreResult(
        health_score=score,
        health_label=label,
        health_color=color,
        health_summary=summary,
        component_scores={
            "sentiment": sentiment_s,
            "urgency": urgency_s,
            "confidence": confidence_s,
            "quality": quality_s,
            "churn_inv": churn_s,
            "vip_factor": vip_s,
        },
    )
