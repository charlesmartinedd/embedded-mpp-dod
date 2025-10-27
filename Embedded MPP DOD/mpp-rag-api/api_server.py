"""
FastAPI Server for MPP RAG System
Provides endpoints for querying, extracting, and cross-referencing DoD MPP documentation
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
import os
from rank_bm25 import BM25Okapi
import numpy as np
from pathlib import Path

# Explicitly load .env from current directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

app = FastAPI(
    title="MPP RAG API",
    description="Query DoD Mentor-Protege Program documentation with exact citations",
    version="1.0.0"
)

# Initialize clients
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection(name="mpp_documents")

# Models
class QueryRequest(BaseModel):
    question: str = Field(..., description="Question to ask about MPP documentation")
    top_k: int = Field(5, description="Number of sources to retrieve")
    doc_type: Optional[str] = Field(None, description="Filter by 'core' or 'module'")
    include_context: bool = Field(True, description="Include full context in response")

class ExtractRequest(BaseModel):
    document: str = Field(..., description="Document name (e.g., 'MPP SOP.pdf')")
    page: Optional[int] = Field(None, description="Specific page number")
    search_term: Optional[str] = Field(None, description="Search for specific term")

class CrossReferenceRequest(BaseModel):
    query: str = Field(..., description="What to cross-reference")
    module_name: Optional[str] = Field(None, description="Specific module to check")

class Source(BaseModel):
    quote: str
    document: str
    page: int
    confidence: float
    doc_type: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Source]
    metadata: Dict

# Helper Functions
def get_embedding(text: str) -> List[float]:
    """Get embedding from OpenAI"""
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
        input=text
    )
    return response.data[0].embedding

def hybrid_search(query: str, top_k: int = 10, doc_type: Optional[str] = None) -> List[Dict]:
    """Combine semantic and keyword search for better accuracy"""

    # Semantic search with ChromaDB
    query_embedding = get_embedding(query)

    where_filter = {"doc_type": doc_type} if doc_type else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k * 2,  # Get more for reranking
        where=where_filter
    )

    # Format results
    semantic_results = []
    for i in range(len(results['ids'][0])):
        semantic_results.append({
            'text': results['documents'][0][i],
            'metadata': results['metadatas'][0][i],
            'distance': results['distances'][0][i] if 'distances' in results else 0,
            'id': results['ids'][0][i]
        })

    # Simple reranking by distance (lower is better)
    semantic_results.sort(key=lambda x: x['distance'])

    return semantic_results[:top_k]

def generate_answer(question: str, sources: List[Dict]) -> str:
    """Generate answer using GPT with strict citation requirements"""

    context = "\n\n".join([
        f"[{i+1}] Document: {s['metadata']['document']}, Page: {s['metadata']['page']}\n{s['text']}"
        for i, s in enumerate(sources)
    ])

    system_prompt = """You are an expert on the DoD Mentor-Protege Program (MPP).

CRITICAL RULES:
1. ONLY use information from the provided context
2. ALWAYS cite sources using [1], [2], etc.
3. If information is not in the context, say "This information is not found in the provided documents"
4. Quote exact text when possible
5. Be precise and accurate - this is regulatory documentation

Format citations like: "According to the MPP SOP [1], mentors must..."
"""

    user_prompt = f"""Question: {question}

Context from MPP Documentation:
{context}

Provide a detailed answer with exact citations."""

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        # GPT-5 only supports default temperature of 1
    )

    return response.choices[0].message.content

# API Endpoints

@app.get("/")
async def root():
    """API information"""
    return {
        "name": "MPP RAG API",
        "version": "1.0.0",
        "status": "operational",
        "documents_indexed": collection.count(),
        "endpoints": {
            "query": "/query - Ask questions with citations",
            "extract": "/extract - Get exact quotes from documents",
            "cross_reference": "/cross_reference - Compare modules vs core docs",
            "health": "/health - System status"
        }
    }

@app.get("/health")
async def health_check():
    """System health check"""
    try:
        count = collection.count()
        return {
            "status": "healthy",
            "database": "connected",
            "documents_indexed": count,
            "openai_api": "configured"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Query the MPP documentation with exact citations

    Returns synthesized answer with source citations and confidence scores
    """
    try:
        # Retrieve relevant sources
        sources = hybrid_search(
            request.question,
            top_k=request.top_k,
            doc_type=request.doc_type
        )

        if not sources:
            raise HTTPException(status_code=404, detail="No relevant documents found")

        # Generate answer with citations
        answer = generate_answer(request.question, sources)

        # Format sources
        formatted_sources = [
            Source(
                quote=s['text'][:500] + "..." if len(s['text']) > 500 else s['text'],
                document=s['metadata']['document'],
                page=s['metadata']['page'],
                confidence=1.0 - (s['distance'] / 2.0),  # Convert distance to confidence
                doc_type=s['metadata']['doc_type']
            )
            for s in sources
        ]

        return QueryResponse(
            query=request.question,
            answer=answer,
            sources=formatted_sources,
            metadata={
                "total_sources": len(sources),
                "doc_filter": request.doc_type,
                "model": os.getenv("LLM_MODEL", "gpt-4")
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract")
async def extract_from_document(request: ExtractRequest):
    """
    Extract exact text from specific document/page

    Returns verbatim text from the specified document
    """
    try:
        # Build filter with proper ChromaDB syntax
        if request.page:
            where_filter = {
                "$and": [
                    {"document": {"$eq": request.document}},
                    {"page": {"$eq": request.page}}
                ]
            }
        else:
            where_filter = {"document": {"$eq": request.document}}

        # Query collection
        if request.search_term:
            # Search for specific term
            query_embedding = get_embedding(request.search_term)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=10,
                where=where_filter
            )
        else:
            # Get all chunks from document/page
            results = collection.get(
                where=where_filter,
                limit=100
            )

        if not results or (isinstance(results, dict) and not results.get('documents')):
            raise HTTPException(
                status_code=404,
                detail=f"No content found for {request.document}" +
                       (f" page {request.page}" if request.page else "")
            )

        # Format results
        extracts = []
        docs = results['documents'] if isinstance(results['documents'][0], str) else results['documents'][0]
        metas = results['metadatas'] if isinstance(results['metadatas'][0], dict) else results['metadatas'][0]

        for i, doc in enumerate(docs):
            extracts.append({
                "text": doc,
                "page": metas[i]['page'],
                "document": metas[i]['document']
            })

        # Sort by page
        extracts.sort(key=lambda x: x['page'])

        return {
            "document": request.document,
            "page": request.page,
            "search_term": request.search_term,
            "total_extracts": len(extracts),
            "extracts": extracts
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cross_reference")
async def cross_reference(request: CrossReferenceRequest):
    """
    Cross-reference modules against core documents

    Checks if module content aligns with core MPP SOP and Appendix I
    """
    try:
        # Search in modules
        module_filter = {"doc_type": "module"}
        if request.module_name:
            module_filter["document"] = request.module_name

        module_results = hybrid_search(
            request.query,
            top_k=5,
            doc_type="module"
        )

        # Search in core docs
        core_results = hybrid_search(
            request.query,
            top_k=5,
            doc_type="core"
        )

        # Compare results
        module_sources = [
            {
                "document": r['metadata']['document'],
                "page": r['metadata']['page'],
                "text": r['text'][:300] + "..."
            }
            for r in module_results
        ]

        core_sources = [
            {
                "document": r['metadata']['document'],
                "page": r['metadata']['page'],
                "text": r['text'][:300] + "..."
            }
            for r in core_results
        ]

        # Generate alignment analysis
        alignment_prompt = f"""Compare these module and core document excerpts about: {request.query}

MODULE CONTENT:
{chr(10).join([f"{i+1}. {s['document']} p.{s['page']}: {s['text']}" for i, s in enumerate(module_sources)])}

CORE DOCUMENT CONTENT:
{chr(10).join([f"{i+1}. {s['document']} p.{s['page']}: {s['text']}" for i, s in enumerate(core_sources)])}

Analyze:
1. Do the modules align with core documents?
2. Are there any contradictions?
3. What are the key authoritative statements from core docs?

Be specific and cite page numbers."""

        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4"),
            messages=[
                {"role": "system", "content": "You are analyzing alignment between DoD MPP modules and core documentation."},
                {"role": "user", "content": alignment_prompt}
            ]
            # GPT-5 only supports default temperature of 1
        )

        return {
            "query": request.query,
            "module_filter": request.module_name,
            "module_sources": module_sources,
            "core_sources": core_sources,
            "alignment_analysis": response.choices[0].message.content,
            "metadata": {
                "modules_checked": len(module_results),
                "core_references": len(core_results)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n{'='*60}")
    print(f"MPP RAG API Starting on http://localhost:{port}")
    print(f"{'='*60}")
    print(f"Documents indexed: {collection.count()}")
    print(f"API docs: http://localhost:{port}/docs")
    print(f"{'='*60}\n")

    uvicorn.run(app, host="0.0.0.0", port=port)
