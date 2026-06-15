from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import requests
import hashlib
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent.parent

def get_index_html() -> str:
    index_path = ROOT / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<html><body><h1>Indian Law RAG API is running</h1></body></html>"

GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


class QueryRequest(BaseModel):
    query: str


def get_supabase():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )


def make_hash(query: str) -> str:
    normalized = query.strip().lower()
    return hashlib.md5(normalized.encode()).hexdigest()


def check_cache(query: str) -> dict | None:
    """Return cached result if exists, else None."""
    try:
        supabase = get_supabase()
        query_hash = make_hash(query)
        result = supabase.table("query_cache") \
            .select("*") \
            .eq("query_hash", query_hash) \
            .limit(1) \
            .execute()

        if result.data:
            # Increment hit count
            supabase.table("query_cache") \
                .update({"hit_count": result.data[0]["hit_count"] + 1}) \
                .eq("query_hash", query_hash) \
                .execute()
            return {
                "answer": result.data[0]["answer"],
                "sources": result.data[0]["sections"],
                "cached": True
            }
    except Exception as e:
        print(f"Cache check error: {e}")
    return None


def save_to_cache(query: str, answer: str, sources: list):
    """Save result to cache."""
    try:
        supabase = get_supabase()
        supabase.table("query_cache").upsert({
            "query_hash": make_hash(query),
            "query": query.strip().lower(),
            "answer": answer,
            "sections": json.dumps(sources)
        }).execute()
    except Exception as e:
        print(f"Cache save error: {e}")


def log_query(query: str, answer: str, sources: list):
    """Log every query and response."""
    try:
        supabase = get_supabase()
        supabase.table("query_logs").insert({
            "query": query,
            "answer": answer,
            "sections": [s.get("section") for s in sources if s.get("section")]
        }).execute()
    except Exception as e:
        print(f"Log error: {e}")


def embed_query(query: str, api_key: str) -> list:
    response = requests.post(
        f"{GEMINI_EMBED_URL}?key={api_key}",
        json={
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": query}]},
            "taskType": "RETRIEVAL_QUERY"
        }
    )
    response.raise_for_status()
    return response.json()["embedding"]["values"]


def retrieve_chunks(query_embedding: list, top_k: int = 2) -> list:
    supabase = get_supabase()
    result = supabase.rpc(
        "match_law_chunks",
        {"query_embedding": query_embedding, "match_count": top_k}
    ).execute()
    return result.data


def generate_answer(query: str, chunks: list, api_key: str) -> str:
    context = ""
    for chunk in chunks:
        context += f"\n[S{chunk.get('section_number')}] {chunk['text'][:800]}\n"

    prompt = f"""Indian road traffic law assistant.
Answer only from provided sections. Cite section numbers.
State fines clearly. Mention DigiLocker if relevant. Under 100 words.

Sections:
{context}

Question: {query}

Answer:"""

    import time
    for attempt in range(3):
        try:
            response = requests.post(
                f"{GEMINI_GENERATE_URL}?key={api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            if attempt < 2:
                time.sleep((attempt + 1) * 3)
            else:
                raise


@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTMLResponse(content=get_index_html())


@app.post("/query")
def query_endpoint(request: QueryRequest):
    query = request.query.strip()
    if not query:
        return {"error": "Query is required"}
    if len(query) > 500:
        return {"error": "Query too long"}

    # 1. Check cache first
    cached = check_cache(query)
    if cached:
        print(f"Cache hit for: {query[:50]}")
        return cached

    # 2. Full RAG pipeline
    gemini_key = os.environ.get("GEMINI_API_KEY")
    embedding = embed_query(query, gemini_key)
    chunks = retrieve_chunks(embedding)
    answer = generate_answer(query, chunks, gemini_key)

    sources = [
        {"section": c.get("section_number"), "chapter": c.get("chapter")}
        for c in chunks
    ]

    # 3. Log and cache in background
    log_query(query, answer, sources)
    save_to_cache(query, answer, sources)

    return {"answer": answer, "sources": sources, "cached": False}


@app.get("/debug")
def debug():
    return {
        "gemini_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "supabase_url_present": bool(os.environ.get("SUPABASE_URL")),
        "supabase_key_present": bool(os.environ.get("SUPABASE_KEY")),
    }