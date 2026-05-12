# Support Triage Agent — Code README

## Architecture

```
code/
├── main.py        # CLI entry point (argparse + Rich terminal UI)
├── agent.py       # Core TriageAgent: orchestrates retrieval → LLM → output
├── scraper.py     # Async web scraper (httpx + BeautifulSoup) for 3 corpora
├── retriever.py   # Hybrid BM25 + TF-IDF retrieval engine
├── safety.py      # Rule-based safety/escalation pre-screen
├── models.py      # Pydantic schemas (SupportTicket, TriageResult, CorpusChunk…)
├── config.py      # All tuneable settings, directory paths
└── README.md      # This file
```

### Design decisions

| Layer | Choice | Why |
|-------|--------|-----|
| Corpus retrieval | BM25 (rank_bm25) + TF-IDF | No embedding API cost; deterministic; fast; competitive with dense retrieval for domain-specific keyword-heavy queries |
| LLM | Claude claude-sonnet-4-20250514 | Best balance of reasoning quality, speed, and JSON adherence |
| Escalation | Two-layer: rule-based pre-screen → LLM judgment | Rules catch obvious high-risk cases at zero cost; LLM catches nuanced ones |
| Output parsing | Regex + json.loads with tolerant fallback | LLMs occasionally wrap JSON in fences; robust parsing prevents data loss |
| Rate limiting | Exponential back-off (3 retries) | Handles API 429/529 gracefully |
| Corpus caching | JSONL file in data/ | Re-scraping on every run would be slow and discourteous to the servers |

---

## Installation

### Requirements
- Python 3.10+
- `pip` (or `uv` / `poetry`)

### Steps

```bash
# 1. Clone and enter the repo
git clone git@github.com:interviewstreet/hackerrank-orchestrate-may26.git
cd hackerrank-orchestrate-may26

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r code/requirements.txt

# 4. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."
# Or copy .env.example → .env and fill it in (python-dotenv is supported)
```

---

## Usage

```bash
# Run on the full test set (writes to support_issues/output.csv)
python code/main.py

# Run on the sample file (to verify expected outputs)
python code/main.py --sample

# Verbose: see every ticket + retrieved docs
python code/main.py --verbose

# Force re-scrape the support corpus (e.g. after support sites update)
python code/main.py --rebuild

# Dry-run: process only the first ticket, no CSV written
python code/main.py --dry-run --verbose

# Process a specific ticket (0-indexed)
python code/main.py --ticket 5 --verbose

# Custom paths
python code/main.py --input /path/to/input.csv --output /path/to/output.csv
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Anthropic API key for Claude claude-sonnet-4-20250514 |

---

## Dependencies

See `requirements.txt`. Key packages:

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude API client |
| `rank_bm25` | BM25 retrieval |
| `httpx` | Async HTTP for scraping |
| `beautifulsoup4` | HTML parsing |
| `pydantic` | Data validation |
| `rich` | Terminal UI |
| `lxml` | Fast HTML parser |

---

## Corpus

The agent builds a local corpus by scraping the three official knowledge bases:
- **HackerRank**: https://support.hackerrank.com/ (9 collections)
- **Claude**: https://support.claude.com/en/ (12 collections)
- **Visa**: https://www.visa.co.in/support.html (6 pages)

The scraped corpus is cached at `data/corpus_cache.jsonl`. Delete this file
and re-run with `--rebuild` if the support sites have been updated.

---

## Escalation logic

The agent escalates (rather than replies) when:

1. **Rule-based (pre-LLM)**: fraud, account compromise, legal requests, safety threats, prompt injection, sensitive data, complex billing disputes.
2. **LLM-based (post-generation)**: Claude flags a case as high-risk via the `escalation_reason` field in its JSON output.

The two-layer approach ensures zero-cost fast handling for obvious cases while using LLM judgment for nuanced edge cases.

---

## Determinism

- `temperature=0.0` on all LLM calls
- BM25 and TF-IDF are deterministic
- Python's `random` is not used (no seeding needed)

---

## Known limitations / failure modes

1. **Corpus coverage gaps**: If a ticket asks about a topic not in the scraped docs, the LLM may produce a thin response. Mitigation: escalate when retrieval score is below threshold.
2. **Visa page structure**: visa.co.in uses minimal structured HTML; some content may be missed. Mitigation: scrape multiple Visa sub-pages.
3. **Rate limits**: Anthropic API limits may slow large batches. Mitigation: exponential back-off with 3 retries.
4. **Language**: Only English tickets are handled well. Non-English tickets should be escalated.
