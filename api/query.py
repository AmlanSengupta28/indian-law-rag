"""
Vercel Serverless Function: api/query.py
Handles POST requests from the frontend.

Deploy structure:
  /api/query.py        <- this file
  /index.html          <- frontend
  /vercel.json         <- config

Vercel auto-detects Python functions in /api folder.
"""

from http.server import BaseHTTPRequestHandler
import json
import os

# Import core RAG logic
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def embed_query(query: str, api_key: str) -> list:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=query,
        task_type="retrieval_query"
    )
    return result['embedding']


def retrieve_chunks(query_embedding: list, top_k: int = 3) -> list:
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
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    context = "\n".join([f"[Section {c.get('section_number')}] {c['text']}" for c in chunks])
    
    prompt = f"""You are an Indian road traffic law assistant. Answer only from these legal sections:

{context}

Question: {query}

Rules: Cite section numbers. State fine amounts clearly. Mention DigiLocker where relevant. Under 150 words."""
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt, generation_config={"max_output_tokens": 300, "temperature": 0.1})
    return response.text


class handler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            query = data.get("query", "").strip()
            if not query:
                self._send_error(400, "Query is required")
                return
            
            if len(query) > 500:
                self._send_error(400, "Query too long (max 500 chars)")
                return
            
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if not gemini_key:
                self._send_error(500, "API key not configured")
                return
            
            # RAG pipeline
            embedding = embed_query(query, gemini_key)
            chunks = retrieve_chunks(embedding)
            answer = generate_answer(query, chunks, gemini_key)
            
            sources = [
                {"section": c.get("section_number"), "chapter": c.get("chapter")}
                for c in chunks
            ]
            
            self._send_json(200, {"answer": answer, "sources": sources})
        
        except Exception as e:
            self._send_error(500, f"Internal error: {str(e)}")
    
    def _send_json(self, status: int, data: dict):
        response = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def _send_error(self, status: int, message: str):
        self._send_json(status, {"error": message})
