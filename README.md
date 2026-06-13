# Indian Road Law RAG

Semantic search over the Motor Vehicles Act 1988. Describe your situation, get the law and fine.

## Stack
- Gemini text-embedding-004 (free) - embeddings
- Gemini 1.5 Flash (free) - answer generation
- Supabase pgvector (free tier) - vector storage
- Vercel (free tier) - hosting

## Setup (one time)

### 1. Get API keys
- Gemini: https://aistudio.google.com/app/apikey (free, no card needed)
- Supabase: https://supabase.com (free tier, create project)

### 2. Create .env file
```
GEMINI_API_KEY=your_key
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_anon_key
```

### 3. Install dependencies
```bash
pip install pymupdf google-generativeai supabase python-dotenv
```

### 4. Run Supabase setup SQL
Go to Supabase dashboard > SQL Editor, run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE law_chunks (
  id TEXT PRIMARY KEY,
  section_number TEXT,
  chapter TEXT,
  text TEXT,
  source TEXT,
  embedding vector(768)
);

CREATE INDEX ON law_chunks USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION match_law_chunks(
  query_embedding vector(768),
  match_count int DEFAULT 3
)
RETURNS TABLE (
  id text,
  section_number text,
  chapter text,
  text text,
  source text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT id, section_number, chapter, text, source,
    1 - (embedding <=> query_embedding) AS similarity
  FROM law_chunks
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

### 5. Build the data pipeline
```bash
python step1_download.py   # Download MV Act PDF
python step2_chunk.py      # Parse into section chunks
python step3_embed_upload.py  # Embed + upload to Supabase
```

### 6. Test locally
```bash
python step4_query.py
```

### 7. Deploy to Vercel
```bash
# Add env vars to Vercel
vercel env add GEMINI_API_KEY
vercel env add SUPABASE_URL
vercel env add SUPABASE_KEY

# Deploy
vercel --prod
```

## Project structure
```
indian-law-rag/
  step1_download.py       # Download MV Act PDF
  step2_chunk.py          # Parse + chunk by section
  step3_embed_upload.py   # Embed + upload to Supabase
  step4_query.py          # Local test of full RAG pipeline
  api/
    query.py              # Vercel serverless function
  index.html              # Frontend
  vercel.json             # Vercel config
  requirements.txt        # Python dependencies
  data/                   # Created during pipeline run
    mv_act_1988.pdf
    chunks.json
```

## Cost
- Gemini: Free (1500 RPM, 1500 queries/day)
- Supabase: Free tier (500MB, plenty for MV Act)
- Vercel: Free tier
- Total: Rs 0 for personal/portfolio usage
