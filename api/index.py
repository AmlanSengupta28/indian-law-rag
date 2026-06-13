from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str


def embed_query(query: str, api_key: str) -> list:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
    )
    return result.embeddings[0].values


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
    from google import genai
    client = genai.Client(api_key=api_key)

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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text


@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    query = request.query.strip()
    if not query:
        return {"error": "Query is required"}, 400
    if len(query) > 500:
        return {"error": "Query too long"}, 400

    gemini_key = os.environ.get("GEMINI_API_KEY")
    embedding = embed_query(query, gemini_key)
    chunks = retrieve_chunks(embedding)
    answer = generate_answer(query, chunks, gemini_key)

    sources = [
        {"section": c.get("section_number"), "chapter": c.get("chapter")}
        for c in chunks
    ]
    return {"answer": answer, "sources": sources}