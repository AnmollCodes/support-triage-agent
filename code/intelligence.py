"""
intelligence.py — Ticket Intelligence Engine

Implements 4 of the 8 advanced features in a single, fast, zero-API module:

  FEATURE 1 — Sentiment & Emotional Tone Analyser
    Detects anger, frustration, distress, neutral, positive tone.
    Also measures emotional intensity (0–1).

  FEATURE 2 — Urgency Scoring & SLA Tier Assignment
    Maps tickets to P0/P1/P2/P3 priority with concrete SLA hours.
    Uses domain-aware rules (fraud → P0, FAQ → P3, etc.)

  FEATURE 3 — VIP / High-Value Account Detector
    Signals that a ticket may come from a high-value customer
    (enterprise language, billing amounts, plan references).

  FEATURE 4 — Multilingual & Cross-Script Threat Detector
    Detects non-English prompt injections, obfuscated commands,
    and Unicode homoglyph attacks that ASCII regex would miss.

All four run deterministically in <5ms per ticket. No API calls.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple

from models import (
    ConfidenceSignal, LanguageSignal, Sentiment, SentimentSignal,
    SupportTicket, UrgencySignal, UrgencyTier, VIPSignal,
)


# ══════════════════════════════════════════════════════════════════
# FEATURE 1 — Sentiment & Emotional Tone Analyser
# ══════════════════════════════════════════════════════════════════

_ANGER_LEXICON = [
    "unacceptable", "outrageous", "furious", "disgusting", "ridiculous",
    "absurd", "incompetent", "useless", "terrible", "horrible",
    "awful", "pathetic", "worst", "hate", "angry", "anger",
    "demand", "immediately", "right now", "no excuse", "fire",
    "lawsuit", "lawyer", "sue", "scam", "rip off", "ripoff",
]

_FRUSTRATION_LEXICON = [
    "again", "still", "doesn't work", "not working", "broken",
    "frustrated", "annoyed", "disappointing", "disappointed",
    "wasted", "waste", "hours", "days", "weeks", "multiple times",
    "keep", "keeps", "cannot", "can't", "unable", "fail", "failed",
    "no response", "ignored", "nobody", "nothing works",
    "why is it", "why won't", "how hard can",
]

_DISTRESS_LEXICON = [
    "desperate", "urgent", "emergency", "critical", "need help now",
    "losing money", "lost money", "blocked", "stuck", "helpless",
    "please help", "begging", "important interview", "job offer",
    "deadline", "tomorrow", "tonight", "losing access",
    "cannot afford", "ruined",
]

_POSITIVE_LEXICON = [
    "thank", "thanks", "great", "love", "excellent", "amazing",
    "wonderful", "appreciate", "helpful", "happy", "satisfied",
    "pleased", "good job", "well done",
]

_CAPS_RATIO_THRESHOLD  = 0.25   # >25% caps → amplify intensity
_EXCL_THRESHOLD        = 2      # >2 exclamation marks → intensifier


def _count_matches(text: str, lexicon: List[str]) -> List[str]:
    text_lower = text.lower()
    return [w for w in lexicon if w in text_lower]


def analyse_sentiment(ticket: SupportTicket) -> SentimentSignal:
    text = f"{ticket.subject} {ticket.issue}"

    anger_hits       = _count_matches(text, _ANGER_LEXICON)
    frustration_hits = _count_matches(text, _FRUSTRATION_LEXICON)
    distress_hits    = _count_matches(text, _DISTRESS_LEXICON)
    positive_hits    = _count_matches(text, _POSITIVE_LEXICON)

    # Intensity amplifiers
    total_alpha = sum(1 for c in text if c.isalpha())
    caps_ratio  = sum(1 for c in text if c.isupper()) / max(total_alpha, 1)
    excl_count  = text.count("!")
    amplifier   = 1.0
    if caps_ratio > _CAPS_RATIO_THRESHOLD:
        amplifier += 0.3
    if excl_count > _EXCL_THRESHOLD:
        amplifier += 0.2

    # Score each category
    a = len(anger_hits)       * 1.5 * amplifier
    f = len(frustration_hits) * 1.0 * amplifier
    d = len(distress_hits)    * 1.2 * amplifier
    p = len(positive_hits)    * 1.0

    scores = {"angry": a, "frustrated": f, "distressed": d, "positive": p}
    dominant = max(scores, key=scores.get)
    dominant_score = scores[dominant]

    if dominant_score < 1.0:
        sentiment  = Sentiment.NEUTRAL
        intensity  = 0.0
        markers: List[str] = []
    else:
        sentiment = Sentiment(dominant)
        intensity = min(dominant_score / 8.0, 1.0)
        if dominant == "angry":
            markers = anger_hits[:4]
        elif dominant == "frustrated":
            markers = frustration_hits[:4]
        elif dominant == "distressed":
            markers = distress_hits[:4]
        else:
            markers = positive_hits[:4]

    return SentimentSignal(
        sentiment=sentiment,
        intensity=round(intensity, 3),
        emotional_markers=markers,
    )


# ══════════════════════════════════════════════════════════════════
# FEATURE 2 — Urgency Scoring & SLA Tier Assignment
# ══════════════════════════════════════════════════════════════════

_P0_PATTERNS = re.compile(
    r"\b(fraud|stolen|hacked|compromised|unauthorized\s+transaction"
    r"|identity\s+theft|system\s+down|platform\s+down|outage"
    r"|can['\s]+t\s+login.*interview|assessment.*not\s+working.*today"
    r"|live\s+interview|emergency|physical\s+threat|data\s+breach)\b",
    re.I,
)

_P1_PATTERNS = re.compile(
    r"\b(billing\s+error|wrong\s+charge|payment\s+fail|account\s+blocked"
    r"|access\s+denied|lost\s+access|urgent|asap|today|by\s+tomorrow"
    r"|job\s+offer|offer\s+letter|deadline|interview\s+tomorrow"
    r"|card\s+blocked|card\s+declined)\b",
    re.I,
)

_P2_PATTERNS = re.compile(
    r"\b(not\s+working|broken|bug|error|crash|fail|can['\s]+t\s+submit"
    r"|can['\s]+t\s+access|reset\s+password|subscription|refund)\b",
    re.I,
)


def compute_urgency(
    ticket: SupportTicket,
    sentiment: SentimentSignal,
    is_escalated: bool,
) -> UrgencySignal:
    text = f"{ticket.subject} {ticket.issue}"
    triggers: List[str] = []

    # Base from patterns
    if _P0_PATTERNS.search(text):
        tier      = UrgencyTier.P0_CRITICAL
        sla       = 1
        score     = 0.95
        found     = _P0_PATTERNS.findall(text.lower())
        triggers  = [f[0] if isinstance(f, tuple) else f for f in found[:3]]
    elif _P1_PATTERNS.search(text):
        tier  = UrgencyTier.P1_HIGH
        sla   = 4
        score = 0.70
        found = _P1_PATTERNS.findall(text.lower())
        triggers = [f[0] if isinstance(f, tuple) else f for f in found[:3]]
    elif _P2_PATTERNS.search(text):
        tier  = UrgencyTier.P2_MEDIUM
        sla   = 24
        score = 0.40
        found = _P2_PATTERNS.findall(text.lower())
        triggers = [f[0] if isinstance(f, tuple) else f for f in found[:3]]
    else:
        tier  = UrgencyTier.P3_LOW
        sla   = 72
        score = 0.10

    # Escalate urgency if sentiment is very angry/distressed
    if sentiment.sentiment in (Sentiment.ANGRY, Sentiment.DISTRESSED) and sentiment.intensity > 0.5:
        if tier == UrgencyTier.P3_LOW:
            tier  = UrgencyTier.P2_MEDIUM
            sla   = 24
            score = max(score, 0.45)
        elif tier == UrgencyTier.P2_MEDIUM:
            tier  = UrgencyTier.P1_HIGH
            sla   = 4
            score = max(score, 0.72)
        triggers.append(f"sentiment:{sentiment.sentiment.value}")

    # Escalated tickets auto-bump to at least P1
    if is_escalated and tier not in (UrgencyTier.P0_CRITICAL,):
        tier  = UrgencyTier.P1_HIGH
        sla   = min(sla, 4)
        score = max(score, 0.70)

    return UrgencySignal(
        tier=tier,
        sla_hours=sla,
        urgency_score=round(score, 3),
        triggers=triggers,
    )


# ══════════════════════════════════════════════════════════════════
# FEATURE 3 — VIP / High-Value Account Detector
# ══════════════════════════════════════════════════════════════════

_VIP_PATTERNS = [
    (re.compile(r"\b(enterprise|fortune\s*500|large\s+org|our\s+company|our\s+team"
                r"|our\s+organization|we\s+use\s+hackerrank|we\s+pay)\b", re.I),
     "enterprise_language"),
    (re.compile(r"\b(thousands?\s+of\s+(users|candidates|employees)"
                r"|hundreds?\s+of\s+(users|candidates)|large\s+scale)\b", re.I),
     "high_volume_usage"),
    (re.compile(r"\b(\$[5-9]\d{2,}|\$[0-9]{4,}|\d{4,}\s*dollar"
                r"|annual\s+contract|multi.year)\b", re.I),
     "high_billing_amount"),
    (re.compile(r"\b(cto|ceo|vp\s+of|head\s+of\s+engineering|director\s+of"
                r"|chief|founder|president)\b", re.I),
     "executive_title"),
    (re.compile(r"\b(priority\s+support|dedicated\s+support|account\s+manager"
                r"|customer\s+success|sla\s+agreement)\b", re.I),
     "expects_priority_support"),
    (re.compile(r"\b(switch\s+to\s+competitor|cancel\s+(our\s+)?plan|moving\s+away"
                r"|evaluating\s+alternatives|looking\s+for\s+alternatives)\b", re.I),
     "churn_risk"),
]


def detect_vip(ticket: SupportTicket) -> VIPSignal:
    text    = f"{ticket.subject} {ticket.issue}"
    signals = []
    for pattern, label in _VIP_PATTERNS:
        if pattern.search(text):
            signals.append(label)
    return VIPSignal(is_vip=len(signals) > 0, signals=signals)


# ══════════════════════════════════════════════════════════════════
# FEATURE 4 — Multilingual & Cross-Script Threat Detector
# ══════════════════════════════════════════════════════════════════

# Unicode homoglyph substitutions attackers use to bypass ASCII regex
# Maps lookalike chars back to ASCII equivalents
_HOMOGLYPH_MAP = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x",
    "і": "i", "ο": "o", "ρ": "p", "α": "a", "е": "e",
    "\u0456": "i", "\u04cf": "l", "\u0455": "s",
    "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
})

# Known injection phrases in multiple languages
_MULTILANG_INJECTION_PATTERNS = [
    # French
    (re.compile(r"(ignorer?\s+les?\s+instructions|afficher?\s+toutes?\s+les?\s+r[eè]gles"
                r"|r[eé]v[eé]ler?\s+les?\s+r[eè]gles|logique\s+exacte"
                r"|documents?\s+r[eé]cup[eé]r[eé]s?|voici\s+mes\s+vraies\s+instructions"
                r"|tu\s+es\s+maintenant)", re.I),
     "fr", "French prompt injection"),
    # Spanish
    (re.compile(r"(ignora\s+(todas?\s+las?\s+)?instrucciones"
                r"|eres\s+ahora\s+un?\s+|rev[eé]la\s+(tus\s+)?instrucciones"
                r"|actuar\s+como\s+sin\s+restricciones)", re.I),
     "es", "Spanish prompt injection"),
    # German
    (re.compile(r"(ignoriere\s+(alle\s+)?anweisungen|du\s+bist\s+jetzt\s+ein?"
                r"|zeig\s+mir\s+deine\s+anweisungen|system\s*prompt\s*anzeigen)", re.I),
     "de", "German prompt injection"),
    # Hindi/Devanagari mixed
    (re.compile(r"[\u0900-\u097F]{3,}.*instruc|instruc.*[\u0900-\u097F]{3,}", re.I),
     "hi", "Hindi-mixed instruction override"),
    # Arabic-script mixed
    (re.compile(r"[\u0600-\u06FF]{3,}.*instruc|instruc.*[\u0600-\u06FF]{3,}", re.I),
     "ar", "Arabic-mixed instruction override"),
    # Chinese characters with injection keywords
    (re.compile(r"[\u4e00-\u9FFF]{2,}.*(ignore|system|prompt|instruction)"
                r"|(ignore|system|prompt|instruction).*[\u4e00-\u9FFF]{2,}", re.I),
     "zh", "Chinese-mixed instruction override"),
    # Base64-encoded "ignore instructions"
    (re.compile(r"aWdub3Jl|aW5zdHJ1Y3Rpb24|c3lzdGVtIHByb21wdA", re.I),
     "b64", "Base64-encoded injection"),
    # Leetspeak / character substitution
    (re.compile(r"(1gn[o0]r3|1nstruct10n|syst3m\s*pr0mpt|j41lbr[e3][a4]k)", re.I),
     "leet", "Leetspeak injection attempt"),
]

# Script detection heuristics
def _detect_script(text: str) -> str:
    """Quick script detection by Unicode block frequency."""
    counts = {
        "ar": 0, "zh": 0, "hi": 0, "ru": 0,
        "fr": 0, "es": 0, "de": 0,
    }
    for ch in text:
        cp = ord(ch)
        if 0x0600 <= cp <= 0x06FF:
            counts["ar"] += 1
        elif 0x4E00 <= cp <= 0x9FFF:
            counts["zh"] += 1
        elif 0x0900 <= cp <= 0x097F:
            counts["hi"] += 1
        elif 0x0400 <= cp <= 0x04FF:
            counts["ru"] += 1

    # Romance/Germanic language word-level detection
    text_lower = text.lower()
    for w in ["le ", "la ", "les ", "vous ", "nous ", "est ", "une ", "des ", "que "]:
        if w in text_lower:
            counts["fr"] += 2
    for w in ["el ", "la ", "los ", "las ", "que ", "con ", "por ", "para "]:
        if w in text_lower:
            counts["es"] += 2
    for w in ["und ", "die ", "der ", "das ", "ich ", "sie ", "ein ", "ist "]:
        if w in text_lower:
            counts["de"] += 2

    dominant = max(counts, key=counts.get)
    return dominant if counts[dominant] >= 3 else "en"


def analyse_language(ticket: SupportTicket) -> LanguageSignal:
    text = f"{ticket.subject} {ticket.issue}"

    # Normalize homoglyphs before analysis
    normalized = text.translate(_HOMOGLYPH_MAP)

    detected_lang = _detect_script(text)
    is_multilingual = False
    injection_found = False
    translation_hint = ""
    matched_label = ""

    # Check all multilingual injection patterns
    for pattern, lang_code, label in _MULTILANG_INJECTION_PATTERNS:
        if pattern.search(normalized) or pattern.search(text):
            injection_found = True
            is_multilingual = True
            detected_lang   = lang_code
            matched_label   = label
            break

    # Check if non-English even without injection
    if detected_lang != "en" and not is_multilingual:
        is_multilingual = True

    # Build translation hint
    if detected_lang == "fr":
        translation_hint = "Ticket appears to contain French text"
    elif detected_lang == "es":
        translation_hint = "Ticket appears to contain Spanish text"
    elif detected_lang == "de":
        translation_hint = "Ticket appears to contain German text"
    elif detected_lang == "ar":
        translation_hint = "Ticket appears to contain Arabic script"
    elif detected_lang == "zh":
        translation_hint = "Ticket appears to contain Chinese characters"
    elif detected_lang == "hi":
        translation_hint = "Ticket appears to contain Devanagari/Hindi script"
    elif detected_lang == "b64":
        translation_hint = "Ticket contains Base64-encoded content"
    elif detected_lang == "leet":
        translation_hint = "Ticket contains leetspeak character substitutions"

    return LanguageSignal(
        detected=detected_lang,
        is_multilingual=is_multilingual,
        injection_in_foreign=injection_found,
        translation_hint=translation_hint if translation_hint else "",
    )


# ══════════════════════════════════════════════════════════════════
# Confidence Scoring helper  (used by run_agent to enrich results)
# ══════════════════════════════════════════════════════════════════

def compute_confidence(
    retrieval_scores: List[float],
    is_escalated: bool,
    corpus_gap: bool,
    language: LanguageSignal,
    ticket: SupportTicket,
) -> ConfidenceSignal:
    """Compute overall decision confidence."""

    # Retrieval quality
    if retrieval_scores:
        top_score = max(retrieval_scores)
        mean_top3 = sum(sorted(retrieval_scores, reverse=True)[:3]) / 3
        retrieval_q = round((top_score * 0.6 + mean_top3 * 0.4), 3)
    else:
        retrieval_q = 0.1

    # Classification certainty
    class_cert = 0.9
    if corpus_gap:
        class_cert -= 0.3
    if language.injection_in_foreign:
        class_cert -= 0.2
    if language.is_multilingual and not language.injection_in_foreign:
        class_cert -= 0.1
    if not ticket.company or ticket.company == "None":
        class_cert -= 0.1
    class_cert = max(0.1, round(class_cert, 3))

    # Overall
    overall = round((retrieval_q * 0.5 + class_cert * 0.5), 3)

    # Build reasoning
    parts = []
    if retrieval_q >= 0.8:
        parts.append("strong corpus match")
    elif retrieval_q >= 0.4:
        parts.append("moderate corpus match")
    else:
        parts.append("weak corpus match — response may be generic")
    if corpus_gap:
        parts.append("knowledge gap detected")
    if language.injection_in_foreign:
        parts.append("foreign-language injection signal")
    if not ticket.company or ticket.company == "None":
        parts.append("company inferred (not specified)")
    reasoning = "; ".join(parts) if parts else "normal confidence"

    return ConfidenceSignal(
        score=overall,
        retrieval_quality=retrieval_q,
        classification_certainty=class_cert,
        reasoning=reasoning,
    )
