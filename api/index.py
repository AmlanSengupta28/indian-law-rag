from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = (ROOT / "index.html").read_text(encoding="utf-8")

GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


class QueryRequest(BaseModel):
    query: str


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
    from supabase import create_client
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )
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

    response = requests.post(
        f"{GEMINI_GENERATE_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}]}
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTMLResponse(content=INDEX_HTML)


@app.post("/query")
def query_endpoint(request: QueryRequest):
    query = request.query.strip()
    if not query:
        return {"error": "Query is required"}
    if len(query) > 500:
        return {"error": "Query too long"}

    gemini_key = os.environ.get("GEMINI_API_KEY")
    embedding = embed_query(query, gemini_key)
    chunks = retrieve_chunks(embedding)
    answer = generate_answer(query, chunks, gemini_key)

    sources = [
        {"section": c.get("section_number"), "chapter": c.get("chapter")}
        for c in chunks
    ]
    return {"answer": answer, "sources": sources}