"""
Pydantic data models for the Support Triage Agent.
Extended with full intelligence layer for all 8 advanced features.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class TicketStatus(str, Enum):
    REPLIED   = "replied"
    ESCALATED = "escalated"


class RequestType(str, Enum):
    PRODUCT_ISSUE    = "product_issue"
    FEATURE_REQUEST  = "feature_request"
    BUG              = "bug"
    INVALID          = "invalid"


class Company(str, Enum):
    HACKERRANK = "HackerRank"
    CLAUDE     = "Claude"
    VISA       = "Visa"
    NONE       = "None"


class UrgencyTier(str, Enum):
    P0_CRITICAL = "P0_Critical"
    P1_HIGH     = "P1_High"
    P2_MEDIUM   = "P2_Medium"
    P3_LOW      = "P3_Low"


class Sentiment(str, Enum):
    ANGRY      = "angry"
    FRUSTRATED = "frustrated"
    DISTRESSED = "distressed"
    NEUTRAL    = "neutral"
    POSITIVE   = "positive"


class IncidentSeverity(str, Enum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"


class SupportTicket(BaseModel):
    issue:   str
    subject: str = ""
    company: str = "None"

    @validator("subject", "company", pre=True, always=True)
    def coerce_none_str(cls, v):
        if v is None or isinstance(v, float):
            return ""
        return str(v).strip()

    @validator("issue", pre=True, always=True)
    def coerce_issue(cls, v):
        if v is None:
            return ""
        return str(v).strip()


class CorpusChunk(BaseModel):
    source:  str
    url:     str
    title:   str
    content: str
    section: str = ""

    @property
    def full_text(self) -> str:
        parts = [self.title]
        if self.section:
            parts.append(self.section)
        parts.append(self.content)
        return " ".join(parts)


class RetrievedDoc(BaseModel):
    chunk: CorpusChunk
    score: float


class AgentDecision(BaseModel):
    status:            str
    product_area:      str
    response:          str
    justification:     str
    request_type:      str
    escalation_reason: Optional[str] = None


class SentimentSignal(BaseModel):
    sentiment:         Sentiment = Sentiment.NEUTRAL
    intensity:         float = 0.0
    emotional_markers: List[str] = Field(default_factory=list)


class UrgencySignal(BaseModel):
    tier:          UrgencyTier = UrgencyTier.P3_LOW
    sla_hours:     int = 72
    urgency_score: float = 0.0
    triggers:      List[str] = Field(default_factory=list)


class ConfidenceSignal(BaseModel):
    score:                    float = 1.0
    retrieval_quality:        float = 1.0
    classification_certainty: float = 1.0
    reasoning:                str = ""


class LanguageSignal(BaseModel):
    detected:              str = "en"
    is_multilingual:       bool = False
    injection_in_foreign:  bool = False
    translation_hint:      str = ""


class CorpusGapSignal(BaseModel):
    gap_detected:        bool = False
    max_retrieval_score: float = 0.0
    gap_description:     str = ""
    suggested_doc_title: str = ""


class QualitySignal(BaseModel):
    score:                float = 1.0
    answers_the_question: bool = True
    is_grounded:          bool = True
    issues:               List[str] = Field(default_factory=list)
    follow_up_questions:  List[str] = Field(default_factory=list)


class VIPSignal(BaseModel):
    is_vip:  bool = False
    signals: List[str] = Field(default_factory=list)


class TriageResult(BaseModel):
    # Required outputs
    status:        TicketStatus
    product_area:  str
    response:      str
    justification: str
    request_type:  RequestType

    # Intelligence layer
    sentiment:           SentimentSignal  = Field(default_factory=SentimentSignal)
    urgency:             UrgencySignal    = Field(default_factory=UrgencySignal)
    confidence:          ConfidenceSignal = Field(default_factory=ConfidenceSignal)
    language:            LanguageSignal   = Field(default_factory=LanguageSignal)
    corpus_gap:          CorpusGapSignal  = Field(default_factory=CorpusGapSignal)
    quality:             QualitySignal    = Field(default_factory=QualitySignal)
    vip:                 VIPSignal        = Field(default_factory=VIPSignal)
    incident_cluster_id: Optional[str]   = None


class IncidentReport(BaseModel):
    cluster_id:           str
    title:                str
    ticket_indices:       List[int]
    company:              str
    product_area:         str
    severity:             IncidentSeverity
    ticket_count:         int
    summary:              str
    common_symptoms:      List[str]
    recommended_action:   str
    auto_response_draft:  str
