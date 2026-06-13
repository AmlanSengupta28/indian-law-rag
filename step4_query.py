"""
STEP 4: Query engine - optimized for tokens
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Indian road traffic law assistant.
Answer only from provided sections. Cite section numbers.
State fines clearly. Mention DigiLocker if relevant. Under 100 words."""


def embed_query(query: str, api_key: str) -> list:
    log.info("Embedding query...")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        embedding = result.embeddings[0].values
        log.info(f"Embedding successful. Dimensions: {len(embedding)}")
        return embedding

    except Exception as e:
        log.error(f"Embedding failed: {type(e).__name__}: {e}")
        raise


def retrieve_chunks(query_embedding: list, supabase_url: str, supabase_key: str, top_k: int = 2) -> list:
    log.info("Retrieving chunks from Supabase...")
    try:
        from supabase import create_client

        supabase = create_client(supabase_url, supabase_key)
        result = supabase.rpc(
            "match_law_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": top_k
            }
        ).execute()

        chunks = result.data
        log.info(f"Retrieved {len(chunks)} chunks")
        for c in chunks:
            log.info(f"  Section {c.get('section_number')} | similarity: {c.get('similarity', 0):.4f}")
        return chunks

    except Exception as e:
        log.error(f"Retrieval failed: {type(e).__name__}: {e}")
        raise


def generate_answer(query: str, chunks: list, api_key: str) -> str:
    log.info("Generating answer...")
    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Truncate each chunk to 800 chars
        context = ""
        for chunk in chunks:
            context += f"\n[S{chunk.get('section_number')}] {chunk['text'][:800]}\n"

        prompt = f"""{SYSTEM_PROMPT}

Sections:
{context}

Question: {query}

Answer:"""

        log.info(f"Prompt length: {len(prompt)} chars")

        import time
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                answer = response.text
                log.info(f"Answer generated. Length: {len(answer)} chars")
                return answer
            except Exception as retry_err:
                if "503" in str(retry_err) and attempt < 2:
                    wait = (attempt + 1) * 3
                    log.info(f"Gemini busy, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    except Exception as e:
        log.error(f"Generation failed: {type(e).__name__}: {e}")
        raise


def rag_query(user_query: str) -> dict:
    log.info("=== RAG QUERY START ===")

    gemini_key = os.getenv("GEMINI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([gemini_key, supabase_url, supabase_key]):
        log.error("Missing env vars. Check .env file.")
        raise ValueError("Missing env vars")

    query_embedding = embed_query(user_query, gemini_key)
    chunks = retrieve_chunks(query_embedding, supabase_url, supabase_key)
    answer = generate_answer(user_query, chunks, gemini_key)

    log.info("=== RAG QUERY END ===")

    return {
        "answer": answer,
        "sources": [
            {
                "section": c.get("section_number"),
                "chapter": c.get("chapter"),
                "preview": c.get("text", "")[:100] + "..."
            }
            for c in chunks
        ]
    }


if __name__ == "__main__":
    queries = [
        "I forgot my driving license at home and got caught by police. What is the fine?",
        "I was caught without a helmet. What is the penalty?",
        "I jumped a red light. What happens now?"
    ]

    for q in queries:
        print(f"\n{'='*50}")
        print(f"Q: {q}")
        result = rag_query(q)
        print(f"\nA: {result['answer']}")
        print(f"Sources: {[s['section'] for s in result['sources']]}")