"""
Agriculture RAG - PDF Ingestion Pipeline
==========================================
Loads CRIDA district contingency plans + handbooks into ChromaDB
with state/district metadata for location-aware retrieval.

Usage:
    python ingest_pdfs.py                          # Ingest all PDFs
    python ingest_pdfs.py --query "rice pest management in Bihar"
    python ingest_pdfs.py --query "drought contingency for Pune district"
"""

import os
import re
import sys
import argparse
import time

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


# ── Configuration ──────────────────────────────────────────────────────────
PDF_DIR = "./crida_plans"
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "agri_advisory"

# Embedding model - runs locally, no API key needed
# This model is good for semantic search and only ~80MB
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Chunking parameters tuned for agriculture contingency plan structure
CHUNK_SIZE = 1500       # These PDFs have dense tables, larger chunks help
CHUNK_OVERLAP = 300     # Overlap to preserve context across chunk boundaries


# ── Metadata extraction ───────────────────────────────────────────────────
# Map folder names and filename patterns to structured metadata
STATE_ALIASES = {
    "andhra_pradesh": "Andhra Pradesh",
    "bihar": "Bihar",
    "maharashtra": "Maharashtra",
    "odisha": "Odisha",
    "rajasthan": "Rajasthan",
    "_handbooks": "All India",
    "_schemes": "All India",
}

# Known agro-climatic zones (partial, for enrichment)
AGRO_ZONES = {
    "Anantapur": "Southern Plateau and Hills",
    "Patna": "Middle Gangetic Plain",
    "Pune": "Western Plateau and Hills",
    "Kalahandi": "Eastern Plateau and Hills",
    "Udaipur": "Southern Rajasthan",
    "Nagpur": "Central Plateau and Hills",
    "Cuttack": "East Coast Plains and Hills",
}


def extract_metadata(filepath):
    """Extract state, district, and document type from file path."""
    parts = filepath.replace("\\", "/").split("/")
    metadata = {
        "source": filepath,
        "doc_type": "contingency_plan",
    }

    # Find state from folder structure
    for part in parts:
        key = part.lower().replace(" ", "_")
        if key in STATE_ALIASES:
            metadata["state"] = STATE_ALIASES[key]
            break

    if "_handbooks" in filepath:
        metadata["doc_type"] = "handbook"
        metadata["state"] = "All India"
        metadata["district"] = "All India"
        return metadata

    if "_schemes" in filepath:
        metadata["doc_type"] = "scheme"
        metadata["state"] = "All India"
        metadata["district"] = "All India"
        # Tag the specific scheme for better retrieval
        fname_lower = os.path.basename(filepath).lower()
        if "pmfby" in fname_lower:
            metadata["scheme"] = "PMFBY"
        elif "pm_kisan" in fname_lower or "pmkisan" in fname_lower:
            metadata["scheme"] = "PM-KISAN"
        elif "rkvy" in fname_lower:
            metadata["scheme"] = "RKVY"
        else:
            metadata["scheme"] = "General"
        return metadata

    # Extract district from filename
    filename = os.path.splitext(os.path.basename(filepath))[0]
    # Clean up common patterns: "BR31_Araria_28.12.13" -> "Araria"
    district = re.sub(r'^[A-Z]{2,}\d*[-_]\s*', '', filename)
    district = re.sub(r'[-_]\d{1,2}[._]\d{1,2}[._]\d{2,4}.*$', '', district)
    district = re.sub(r'[-_]+', ' ', district).strip()
    metadata["district"] = district if district else filename

    # Add agro-climatic zone if known
    for key, zone in AGRO_ZONES.items():
        if key.lower() in district.lower():
            metadata["agro_zone"] = zone
            break

    return metadata


def find_pdfs(base_dir):
    """Recursively find all PDF files."""
    pdfs = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


def load_and_chunk_pdf(filepath, splitter):
    """Load a single PDF and split into chunks with metadata."""
    metadata = extract_metadata(filepath)
    district = metadata.get("district", "unknown")

    try:
        loader = PyPDFLoader(filepath)
        pages = loader.load()
    except Exception as e:
        print(f"    ⚠ Failed to load: {e}")
        return []

    if not pages:
        print(f"    ⚠ No pages extracted")
        return []

    # Add our metadata to each page before splitting
    for page in pages:
        page.metadata.update(metadata)

    # Split into chunks
    chunks = splitter.split_documents(pages)

    # Enrich each chunk with a searchable context prefix
    # This helps the embedding model understand the location context
    for chunk in chunks:
        state = chunk.metadata.get("state", "India")
        dist = chunk.metadata.get("district", "")
        prefix = f"[State: {state} | District: {dist}] "
        chunk.page_content = prefix + chunk.page_content

    return chunks


def ingest(pdf_dir, chroma_dir):
    """Main ingestion pipeline: PDFs -> chunks -> embeddings -> ChromaDB."""

    # 1. Find PDFs
    print(f"\n📂 Scanning {os.path.abspath(pdf_dir)} for PDFs...")
    pdfs = find_pdfs(pdf_dir)
    if not pdfs:
        print(f"✗ No PDFs found in {pdf_dir}")
        print(f"  Run download_crida_plans.py first!")
        sys.exit(1)

    print(f"   Found {len(pdfs)} PDF files\n")

    # 2. Initialize text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    # 3. Load and chunk all PDFs
    print("📄 Loading and chunking PDFs...")
    all_chunks = []
    failed = []

    for i, pdf in enumerate(pdfs, 1):
        short_name = os.path.relpath(pdf, pdf_dir)
        print(f"  [{i}/{len(pdfs)}] {short_name}...", end=" ", flush=True)

        chunks = load_and_chunk_pdf(pdf, splitter)
        if chunks:
            all_chunks.extend(chunks)
            print(f"✓ {len(chunks)} chunks")
        else:
            failed.append(short_name)
            print("✗ skipped")

    print(f"\n📊 Total: {len(all_chunks)} chunks from {len(pdfs) - len(failed)} PDFs")
    if failed:
        print(f"   ⚠ {len(failed)} PDFs failed to load: {', '.join(failed[:5])}")

    # 4. Create embeddings and store in ChromaDB
    print(f"\n🧠 Loading embedding model: {EMBEDDING_MODEL}")
    print(f"   (First run downloads ~80MB model, subsequent runs use cache)\n")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},  # Change to "cuda" if you have GPU
        encode_kwargs={"normalize_embeddings": True},
    )

    print(f"💾 Creating ChromaDB at {os.path.abspath(chroma_dir)}/")
    print(f"   Embedding {len(all_chunks)} chunks (this may take a few minutes)...\n")

    start = time.time()

    # Process in batches to show progress
    batch_size = 50
    vectorstore = None

    for batch_start in range(0, len(all_chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(all_chunks))
        batch = all_chunks[batch_start:batch_end]
        pct = (batch_end / len(all_chunks)) * 100

        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                persist_directory=chroma_dir,
                collection_name=COLLECTION_NAME,
            )
        else:
            vectorstore.add_documents(batch)

        print(f"   {batch_end}/{len(all_chunks)} chunks embedded ({pct:.0f}%)")

    elapsed = time.time() - start
    print(f"\n✅ Ingestion complete in {elapsed:.1f}s")
    print(f"   ChromaDB stored at: {os.path.abspath(chroma_dir)}/")

    return vectorstore


def query_test(chroma_dir, query, k=5):
    """Run a test query against the vector store."""

    print(f"\n🔍 Query: \"{query}\"\n")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    vectorstore = Chroma(
        persist_directory=chroma_dir,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )

    # Basic similarity search
    results = vectorstore.similarity_search_with_score(query, k=k)

    if not results:
        print("   No results found.")
        return

    print(f"   Top {len(results)} results:\n")
    for i, (doc, score) in enumerate(results, 1):
        state = doc.metadata.get("state", "?")
        district = doc.metadata.get("district", "?")
        page = doc.metadata.get("page", "?")
        # Trim the location prefix we added during ingestion
        content = doc.page_content
        if content.startswith("["):
            content = content.split("] ", 1)[-1]
        preview = content[:300].replace("\n", " ")

        print(f"   ── Result {i} (score: {score:.3f}) ──")
        print(f"   📍 {state} > {district} (page {page})")
        print(f"   {preview}...")
        print()

    # Also try filtered search (by state)
    print(f"   ── Filtered search example (Bihar only) ──")
    filtered = vectorstore.similarity_search(
        query, k=3,
        filter={"state": "Bihar"}
    )
    for doc in filtered:
        district = doc.metadata.get("district", "?")
        content = doc.page_content
        if content.startswith("["):
            content = content.split("] ", 1)[-1]
        print(f"   📍 Bihar > {district}: {content[:200].replace(chr(10), ' ')}...")
        print()


def main():
    ap = argparse.ArgumentParser(description="Agriculture RAG - PDF Ingestion")
    ap.add_argument("--pdf-dir", default=PDF_DIR, help="Directory with PDFs")
    ap.add_argument("--db-dir", default=CHROMA_DIR, help="ChromaDB output directory")
    ap.add_argument("--query", type=str, help="Run a test query after ingestion")
    ap.add_argument("--query-only", action="store_true",
                    help="Skip ingestion, just query existing DB")
    args = ap.parse_args()

    if args.query_only and args.query:
        query_test(args.db_dir, args.query)
        return

    if args.query_only:
        print("Use --query 'your question' with --query-only")
        return

    # Run ingestion
    ingest(args.pdf_dir, args.db_dir)

    # Run test query if provided
    if args.query:
        query_test(args.db_dir, args.query)
    else:
        # Run a default demo query
        print("\n" + "="*50)
        print("🧪 Running demo query...\n")
        query_test(args.db_dir, "What crops to grow during drought in Maharashtra?")

        print("="*50)
        print("""
Try more queries:

  python ingest_pdfs.py --query-only --query "rice pest management Odisha"
  python ingest_pdfs.py --query-only --query "irrigation strategy for Rajasthan drought"
  python ingest_pdfs.py --query-only --query "kharif crop alternatives delayed monsoon Bihar"
  python ingest_pdfs.py --query-only --query "flood contingency plan coastal Andhra Pradesh"
""")


if __name__ == "__main__":
    main()