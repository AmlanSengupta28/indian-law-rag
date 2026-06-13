"""
STEP 3: Embed chunks with Gemini + upload to Supabase
"""

import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

CHUNKS_PATH = "data/chunks.json"
BATCH_SIZE = 20


def get_gemini_embeddings(texts: list, api_key: str) -> list:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    embeddings = []
    for text in texts:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        embeddings.append(result.embeddings[0].values)

    return embeddings


def upload_chunks_to_supabase(chunks: list, supabase_url: str, supabase_key: str, gemini_key: str):
    from supabase import create_client

    supabase = create_client(supabase_url, supabase_key)

    total = len(chunks)
    uploaded = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        print(f"Embedding batch {i//BATCH_SIZE + 1} ({i+1}-{min(i+BATCH_SIZE, total)} of {total})...")

        try:
            embeddings = get_gemini_embeddings(texts, gemini_key)

            rows = []
            for chunk, embedding in zip(batch, embeddings):
                rows.append({
                    "id": chunk["id"],
                    "section_number": chunk["section_number"],
                    "chapter": chunk["chapter"],
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "embedding": embedding
                })

            supabase.table("law_chunks").upsert(rows).execute()
            uploaded += len(rows)
            print(f"Uploaded {uploaded}/{total}")

            time.sleep(1)

        except Exception as e:
            print(f"Error in batch {i//BATCH_SIZE + 1}: {e}")
            time.sleep(5)

    print(f"\nDone. Uploaded {uploaded}/{total} chunks to Supabase.")


if __name__ == "__main__":
    gemini_key = os.getenv("GEMINI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([gemini_key, supabase_url, supabase_key]):
        print("Missing env vars. Check your .env file.")
        exit(1)

    if not os.path.exists(CHUNKS_PATH):
        print("chunks.json not found. Run step2_chunk.py first.")
        exit(1)

    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks")
    upload_chunks_to_supabase(chunks, supabase_url, supabase_key, gemini_key)