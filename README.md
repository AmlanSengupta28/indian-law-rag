# Kanoon Saathi — Indian Road Law Assistant

A semantic search application built on the Motor Vehicles Act 1988. Describe a traffic situation in plain English, get the relevant law, fine, and your rights — instantly.

**Live:** [indian-law-rag.vercel.app](https://indian-law-rag.vercel.app)

---

## What it does

Most people don't know their rights when stopped by traffic police. This tool lets you describe a situation in plain words — "I forgot my licence at home" or "caught without helmet" — and retrieves the exact section of the Motor Vehicles Act that applies, along with the fine and what an officer can or cannot do.

It does not keyword-match. It understands meaning. Asking "cop stopped me for not wearing headgear" retrieves Section 129 (protective headgear) even though the word "headgear" wasn't in the query. That's the difference semantic search makes.

---

## How it works — the RAG architecture

RAG stands for Retrieval-Augmented Generation. Instead of asking an LLM to answer from memory (which leads to hallucination), the system first retrieves the relevant legal text, then generates an answer grounded in that text.

```
User query
    │
    ▼
[Embedding model]          ← converts query to a 3072-dim vector
    │
    ▼
[Vector similarity search] ← finds closest law sections in Supabase
    │
    ▼
[Top 2 sections retrieved] ← actual text from MV Act 1988
    │
    ▼
[LLM generation]           ← Gemini answers using only retrieved text
    │
    ▼
Answer + cited sections
```

The key insight: the LLM never invents law. It only interprets what the retrieval layer found.

---

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| Embedding | Gemini `text-embedding-001` | 3072-dim vectors, free tier |
| Vector DB | Supabase pgvector | Postgres-native, free tier, no index needed at 247 rows |
| LLM | Gemini 2.5 Flash | Fast, generous free quota |
| Backend | FastAPI on Vercel | Python serverless, auto-detected |
| Frontend | Vanilla HTML/CSS/JS | No framework overhead |
| Data source | Motor Vehicles Act 1988 PDF | India Code (official govt repository) |

**Total cost: ₹0** for personal/portfolio usage within free tier limits.

---

## What I built — step by step

### Step 1: Download the source document
Downloaded the Motor Vehicles Act 1988 PDF from India Code (`indiacode.nic.in`) — the official government repository. This gives us 175 pages of law to search over.

### Step 2: Parse and chunk by section
Used PyMuPDF to extract raw text from the PDF. The key challenge: PDFs don't have semantic structure. A naive split by page loses context.

The solution: split by legal section. Each section (Section 129, Section 177, etc.) is one retrievable unit — one legal concept. This required writing a regex parser that handles:
- Table of contents pages (pages 1–14, skipped)
- Footnote markers like `3[129.` that prefix section numbers
- Omitted sections deleted by 2022 amendments
- Duplicate section numbers from cross-references (kept the longest version)

**Result: 247 clean section chunks.**

### Step 3: Embed and upload to Supabase
Each chunk was passed through Gemini's embedding model with `task_type: RETRIEVAL_DOCUMENT`. This converts the legal text into a 3072-dimensional vector — a point in high-dimensional space where meaning determines proximity.

All 247 vectors were upserted into a Supabase `law_chunks` table with pgvector. No index needed at this scale; Postgres does a full scan in milliseconds.

A Postgres function `match_law_chunks` handles cosine similarity search:
```sql
SELECT *, 1 - (embedding <=> query_embedding) AS similarity
FROM law_chunks
ORDER BY embedding <=> query_embedding
LIMIT 3;
```

### Step 4: Build the query pipeline
At query time:
1. Embed the user's question with `task_type: RETRIEVAL_QUERY` (different from document embedding — optimised for asymmetric search)
2. Run vector similarity search in Supabase
3. Pass top 2 retrieved sections + user question to Gemini
4. Return grounded answer with section citations

The system prompt constrains Gemini to only answer from the provided sections, cite section numbers, and mention DigiLocker where relevant.

### Step 5: Deploy on Vercel
FastAPI serves both the HTML frontend and the `/query` POST endpoint from a single `api/index.py` file. Vercel auto-detects Python from `requirements.txt`.

Key learnings from deployment:
- Vercel vendors its own copy of certain packages — using direct HTTP calls to Gemini API avoids SDK conflicts
- Environment variables must be added to Vercel dashboard before redeployment takes effect
- `@vercel/python` runtime handles ASGI (FastAPI) natively

---

## Concepts this project covers

**RAG pipeline** — chunking strategy, retrieval vs generation separation, grounding LLM responses

**Embeddings** — what a vector is, cosine similarity, why semantic search beats keyword search, asymmetric query vs document embeddings

**Vector databases** — pgvector extension, cosine similarity search, when you need an index vs when you don't

**PDF parsing** — text extraction, cleaning, regex-based chunking, handling real-world document noise

**Prompt engineering** — constrained generation, citation forcing, system prompt design for domain-specific tools

**Serverless deployment** — Vercel Python functions, ASGI, environment variable management, dependency conflicts

---

## Project structure

```
kanoon-saathi/
  step1_download.py       # Downloads MV Act PDF from India Code
  step2_chunk.py          # Parses PDF, splits by section, saves chunks.json
  step3_embed_upload.py   # Embeds chunks with Gemini, uploads to Supabase
  step4_query.py          # Local test of full RAG pipeline
  api/
    index.py              # FastAPI app — serves UI + handles /query POST
  index.html              # Frontend (Lora serif, warm paper tones)
  requirements.txt
  data/                   # Created locally during pipeline run
    mv_act_1988.pdf
    chunks.json
```

---

## Setup

### Prerequisites
- Python 3.10+
- Gemini API key: [aistudio.google.com](https://aistudio.google.com)
- Supabase project: [supabase.com](https://supabase.com)

### 1. Clone and install
```bash
git clone https://github.com/AmlanSengupta28/indian-law-rag
cd indian-law-rag
pip install -r requirements.txt
```

### 2. Create `.env`
```
GEMINI_API_KEY=your_key
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_anon_key
```

### 3. Run Supabase setup SQL
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE law_chunks (
  id TEXT PRIMARY KEY,
  section_number TEXT,
  chapter TEXT,
  text TEXT,
  source TEXT,
  embedding vector(3072)
);

CREATE OR REPLACE FUNCTION match_law_chunks(
  query_embedding vector(3072),
  match_count int DEFAULT 3
)
RETURNS TABLE (
  id text, section_number text, chapter text,
  text text, source text, similarity float
)
LANGUAGE sql STABLE AS $$
  SELECT id, section_number, chapter, text, source,
    1 - (embedding <=> query_embedding) AS similarity
  FROM law_chunks
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

### 4. Build the data pipeline
```bash
python step1_download.py
python step2_chunk.py
python step3_embed_upload.py
python step4_query.py   # test locally
```

### 5. Deploy
Add `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` to Vercel environment variables, then:
```bash
git push origin main
```
Vercel auto-deploys on push.

---

## Limitations and next steps

The current build covers only the central Motor Vehicles Act 1988. State-level RTO rules, city-specific challan amounts, and 2024+ amendments are not included. A stronger version would ingest multiple sources and handle multi-turn conversation to clarify ambiguous situations.

---

*Built by [Amlan Sengupta](https://linkedin.com/in/amlan-sengupta28/) · Associate Product Manager, MakeMyTrip*
