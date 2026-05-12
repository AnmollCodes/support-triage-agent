"""
Configuration for the Support Triage Agent.
All tuneable parameters live here — never hardcoded in business logic.
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List


# ─────────────────────────────────────────────
# Directory layout  (relative to repo root)
# ─────────────────────────────────────────────

REPO_ROOT       = Path(__file__).parent.parent
CODE_DIR        = REPO_ROOT / "code"
DATA_DIR        = REPO_ROOT / "data"
ISSUES_DIR      = REPO_ROOT / "support_issues"

CORPUS_CACHE    = DATA_DIR / "corpus_cache.jsonl"

INPUT_CSV       = ISSUES_DIR / "support_issues.csv"
SAMPLE_CSV      = ISSUES_DIR / "sample_support_issues.csv"
OUTPUT_CSV      = ISSUES_DIR / "output.csv"


# ─────────────────────────────────────────────
# Support site URLs
# ─────────────────────────────────────────────

SUPPORT_URLS: Dict[str, str] = {
    "HackerRank": "https://support.hackerrank.com/",
    "Claude":     "https://support.claude.com/en/",
    "Visa":       "https://www.visa.co.in/support.html",
}

# Article-listing endpoints for each knowledge base
COLLECTION_URLS: Dict[str, List[str]] = {
    "HackerRank": [
        "https://support.hackerrank.com/collections/4054400338-engage-",
        "https://support.hackerrank.com/collections/1453467047-hackerrank-screen",
        "https://support.hackerrank.com/collections/3896660124-interviews",
        "https://support.hackerrank.com/collections/9492939711-chakra",
        "https://support.hackerrank.com/collections/6175643472-skillup",
        "https://support.hackerrank.com/collections/9271153455-library",
        "https://support.hackerrank.com/collections/4294572050-account-settings",
        "https://support.hackerrank.com/collections/7654924072-integrations-1",
        "https://support.hackerrank.com/collections/9278577162-general-help",
    ],
    "Claude": [
        "https://support.claude.com/en/collections/4078531-claude",
        "https://support.claude.com/en/collections/5953830-pro-and-max-plans",
        "https://support.claude.com/en/collections/9387370-team-and-enterprise-plans",
        "https://support.claude.com/en/collections/5370014-claude-api-and-console",
        "https://support.claude.com/en/collections/17270717-identity-management-sso-jit-scim",
        "https://support.claude.com/en/collections/14445694-claude-code",
        "https://support.claude.com/en/collections/16163169-claude-desktop",
        "https://support.claude.com/en/collections/9387080-claude-mobile-apps",
        "https://support.claude.com/en/collections/15399129-connectors",
        "https://support.claude.com/en/collections/18031491-claude-in-chrome",
        "https://support.claude.com/en/collections/4078534-privacy-and-legal",
        "https://support.claude.com/en/collections/4078535-safeguards",
    ],
    "Visa": [
        "https://www.visa.co.in/support.html",
        "https://www.visa.co.in/support/consumer/card-benefits.html",
        "https://www.visa.co.in/support/consumer/security.html",
        "https://www.visa.co.in/support/consumer/travel-support.html",
        "https://www.visa.co.in/support/small-business/security-fraud.html",
        "https://www.visa.co.in/support/consumer/lost-stolen-cards.html",
    ],
}


# ─────────────────────────────────────────────
# Scraping settings
# ─────────────────────────────────────────────

@dataclass
class ScraperConfig:
    max_articles_per_collection: int = 30
    max_depth: int = 2
    request_delay: float = 0.5       # seconds between requests
    timeout: float = 15.0
    max_concurrent: int = 5
    chunk_size: int = 800            # text chunk size for splitting
    user_agent: str = (
        "Mozilla/5.0 (compatible; SupportTriageBot/1.0; "
        "+https://github.com/interviewstreet/hackerrank-orchestrate-may26)"
    )
    min_content_length: int = 50     # skip pages with < N chars of text


# ─────────────────────────────────────────────
# Retrieval settings
# ─────────────────────────────────────────────

@dataclass
class RetrieverConfig:
    top_k: int = 6                   # docs to return to the agent
    bm25_weight: float = 0.7
    tfidf_weight: float = 0.3
    min_score_threshold: float = 0.01
    chunk_size: int = 800            # tokens (approx chars / 4)
    chunk_overlap: int = 100


# ─────────────────────────────────────────────
# Agent / LLM settings
# ─────────────────────────────────────────────

@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.0         # deterministic
    seed: int = 42

    # High-risk patterns that force escalation before LLM call
    escalation_keywords: list = field(default_factory=lambda: [
        "fraud", "fraudulent", "unauthorized", "stolen", "hack",
        "compromised", "account takeover", "phishing", "scam",
        "chargeback", "dispute", "legal", "lawsuit", "sue",
        "gdpr", "data breach", "leak", "lawsuit", "emergency",
        "critical security", "harassment", "discrimination",
    ])


SCRAPER_CFG   = ScraperConfig()
RETRIEVER_CFG = RetrieverConfig()
AGENT_CFG     = AgentConfig()

# Read API key from env – never hardcoded
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
