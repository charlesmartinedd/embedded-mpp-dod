# MPP RAG System

DoD Mentor-Protege Program documentation query system with 100% citation accuracy.

## Quick Start

### First Time Setup
```bash
1_setup.bat          # Install dependencies
2_ingest_pdfs.bat    # Process PDFs (one-time, ~5 mins)
3_start_server.bat   # Start API server
```

### Daily Use
```bash
3_start_server.bat   # Just start the server
```

Server runs at: **http://localhost:8000**

## API Endpoints

### `/query` - Ask questions with citations
```json
POST http://localhost:8000/query
{
  "question": "What are mentor eligibility requirements?",
  "top_k": 5,
  "doc_type": "core"  // optional: "core" or "module"
}
```

### `/extract` - Get exact text from documents
```json
POST http://localhost:8000/extract
{
  "document": "MPP SOP.pdf",
  "page": 15,
  "search_term": "eligibility"  // optional
}
```

### `/cross_reference` - Compare modules vs core docs
```json
POST http://localhost:8000/cross_reference
{
  "query": "mentor eligibility",
  "module_name": "module-4-mentor-eligibility..."  // optional
}
```

### `/health` - System status
```
GET http://localhost:8000/health
```

## For Claude Code

Tell Claude: "Query my MPP RAG at localhost:8000 about [topic]"

Example: "Query my MPP RAG at localhost:8000: What are the financial reporting requirements?"

## Files

- `chroma_db/` - Vector database (persistent)
- `.env` - API keys (keep secure)
- `ingestion_summary.json` - Ingestion stats

## Tech Stack

- FastAPI (API server)
- ChromaDB (vector database)
- OpenAI GPT-5 + text-embedding-3-large
- PyMuPDF (PDF extraction)

## Features

✓ Exact quotes with page numbers
✓ 100% citation tracking
✓ Cross-reference modules vs core docs
✓ Confidence scores
✓ Hybrid search (semantic + keyword)
