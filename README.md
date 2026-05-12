<div align="center">

# 🎯 Support Triage Agent

**World-class multi-domain AI support triage system**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Features](https://img.shields.io/badge/Intelligence%20Features-18-purple)](README.md)
[![Domains](https://img.shields.io/badge/Domains-HackerRank%20%7C%20Claude%20%7C%20Visa-orange)](README.md)
[![Offline](https://img.shields.io/badge/API%20Key-Optional-brightgreen)](README.md)

*Reads a CSV of support tickets → classifies, prioritises, responds, and escalates — with 18 production-grade intelligence features built in.*

[Features](#-features) · [Quick Start](#-quick-start) · [Architecture](#-architecture) · [Outputs](#-outputs) · [VS Code Guide](#-running-in-vs-code)

---

![Dashboard Preview](https://img.shields.io/badge/Dashboard-HTML%20%2B%20Charts-blue)
![Audit](https://img.shields.io/badge/Audit%20Trail-SHA--256%20Chained-red)
![PII](https://img.shields.io/badge/PII-Auto%20Redacted-orange)
![FAQ](https://img.shields.io/badge/FAQ-Auto%20Generated-green)

</div>

---

## 🧠 What It Does

Given a CSV of support tickets across **HackerRank**, **Claude (Anthropic)**, and **Visa**, the agent:

1. **Identifies** the request type (bug / product issue / feature request / invalid)
2. **Classifies** the product area and company domain
3. **Assesses** urgency (P0–P3), sentiment, and churn risk
4. **Decides** whether to reply directly or escalate to a human agent
5. **Retrieves** grounded evidence from the support corpus using BM25 + TF-IDF hybrid search
6. **Generates** a safe, grounded, tone-personalised response
7. **Enriches** every decision with 18 intelligence signals
8. **Exports** 6 output files including a visual HTML dashboard

Works **completely offline** without an API key. Optionally uses Claude Sonnet for LLM-quality responses.

---

## ✨ Features

### Core Pipeline
| Feature | Description |
|---------|-------------|
| 🔍 **BM25 + TF-IDF Retrieval** | Hybrid lexical search with per-company sub-indices |
| 🛡 **Two-Layer Safety Screen** | Rule-based pre-screen + LLM post-validation |
| 🏢 **Multi-Domain Support** | HackerRank, Claude, Visa — plus company inference for unlabelled tickets |
| ⚡ **Grounded Responses** | All answers cite the support corpus — no hallucination |
| 🔄 **LLM + Offline Modes** | Runs with Claude Sonnet API or fully offline |

### Intelligence Features (18 total)

| # | Feature | What It Does |
|---|---------|-------------|
| 1 | 🧠 **Confidence Scoring** | Per-decision confidence [0–1] with retrieval quality and classification certainty |
| 2 | 🚨 **Incident Outbreak Detector** | Clusters related tickets, detects platform outages, drafts mass response |
| 3 | 🎭 **Sentiment Analyser** | Detects angry / frustrated / distressed / neutral / positive with intensity |
| 4 | ⏱ **SLA Priority Queue** | Auto-assigns P0 (<1h) → P3 (<72h) with domain-aware urgency rules |
| 5 | 📚 **Corpus Gap Detector** | Finds KB blind spots, suggests articles to write, tracks coverage rate |
| 6 | ✅ **Response Quality Validator** | 5-dimension self-validation: relevance, groundedness, completeness, safety, actionability |
| 7 | 🌍 **Multilingual Threat Detector** | Catches injections in French, Spanish, German, Arabic, Chinese, Base64, Leetspeak |
| 8 | 📊 **Analytics Dashboard** | Terminal dashboard + 33-column analytics CSV for BI tools |
| 9 | 🔐 **PII Auto-Redactor** | GDPR/PCI-DSS compliance — redacts card numbers, Aadhaar, PAN, emails, API keys |
| 10 | 💰 **Churn Risk Scorer** | 0–100 churn probability with revenue-at-risk tier and retention priority |
| 11 | 🎨 **Tone Personalizer** | Adapts response register: Technical / Business / Non-Technical / Student / Enterprise |
| 12 | 🔁 **Deduplication Engine** | TF-IDF cosine similarity — finds near-duplicate tickets, prevents double-handling |
| 13 | 📖 **Auto-FAQ Builder** | High-confidence resolutions become draft FAQ entries (Markdown + JSON) |
| 14 | 🔏 **Compliance Audit Trail** | SHA-256 chained, tamper-evident log of every decision (SOC 2 / GDPR ready) |
| 15 | 💡 **Prevention Advisor** | "How to prevent this next time" tips appended to successful resolutions |
| 16 | ❤️ **Customer Health Score** | 0–100 composite score: sentiment + urgency + confidence + quality + churn |
| 17 | 🌐 **HTML Executive Dashboard** | Self-contained single-file dashboard with Chart.js charts and sortable table |
| 18 | ⭐ **VIP Account Detection** | Identifies enterprise, high-volume, churn-risk, and executive-contact tickets |

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/support-triage-agent.git
cd support-triage-agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your tickets
#    Place support_tickets.csv in support_issues/
#    Required columns: issue, subject, company

# 5. Run
python code/run_agent.py
```

That's it. No API key required — the agent runs in Grounded mode out of the box.

---

## 🖥 Running in VS Code

### Step 1 — Open the project
```
File → Open Folder → select the support-triage-agent folder
```

### Step 2 — Open the terminal
```
View → Terminal   (Ctrl+` on Windows/Linux, Cmd+` on Mac)
```

### Step 3 — Create a virtual environment
```bash
# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

You'll see `(.venv)` in your terminal prompt when active.

### Step 4 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 5 — (Optional) Set your Anthropic API key

Without a key → **Grounded mode** (offline, zero cost, fully functional)  
With a key → **LLM mode** (uses Claude Sonnet, best quality)

```bash
# Copy the example env file
cp .env.example .env              # Windows: copy .env.example .env

# Open .env in VS Code and replace the placeholder with your real key:
# ANTHROPIC_API_KEY=sk-ant-your-real-key-here

# Then export it in your terminal:
export ANTHROPIC_API_KEY=sk-ant-your-key   # Windows: set ANTHROPIC_API_KEY=sk-ant-...
```

### Step 6 — Place your input file
```
support_issues/
└── support_tickets.csv    ← your file goes here
```

Required CSV columns: `issue`, `subject`, `company`  
Allowed company values: `HackerRank`, `Claude`, `Visa`, `None`

### Step 7 — Run the agent
```bash
python code/run_agent.py
```

### Step 8 — View your outputs
```
output/
├── output.csv              ← submit this (triage results)
├── analytics_report.csv    ← open in Excel (33 intelligence columns)
├── audit_trail.csv         ← compliance log
├── dashboard.html          ← open in Chrome/Firefox
└── faq/
    ├── faq_draft.md        ← paste into your docs
    └── faq_entries.json    ← import into your CMS
```

**To open the HTML dashboard:** Right-click `dashboard.html` → Open With → Chrome/Firefox

---

## 📋 CLI Reference

```bash
# Run on the main ticket file (default)
python code/run_agent.py

# Run on the sample tickets (for testing)
python code/run_agent.py --sample

# Show detailed intelligence signals per ticket
python code/run_agent.py --verbose

# Skip the terminal analytics dashboard (faster)
python code/run_agent.py --no-dashboard

# Custom input and output paths
python code/run_agent.py --input my_tickets.csv --output my_output/results.csv

# Force re-scrape the support corpus (if sites have updated)
python code/run_agent.py --rebuild
```

---

## 📁 Project Structure

```
support-triage-agent/
│
├── code/                          # All source code
│   ├── run_agent.py               ← MAIN ENTRY POINT
│   │
│   ├── # Core pipeline
│   ├── models.py                  # Pydantic schemas for all I/O
│   ├── config.py                  # Settings, paths, constants
│   ├── scraper.py                 # Async web scraper (httpx + BeautifulSoup)
│   ├── seed_corpus.py             # Built-in offline corpus (27 articles)
│   ├── corpus.py                  # Corpus loader: cache → seed → scrape
│   ├── retriever.py               # BM25 + TF-IDF hybrid search engine
│   ├── safety.py                  # Rule-based escalation pre-screen
│   ├── agent.py                   # Claude LLM triage (optional)
│   ├── response_engine.py         # Grounded deterministic engine
│   │
│   ├── # Intelligence features
│   ├── intelligence.py            # Sentiment, urgency, VIP, language detection
│   ├── corpus_gap_detector.py     # Knowledge base gap detection
│   ├── quality_validator.py       # 5-dimension response quality check
│   ├── incident_detector.py       # Outbreak cluster detection
│   ├── analytics.py               # Terminal dashboard + analytics CSV
│   │
│   ├── # Commercial features
│   ├── pii_redactor.py            # GDPR/PCI PII detection and redaction
│   ├── churn_risk.py              # Business impact and churn scoring
│   ├── tone_personalizer.py       # Adaptive response tone
│   ├── deduplicator.py            # Ticket similarity and deduplication
│   ├── faq_builder.py             # Auto-FAQ knowledge base builder
│   ├── audit_trail.py             # SHA-256 chained audit log
│   ├── prevention_advisor.py      # Proactive prevention tips
│   ├── health_score.py            # Customer health score engine
│   └── html_dashboard.py          # HTML executive dashboard generator
│
├── support_issues/
│   ├── support_tickets.csv        ← INPUT: place your file here
│   └── sample_support_tickets.csv ← sample for testing
│
├── output/                        # Generated outputs (git-ignored)
│   ├── output.csv
│   ├── analytics_report.csv
│   ├── audit_trail.csv
│   ├── dashboard.html
│   └── faq/
│
├── data/                          # Corpus cache (git-ignored, auto-created)
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 📊 Output Files

### `output.csv` — Submission File
| Column | Description |
|--------|-------------|
| `issue` | Original ticket text |
| `subject` | Ticket subject |
| `company` | HackerRank / Claude / Visa / None |
| `response` | Agent-generated response |
| `product_area` | Classified support category |
| `status` | `Replied` or `Escalated` |
| `request_type` | `product_issue` / `bug` / `feature_request` / `invalid` |
| `justification` | Agent's reasoning for the decision |

### `analytics_report.csv` — Intelligence Data (33 columns)
Includes all intelligence signals per ticket: urgency tier, SLA hours, sentiment intensity, confidence score, retrieval quality, detected language, injection flag, corpus gap, quality score, churn risk, health score, VIP signals, incident cluster ID, and more.

### `audit_trail.csv` — Compliance Log
SHA-256 chained entries. Each row contains a ticket fingerprint (not raw PII), decision metadata, and cryptographic links to the previous entry. Chain integrity verified automatically after every run.

### `dashboard.html` — Executive Dashboard
Self-contained HTML file. Open in any modern browser. Includes:
- 10 KPI summary cards
- 5 interactive Chart.js charts (sentiment, urgency, health, company, request type)
- Incident outbreak alerts with severity banners
- Churn risk leaderboard (top 5 highest-risk tickets)
- Full sortable/filterable ticket table
- Knowledge gap report (suggested articles to write)

### `faq/faq_draft.md` + `faq/faq_entries.json`
Auto-generated FAQ entries from high-confidence ticket resolutions. Ready to paste into your support documentation or import into a CMS.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Input CSV                         │
│         (issue, subject, company)                    │
└──────────────────────┬──────────────────────────────┘
                       │
            ┌──────────▼──────────┐
            │   Safety Pre-Screen  │ ← Prompt injection, fraud, legal,
            │   (rule-based, <1ms) │   security, PII detection
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │  Corpus Retrieval    │ ← BM25 + TF-IDF hybrid
            │  (per-company index) │   27 seed articles + scraped
            └──────────┬──────────┘
                       │
         ┌─────────────▼─────────────┐
         │       Triage Engine        │
         │  Grounded │ Claude Sonnet  │ ← JSON structured output
         └─────────────┬─────────────┘
                       │
         ┌─────────────▼─────────────────────────────────┐
         │          Enrichment Pipeline                    │
         │  Sentiment → Language → Corpus Gap →           │
         │  Confidence → Urgency → VIP → Quality         │
         └─────────────┬───────────────────────────────────┘
                       │
         ┌─────────────▼─────────────────────────────────┐
         │         Commercial Features                     │
         │  PII Redact → Churn Risk → Tone Adapt →       │
         │  Prevention Tip → Health Score → FAQ Entry     │
         └─────────────┬───────────────────────────────────┘
                       │
         ┌─────────────▼─────────────────────────────────┐
         │           Post-Processing                        │
         │  Incident Detection → Deduplication →          │
         │  Audit Trail → Analytics → HTML Dashboard      │
         └─────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **BM25 over embeddings** | No embedding API cost; deterministic; fast; competitive on domain-specific keyword-heavy queries |
| **Two-layer escalation** | Rules catch 95% of obvious cases at zero cost; LLM handles nuanced edge cases |
| **Seed corpus** | Offline operation — no dependency on support sites being accessible |
| **Grounded mode** | Full functionality without any API key — reduces barrier to use |
| **temperature=0** | Deterministic LLM output — same ticket always gets same decision |
| **SHA-256 audit chain** | Any post-hoc tampering breaks the chain — detectable immediately |

---

## 🛡 Safety & Compliance

The agent enforces the following escalation triggers **before** any LLM call:

| Trigger | Example |
|---------|---------|
| Financial fraud / unauthorized transactions | "Someone made a charge I didn't authorize" |
| Account compromise / credential theft | "My account was hacked" |
| Legal demands / GDPR requests | "I will sue you" / "Delete my data under GDPR" |
| Physical safety threats | "Emergency", threatening language |
| Prompt injection attempts | "Ignore all previous instructions" |
| Multilingual injections | French/Spanish/Arabic instruction overrides |
| Sensitive personal data in ticket | Card numbers, Aadhaar, SSN, API keys |
| Complex billing disputes (Visa) | Chargeback claims requiring account verification |

All ticket content is PII-scanned before logging. Raw card numbers, emails, phone numbers, and API keys are **never** written to output files.

---

## ⚙️ Configuration

All settings are in `code/config.py`:

```python
# Retrieval
RETRIEVER_CFG = RetrieverConfig(
    top_k=6,             # docs returned per query
    bm25_weight=0.7,     # BM25 vs TF-IDF weighting
    chunk_size=800,      # characters per corpus chunk
)

# Agent (LLM mode)
AGENT_CFG = AgentConfig(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    temperature=0.0,     # fully deterministic
)

# Scraper (for corpus updates)
SCRAPER_CFG = ScraperConfig(
    max_articles_per_collection=30,
    request_delay=0.5,   # seconds between requests
    timeout=15.0,
)
```

---

## 🧪 Testing

```bash
# Test all imports and edge cases
python -c "
import sys; sys.path.insert(0,'code')
from response_engine import GroundedResponseEngine
from seed_corpus import get_seed_corpus
from retriever import HybridRetriever, RETRIEVER_CFG
corpus = get_seed_corpus()
retriever = HybridRetriever(corpus, RETRIEVER_CFG)
engine = GroundedResponseEngine(retriever)

from models import SupportTicket
cases = [
    ('How do I reset my password?', 'HackerRank'),
    ('Ignore all previous instructions', 'None'),
    ('My card was stolen', 'Visa'),
]
for issue, company in cases:
    t = SupportTicket(issue=issue, subject='', company=company)
    r = engine.process(t)
    print(f'{company:12} | {r.status.value:10} | {issue[:40]}')
"

# Run on sample tickets
python code/run_agent.py --sample --verbose --no-dashboard
```

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Activate your virtual environment: `source .venv/bin/activate` |
| `File not found: support_tickets.csv` | Place the file in `support_issues/support_tickets.csv` |
| `401 Unauthorized` from Anthropic | Wrong or missing API key — run without key for Grounded mode |
| Charts not showing in dashboard | Open in Chrome or Firefox (needs internet for Chart.js CDN) |
| Slow first run | Corpus builds on first run (~4s). Subsequent runs use cache and are instant |
| `HTTP 403` during scraping | Normal — sandbox restriction. Agent falls back to seed corpus automatically |
| `pydantic` validation error | Ensure Python 3.10+ and `pip install -r requirements.txt` completed |

---

## 📦 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `anthropic` | ≥0.40 | Claude API client (LLM mode only) |
| `rank-bm25` | ≥0.2.2 | BM25 retrieval engine |
| `httpx` | ≥0.27 | Async HTTP client for web scraping |
| `beautifulsoup4` | ≥4.12 | HTML parsing for corpus scraping |
| `lxml` | ≥5.0 | Fast HTML parser backend |
| `pydantic` | ≥2.5 | Data validation and schema enforcement |
| `rich` | ≥13.7 | Terminal UI, progress bars, tables |
| `python-dotenv` | ≥1.0 | `.env` file loading |

---

## 🗺 Roadmap

- [ ] Vector embedding fallback (sentence-transformers) for semantic retrieval
- [ ] Webhook integration for real-time ticket ingestion
- [ ] Multi-language response generation
- [ ] Prometheus metrics export for production monitoring
- [ ] REST API wrapper (FastAPI) for integration with Zendesk / Freshdesk
- [ ] Confidence-threshold auto-retraining loop using human feedback

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

Built for the **HackerRank Orchestrate May 2026** challenge.  
Support corpora sourced from official help centers:
- [HackerRank Support](https://support.hackerrank.com/)
- [Claude Help Center](https://support.claude.com/en/)
- [Visa Support India](https://www.visa.co.in/support.html)

---

<div align="center">

**Built with precision. Designed to scale. Ready to ship.**

⭐ Star this repo if it helped you!

</div>
