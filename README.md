# 🛡️ ContentGuard — LLM-Powered Content Validation Platform

Validate social media posts against trained batches of approved content using Claude/GPT-4V vision models.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     ContentGuard Stack                      │
│                                                              │
│  ┌─────────────┐   ┌──────────────────┐   ┌─────────────┐ │
│  │  Next.js 14 │   │   Python/FastAPI  │   │  MySQL 8.0  │ │
│  │  :3000      │──▶│   :8000          │──▶│  :3306      │ │
│  │  Dashboard  │   │  + Anthropic/    │   │  7 tables   │ │
│  │  Templates  │   │    OpenAI Vision  │   └─────────────┘ │
│  │  Validate   │   └──────────────────┘                    │
│  │  Reports    │                                            │
│  └─────────────┘                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Quick Start (Docker — Recommended)

### Prerequisites
- Docker Desktop running
- Anthropic API key (get one free at https://console.anthropic.com)

### 1. Configure API Key
```bash
# Copy the env template
cp .env.example .env
# Edit .env and add your key:
# ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Start Everything
```bash
docker-compose up --build
```

Wait ~2 minutes, then open:
- **App**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

---

## Manual Setup (Without Docker)

### Prerequisites
- Python 3.11+
- Node.js 20+
- MySQL 8.0

### Step 1 — Database
```bash
mysql -u root -p < database/init.sql
```

### Step 2 — Python Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add DB URL and ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

### Step 3 — Next.js Frontend
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

---

## How to Use

### 1. Create a Template
- Go to **Templates** → **+ Create Template**
- Give it a descriptive name (e.g. "Q1 2024 Instagram Campaign")
- Click **Manage Files** to open the template

### 2. Upload & Train Approved Content
- Drag & drop approved images and videos
- Each file is automatically sent to the LLM for analysis
- Training extracts: visual description, text/captions, brand elements, color palette
- Status changes: `pending` → `processing` → `done`
- Template status becomes `ready` once all files are trained

### 3. Validate a Post
- Go to **Validate**
- Select the template to validate against
- Choose **Upload File** or **Paste URL**
- Optionally enter: post timestamp, platform, caption
- Click **Run Validation**
- LLM compares destination content against all trained files (30–90 seconds)

### 4. Review Results
The results table shows per-file comparison:

| Column | Description |
|--------|-------------|
| **Template File** | Name of the trained approved content file |
| **Trained Content Suspected Match** | Template name + file name if match detected |
| **Exact Pixel Match?** | Yes/No — pixel-level identity check |
| **MCC Compliant?** | Content compliance check (no explicit/harmful content) |
| **Similarity Score** | Combined LLM + pixel score (0–100%) |
| **Action** | Appropriate / Escalate / Need to Review |

### 5. Reports & Export
- All validations are automatically saved to **Reports**
- Filter by template, verdict, date range
- Click **Export to Excel** for a formatted .xlsx with:
  - Summary sheet: all validations with verdict and match info
  - Detail sheet: per-file match scores and reasoning

---

## LLM Configuration

### Anthropic Claude (Default — Recommended)
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
```
Uses `claude-sonnet-4-20250514` with vision capability.

### OpenAI GPT-4V
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key
```

### Demo Mode (No API Key)
If no API key is set, the system runs in **demo mode** — it returns mock similarity scores so you can explore the full UI without an API key.

---

## Matching Algorithm

```
Overall Score = (LLM Semantic Score × 55%) + (Pixel Hash Score × 30%) + (LLM Score × 15%)

Thresholds (configurable in .env):
  SUSPECTED_MATCH_THRESHOLD = 75%   → "is_suspected_match: true"
  PIXEL_MATCH_THRESHOLD     = 95%   → "is_exact_pixel_match: true"
  SEMANTIC_MATCH_THRESHOLD  = 72%   → LLM similarity threshold

Verdict logic:
  exact_pixel_matches > 0   → Appropriate
  all scores < threshold    → Need Review (if LLM says escalate → Escalate)
  mcc_compliant = false     → Escalate (overrides everything)
```

---

## Project Structure

```
content-validator/
├── docker-compose.yml
├── database/
│   └── init.sql                   ← MySQL schema (7 tables)
├── backend/
│   ├── main.py                    ← FastAPI app entry point
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── config.py              ← Settings (reads .env)
│       ├── models/
│       │   ├── models.py          ← SQLAlchemy ORM models
│       │   └── database.py        ← DB session
│       ├── schemas/
│       │   └── schemas.py         ← Pydantic request/response schemas
│       ├── api/
│       │   ├── templates.py       ← Template CRUD + file upload endpoints
│       │   ├── validations.py     ← Validate upload/URL endpoints
│       │   └── reports.py         ← Reports list, detail, export endpoints
│       └── services/
│           ├── llm_service.py     ← Anthropic/OpenAI vision analysis
│           ├── image_service.py   ← pHash, pixel similarity, file ops
│           ├── validation_service.py ← Orchestrates full pipeline
│           └── export_service.py  ← Excel report generation
└── frontend/
    ├── next.config.js
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx         ← Sidebar navigation shell
        │   ├── dashboard/page.tsx ← Analytics dashboard
        │   ├── templates/
        │   │   ├── page.tsx       ← Template list + create
        │   │   └── [id]/page.tsx  ← Upload files + training status
        │   ├── validate/page.tsx  ← Validate upload/URL + results table
        │   └── reports/page.tsx   ← Reports history + Excel export
        ├── lib/
        │   └── api.ts             ← All API calls (typed)
        └── styles/
            └── globals.css        ← Design tokens + global styles
```

---

## .env Reference

```env
# Required
DATABASE_URL=mysql+pymysql://root:Validator@2024@localhost:3306/content_validator
ANTHROPIC_API_KEY=sk-ant-...

# Optional
LLM_PROVIDER=anthropic          # or "openai"
OPENAI_API_KEY=sk-...
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=100
PIXEL_MATCH_THRESHOLD=95
SEMANTIC_MATCH_THRESHOLD=72
SUSPECTED_MATCH_THRESHOLD=75
```
