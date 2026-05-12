# 🚀 Deployment & Setup Guide

## Prerequisites

- **OS**: Windows, macOS, or Linux
- **Python**: 3.10 or higher
- **Disk Space**: 200 MB (code + corpus + outputs)
- **RAM**: 512 MB minimum (1 GB recommended)
- **Internet**: Required only for corpus scraping (first run)

---

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/AnmollCodes/support-triage-agent.git
cd support-triage-agent
```

### Step 2: Create Virtual Environment

**On Windows:**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**What gets installed:**
```
anthropic>=0.40.0         # Claude API client (optional)
httpx>=0.27.0             # HTTP client for scraping
beautifulsoup4>=4.12.0    # HTML parsing
lxml>=5.0.0               # XML/HTML parser (faster)
rank-bm25>=0.2.2          # BM25 ranking algorithm
pydantic>=2.5.0           # Data validation
rich>=13.7.0              # Rich terminal output
python-dotenv>=1.0.0      # Environment config
```

---

## Running the Agent

### Grounded Mode (Offline, No API Key)

```bash
python code/run_agent.py
```

**Output:**
```
───────────────   Support Triage Agent  ·  World-Class Edition   ───────────────
  HackerRank · Claude · Visa  |  18 intelligence features

1/5  Knowledge Corpus
  ✓ Built corpus: 27 chunks (0 scraped + 27 seed) in 10.9s

2/5  Retrieval Index (BM25 + TF-IDF)
  ✓ Index ready in 0.00s

3/5  Loading Tickets (support_tickets.csv)
  ✓ 29 tickets loaded

4/5  Triaging
    #  Status      Priority      Sentiment     Conf   Qual   Health  Churn    
Issue
  ─────────────────────────────────────────────────────────────────────────────
    1  ✓ replied   P1_High      angry        0.89  1.00   54     30  I lost...
    2  ✓ replied   P3_Low       neutral      0.91  0.90   87      0  I completed...
    ...
    29 ✓ replied   P3_Low       neutral      0.92  1.00   88      0  i am a...

5/5  Outputs
  ✓ output.csv (full decision log)
  ✓ analytics_report.csv (summary statistics)
  ✓ audit_trail.csv (SOC 2 compliance log)
  ✓ faq_entries.json (auto-generated FAQ)
  ✓ dashboard.html (interactive dashboard)

✅ Finished in 12.3s
```

**Runtime:** ~5-15 seconds depending on corpus size and number of tickets.

---

### LLM Mode (With Claude Sonnet)

**Enhanced responses** using Claude Sonnet API:

#### Option 1: Set Environment Variable

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-your-real-key-here"

# Windows CMD
set ANTHROPIC_API_KEY=sk-ant-your-real-key-here

# macOS/Linux
export ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

#### Option 2: Create `.env` File

```bash
# Copy template
cp .env.example .env

# Edit .env with your real key
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

**Then run:**
```bash
python code/run_agent.py
```

**Benefits of LLM Mode:**
- ✨ Higher-quality responses
- 💬 Better tone personalization
- 🔍 More nuanced understanding
- ⚠️ Small cost (~$0.01-0.05 per ticket with Claude Sonnet)

---

## Input Data Format

### Support Tickets CSV (`support_issues/support_tickets.csv`)

**Required columns:**
```csv
issue,subject,company
"I lost access to my team workspace","Claude access lost","Claude"
"I completed a HackerRank test but got rejected","HackerRank test score review","HackerRank"
"I used my Visa card and the merchant sent wrong product","Wrong product received","Visa"
```

**Rules:**
- `issue`: Full problem description (can be multi-sentence)
- `subject`: Short title (<50 chars)
- `company`: HackerRank, Claude, or Visa (if blank, auto-inferred)
- **No header row** (remove if copying from Excel)

**Example with auto-inference:**
```csv
issue,subject,company
"Can I reset my password?","Password reset","Claude"
"My mock test is broken and I can't continue","Test platform bug",""
"My card was charged twice","Duplicate charge",""
```

The agent auto-detects company from keywords in the `issue` column.

---

## Output Files

### 1. `output/output.csv`

**Full decision log** — one row per ticket.

**Columns:**
```
issue, subject, company, response, product_area, status, request_type, justification
```

**Use this for:**
- Auto-reply email templates
- CRM import
- Manual review (for escalated tickets)

### 2. `output/analytics_report.csv`

**Summary statistics** — one row per ticket with scores.

**Columns:**
```
ticket_id, company, status, urgency, sentiment, confidence, quality, 
health_score, churn_risk, product_area, request_type, pii_risk
```

**Use this for:**
- Dashboard BI tools (Tableau, PowerBI)
- Analytics dashboards
- Performance tracking

### 3. `output/audit_trail.csv`

**SOC 2/GDPR compliance log** — SHA-256 chained entries.

**Columns:**
```
seq, timestamp, ticket_fingerprint, company, status, urgency, confidence, 
quality, pii_risk_level, is_duplicate, churn_risk, incident_cluster, 
prev_hash, entry_hash
```

**Use this for:**
- Compliance audits
- Tamper detection
- Regulatory evidence

**Verify chain integrity:**
```python
import pandas as pd
df = pd.read_csv('output/audit_trail.csv')

# Check chain links
for i in range(1, len(df)):
    if df.iloc[i]['prev_hash'] != df.iloc[i-1]['entry_hash']:
        print(f"❌ Chain broken at entry {i}")
        break
else:
    print("✓ Audit trail chain verified")
```

### 4. `output/faq/faq_entries.json`

**Auto-generated FAQ** from high-confidence resolutions.

**Format:**
```json
[
  {
    "question": "How do I resolve: Claude access lost?",
    "answer": "We're here to help! Here's what to do: ...",
    "product": "Claude",
    "product_area": "team_and_enterprise",
    "tags": ["claude", "account-access"],
    "confidence": 0.891,
    "source_ticket": 1
  }
]
```

**Use this for:**
- Documentation updates
- Knowledge base ingestion
- FAQ website automation

### 5. `output/faq/faq_draft.md`

**Same as faq_entries.json** but in Markdown format for humans.

### 6. `output/dashboard.html`

**Interactive HTML dashboard** — open in Chrome/Firefox.

**Features:**
- 📊 6+ charts (sentiment, SLA queue, health scores)
- 🎯 KPI cards (tickets processed, reply rate, etc.)
- 🔍 Sortable/filterable ticket table
- 📱 Mobile responsive
- 💾 Single file (no dependencies)

**To view:**
```bash
# Open in default browser
open output/dashboard.html              # macOS
xdg-open output/dashboard.html          # Linux
start output/dashboard.html             # Windows PowerShell
```

---

## Configuration

### Advanced Settings

Edit `code/config.py` to customize:

```python
# corpus.py config
SCRAPER_CFG = {
    'timeout': 10,           # HTTP request timeout (seconds)
    'chunk_size': 1000,      # Characters per chunk
    'skip_seed': False,      # Skip built-in seed corpus
}

# retriever.py config
RETRIEVER_CFG = {
    'bm25_weight': 0.4,      # BM25 contribution to ranking
    'tfidf_weight': 0.6,     # TF-IDF contribution
    'top_k': 5,              # Retrieved docs per query
    'min_score': 0.3,        # Minimum relevance threshold
}

# agent.py config
AGENT_CFG = {
    'use_llm': False,        # Set True if using Claude API
    'confidence_threshold': 0.5,  # Escalate if <50%
    'quality_threshold': 0.7,     # Escalate if quality <70%
}
```

### Custom Corpus

To add your own support documents:

```bash
# 1. Create corpus file
cat > code/seed_corpus.json << 'EOF'
{
  "HackerRank": [
    {
      "text": "To reset your password: click 'Forgot Password' on the login screen...",
      "source": "internal_kb_001",
      "product_area": "billing"
    }
  ]
}
EOF

# 2. Or edit code/seed_corpus.py to add URLs to scrape
URLS_TO_SCRAPE = {
    'YourCompany': {
        'help_page': 'https://company.com/support',
        'faq_page': 'https://company.com/faq'
    }
}

# 3. Re-run agent
python code/run_agent.py
```

---

## Troubleshooting

### Issue: ModuleNotFoundError for `rank_bm25`

**Solution:**
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Issue: No tickets loaded from CSV

**Check:**
1. File exists at `support_issues/support_tickets.csv`
2. No header row (remove first line if present)
3. Columns are: `issue`, `subject`, `company`
4. CSV not empty

**Fix:**
```bash
# Create minimal test CSV
cat > support_issues/support_tickets.csv << 'EOF'
"Test issue 1","Test subject 1","Claude"
"Test issue 2","Test subject 2","HackerRank"
EOF
```

### Issue: Slow first run (HTTP timeouts)

**Reason:** Corpus scraping from websites (attempt to fetch 3 domains).

**Solution:**
```bash
# Skip scraping, use seed corpus only
# Edit code/config.py:
SCRAPER_CFG['skip_scraping'] = True
```

### Issue: Dashboard not displaying charts

**Solution:**
1. Ensure JavaScript is enabled in browser
2. Try different browser (Chrome/Firefox recommended)
3. Check browser console for errors (F12)
4. Regenerate dashboard:
   ```bash
   python code/run_agent.py  # Regenerates dashboard.html
   ```

### Issue: Out of memory on large corpus

**Solution:**
```bash
# Reduce batch size
# Edit code/config.py:
BATCH_SIZE = 100  # Process 100 tickets at a time

# Or reduce corpus size:
# Keep only top 1,000 most relevant chunks per company
```

---

## Integration Examples

### Send Replies via Email

```python
import smtplib
from email.mime.text import MIMEText
import pandas as pd

df = pd.read_csv('output/output.csv')

for _, row in df.iterrows():
    if row['status'] == 'Replied':
        msg = MIMEText(row['response'])
        msg['Subject'] = f"Re: {row['subject']}"
        msg['From'] = 'support@company.com'
        msg['To'] = row['customer_email']  # Add email column to CSV
        
        with smtplib.SMTP('localhost') as server:
            server.send_message(msg)
```

### Slack Notifications for Escalations

```python
import json
from slack_sdk import WebClient

slack = WebClient(token='xoxb-your-token')

with open('output/output.csv') as f:
    for row in csv.DictReader(f):
        if row['status'] == 'Escalated':
            slack.chat_postMessage(
                channel='#support-escalations',
                text=f"""🚨 *{row['subject']}* (Ticket #{row['id']})
Company: {row['company']}
Priority: {row['urgency']}
Reason: {row['justification']}"""
            )
```

### Zapier / Make Automation

1. Create Zap: "On New Row in CSV → Create Task in Asana"
2. Connect `output/output.csv` as trigger
3. Map fields:
   - Task name = `subject`
   - Description = `response`
   - Project = inferred from `company`
   - Priority = urgency tier
4. Run daily after `python code/run_agent.py`

---

## Performance Benchmarks

### Single Machine (Grounded Mode)

| Metric | Value |
|--------|-------|
| **Tickets processed** | 29 |
| **Total runtime** | 12.3 seconds |
| **Per-ticket latency** | 424 ms avg |
| **Memory usage** | 145 MB |
| **Throughput** | ~140 tickets/min |

### Scaling (Estimated)

| Corpus Size | Tickets | Runtime | Memory | Throughput |
|-------------|---------|---------|--------|------------|
| 27 chunks | 29 | 12 s | 145 MB | 145/min |
| 1,000 chunks | 1,000 | ~7 min | 500 MB | 143/min |
| 10,000 chunks | 10,000 | ~70 min | 2 GB | 143/min |

**Scaling strategy:**
- Latency ≈ constant (BM25/TF-IDF optimized)
- Memory ≈ linear with corpus size
- Throughput ≈ linear with # of workers

---

## Production Deployment

### Option 1: Scheduled Batch Processing

```bash
#!/bin/bash
# run_daily.sh

cd /var/support-triage-agent

# Activate venv
source .venv/bin/activate

# Run agent
python code/run_agent.py

# Upload outputs
aws s3 cp output/ s3://my-bucket/outputs/$(date +%Y-%m-%d)/ --recursive

# Send email report
python scripts/email_summary.py output/analytics_report.csv
```

**Schedule with cron:**
```bash
0 2 * * * /var/support-triage-agent/run_daily.sh  # 2 AM daily
```

### Option 2: Real-time API

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
from agent import SupportTriageAgent

app = FastAPI()
agent = SupportTriageAgent()

@app.post("/triage")
async def triage_ticket(ticket: dict):
    """
    POST /triage
    {
      "issue": "...",
      "subject": "...",
      "company": "Claude"
    }
    """
    result = agent.process(ticket)
    return JSONResponse(result)

@app.get("/health")
async def health():
    return {"status": "ok"}

# Run with: uvicorn main:app --port 8000
```

**Usage:**
```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"issue":"My card was blocked","company":"Visa"}'
```

### Option 3: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY code/ code/
COPY support_issues/ support_issues/

ENV ANTHROPIC_API_KEY=sk-ant-placeholder

CMD ["python", "code/run_agent.py"]
```

**Build & run:**
```bash
docker build -t support-triage-agent .
docker run -e ANTHROPIC_API_KEY=sk-ant-xxx support-triage-agent
```

---

## Support & Contributing

- **Issues**: [GitHub Issues](https://github.com/AnmollCodes/support-triage-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/AnmollCodes/support-triage-agent/discussions)
- **Pull Requests**: Contributions welcome! See `CONTRIBUTING.md`

---

## License

MIT License — see [LICENSE](LICENSE) file

---

**Last Updated**: 2026-05-12 | **Status**: Production Ready ✅

