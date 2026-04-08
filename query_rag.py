"""
Agriculture RAG - Query Pipeline with Ollama
==============================================
Retrieves relevant chunks from ChromaDB and uses Ollama (Mistral)
to generate natural language answers grounded in the documents.

Usage:
    python query_rag.py "What should I grow if monsoon is delayed in Patna?"
    python query_rag.py "Rice pest control in Odisha"
    python query_rag.py "Drought management for Solapur Maharashtra"
    python query_rag.py --state Bihar "flood contingency measures"
    python query_rag.py --interactive
"""
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"


import sys
import argparse
import requests
import json

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


# ── Configuration ──────────────────────────────────────────────────────────
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "agri_advisory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
TOP_K = 6  # Number of chunks to retrieve


# ── System prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a STRICT agricultural advisor for Indian farmers, 
answering ONLY from the provided CONTEXT DOCUMENTS (official ICAR-CRIDA 
district contingency plans and government agriculture handbooks).

STRICT RULES:
1. If the context does NOT explicitly cover the crop, location, or topic asked 
   about, you MUST say: "The official ICAR-CRIDA contingency plans in my 
   database do not cover this specific query."
2. NEVER use outside knowledge. Do NOT mention regions, varieties, chemicals, 
   or practices not found in the context documents.
3. Always cite the specific district and state from the context.
4. Include specific crop varieties, chemical dosages, and timing when available 
   in the context.
5. Keep language simple and practical — your audience is farmers and field officers.
6. For weather contingency questions (drought, flood, delayed monsoon), structure 
   your answer as:
   (a) The situation
   (b) Recommended crops/varieties from the context
   (c) Agronomic measures mentioned
   (d) Any government scheme linkages mentioned
7. If the context partially covers the query, answer what you can and clearly 
   state what is NOT covered."""


def get_vectorstore():
    """Load the ChromaDB vector store."""
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


def retrieve(vectorstore, query, state_filter=None, k=TOP_K):
    """Retrieve relevant chunks, optionally filtered by state."""
    search_kwargs = {"k": k}
    if state_filter:
        search_kwargs["filter"] = {"state": state_filter}

    results = vectorstore.similarity_search_with_score(query, **search_kwargs)
    return results


def format_context(results):
    """Format retrieved chunks into a context string for the LLM."""
    context_parts = []
    for i, (doc, score) in enumerate(results, 1):
        state = doc.metadata.get("state", "Unknown")
        district = doc.metadata.get("district", "Unknown")
        page = doc.metadata.get("page", "?")

        # Remove the location prefix we added during ingestion
        content = doc.page_content
        if content.startswith("["):
            content = content.split("] ", 1)[-1]

        context_parts.append(
            f"--- Document {i} (State: {state}, District: {district}, Page: {page}) ---\n"
            f"{content}\n"
        )

    return "\n".join(context_parts)


def query_ollama(prompt, stream=True):
    """Send prompt to Ollama and stream the response."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": stream,
        "options": {
            "temperature": 0.3,      # Low temperature for factual answers
            "num_predict": 1024,      # Max tokens in response
            "top_p": 0.9,
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=stream, timeout=(10, 300))
        response.raise_for_status()
    except requests.ConnectionError:
        print("\n✗ Cannot connect to Ollama. Make sure it's running:")
        print("  ollama serve")
        print(f"  ollama pull {OLLAMA_MODEL}")
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"\n✗ Ollama error: {e}")
        sys.exit(1)

    if stream:
        full_response = []
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                token = data.get("response", "")
                print(token, end="", flush=True)
                full_response.append(token)
                if data.get("done", False):
                    break
        print()  # newline after streaming
        return "".join(full_response)
    else:
        data = response.json()
        return data.get("response", "")


def ask(query, state_filter=None, verbose=False):
    """Full RAG pipeline: retrieve + generate."""

    # 1. Retrieve
    vectorstore = get_vectorstore()
    results = retrieve(vectorstore, query, state_filter)

    if not results:
        print("No relevant documents found.")
        return

    if verbose:
        print(f"\n📚 Retrieved {len(results)} chunks:")
        for i, (doc, score) in enumerate(results, 1):
            state = doc.metadata.get("state", "?")
            district = doc.metadata.get("district", "?")
            print(f"   {i}. {state} > {district} (score: {score:.3f})")
        print()

    # 2. Build prompt
    context = format_context(results)

    prompt = f"""{SYSTEM_PROMPT}

CONTEXT DOCUMENTS:
{context}

FARMER'S QUESTION: {query}

Based on the context documents above, provide a helpful and specific answer:"""

    # 3. Generate
    state_info = f" (filtered: {state_filter})" if state_filter else ""
    print(f"\n🌾 Answer{state_info}:\n")
    response = query_ollama(prompt)

    # 4. Show sources
    print(f"\n📍 Sources:")
    seen = set()
    for doc, score in results:
        state = doc.metadata.get("state", "?")
        district = doc.metadata.get("district", "?")
        key = f"{state}>{district}"
        if key not in seen:
            seen.add(key)
            print(f"   • {state} — {district} district")

    return response


def interactive_mode(state_filter=None):
    """Interactive Q&A loop."""
    print("\n" + "="*55)
    print("  🌾 Agriculture Advisory RAG System")
    print("  Type your question, or 'quit' to exit")
    print("  Prefix with @State to filter, e.g. @Bihar")
    print("="*55 + "\n")

    while True:
        try:
            query = input("🧑‍🌾 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        # Check for @State prefix
        current_filter = state_filter
        if query.startswith("@"):
            parts = query.split(" ", 1)
            if len(parts) == 2:
                current_filter = parts[0][1:]  # Remove @
                query = parts[1]

        ask(query, state_filter=current_filter, verbose=True)
        print()


def main():
    global OLLAMA_MODEL
    ap = argparse.ArgumentParser(description="Agriculture RAG Query System")
    ap.add_argument("query", nargs="?", help="Your agriculture question")
    ap.add_argument("--state", type=str, help="Filter by state (e.g. Bihar, Odisha)")
    ap.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    ap.add_argument("--verbose", "-v", action="store_true", help="Show retrieval details")
    ap.add_argument("--model", default=OLLAMA_MODEL, help="Ollama model name")
    args = ap.parse_args()

    OLLAMA_MODEL = args.model

    if args.interactive:
        interactive_mode(args.state)
    elif args.query:
        ask(args.query, state_filter=args.state, verbose=args.verbose)
    else:
        print("Usage:")
        print('  python query_rag.py "your question here"')
        print('  python query_rag.py --state Bihar "delayed monsoon advice"')
        print('  python query_rag.py --interactive')


if __name__ == "__main__":
    main()