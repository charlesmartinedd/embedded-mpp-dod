"""
PDF Ingestion Script for MPP Documentation
Extracts text from PDFs with exact page tracking and creates vector embeddings
"""

import os
import fitz  # PyMuPDF
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import json
from typing import List, Dict
import hashlib

# Explicitly load .env from current directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

class PDFIngestion:
    def __init__(self, core_dir: str, modules_dir: str):
        self.core_dir = Path(core_dir)
        self.modules_dir = Path(modules_dir)

        # Force load API key from .env file
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "lmstudio":
            raise ValueError("OPENAI_API_KEY not properly loaded from .env file")

        print(f"Using API key: {api_key[:20]}...")
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", 512))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", 50))

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")

        # Create or get collections
        self.collection = self.chroma_client.get_or_create_collection(
            name="mpp_documents",
            metadata={"description": "DoD Mentor-Protege Program Documentation"}
        )

    def extract_text_from_pdf(self, pdf_path: Path, doc_type: str) -> List[Dict]:
        """Extract text from PDF with page-level tracking"""
        chunks = []

        try:
            doc = fitz.open(pdf_path)
            print(f"Processing: {pdf_path.name} ({len(doc)} pages)")

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                # Skip empty pages
                if not text.strip():
                    continue

                # Create chunks from page text
                page_chunks = self._create_chunks(text, page_num + 1)

                for idx, chunk_text in enumerate(page_chunks):
                    chunk_id = self._generate_chunk_id(pdf_path.name, page_num + 1, idx)

                    chunks.append({
                        "id": chunk_id,
                        "text": chunk_text,
                        "metadata": {
                            "document": pdf_path.name,
                            "page": page_num + 1,
                            "doc_type": doc_type,  # "core" or "module"
                            "chunk_index": idx,
                            "file_path": str(pdf_path)
                        }
                    })

            doc.close()
            print(f"  [OK] Extracted {len(chunks)} chunks from {pdf_path.name}")

        except Exception as e:
            print(f"  [ERROR] Error processing {pdf_path.name}: {str(e)}")

        return chunks

    def _create_chunks(self, text: str, page_num: int) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk = ' '.join(words[i:i + self.chunk_size])
            chunks.append(chunk)

        return chunks

    def _generate_chunk_id(self, filename: str, page: int, chunk_idx: int) -> str:
        """Generate unique ID for chunk"""
        content = f"{filename}_{page}_{chunk_idx}"
        return hashlib.md5(content.encode()).hexdigest()

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI"""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts
        )
        return [item.embedding for item in response.data]

    def ingest_documents(self):
        """Main ingestion process"""
        all_chunks = []

        print("\n=== Processing Core Documents ===")
        for pdf_file in self.core_dir.glob("*.pdf"):
            chunks = self.extract_text_from_pdf(pdf_file, "core")
            all_chunks.extend(chunks)

        print("\n=== Processing Module Documents ===")
        for pdf_file in self.modules_dir.glob("*.pdf"):
            chunks = self.extract_text_from_pdf(pdf_file, "module")
            all_chunks.extend(chunks)

        print(f"\n=== Total Chunks: {len(all_chunks)} ===")

        # Batch process embeddings
        print("\n=== Generating Embeddings ===")
        batch_size = 100

        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            texts = [chunk["text"] for chunk in batch]

            print(f"Processing batch {i//batch_size + 1}/{(len(all_chunks) + batch_size - 1)//batch_size}")
            embeddings = self.get_embeddings(texts)

            # Add to ChromaDB
            self.collection.add(
                ids=[chunk["id"] for chunk in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[chunk["metadata"] for chunk in batch]
            )

        print("\n=== Ingestion Complete ===")
        print(f"Total documents in collection: {self.collection.count()}")

        # Save summary
        summary = {
            "total_chunks": len(all_chunks),
            "core_docs": len(list(self.core_dir.glob("*.pdf"))),
            "module_docs": len(list(self.modules_dir.glob("*.pdf"))),
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size
        }

        with open("ingestion_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return summary

if __name__ == "__main__":
    # Adjust paths to parent directories
    core_dir = "../Core"
    modules_dir = "../Modules"

    ingestion = PDFIngestion(core_dir, modules_dir)
    summary = ingestion.ingest_documents()

    print("\n" + "="*50)
    print("Summary:")
    print(json.dumps(summary, indent=2))
