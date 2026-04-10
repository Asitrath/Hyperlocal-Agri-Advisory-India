"""
Agriculture RAG - Weather-Aware Query Pipeline
================================================
Retrieves relevant chunks from ChromaDB, fetches real-time weather
for the detected district, and uses Ollama to generate grounded answers.

Usage:
    python query_rag.py "What should I grow if monsoon is delayed in Patna?"
    python query_rag.py --state Bihar "flood contingency measures"
    python query_rag.py --no-weather "general irrigation advice"
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

# Weather integration
from weather import get_weather_context, detect_district


# ── Configuration ──────────────────────────────────────────────────────────
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "agri_advisory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
TOP_K = 6


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
   state what is NOT covered.
8. If REAL-TIME WEATHER data is provided, use it to make your advice more 
   specific. For example, if rainfall is in deficit, prioritize drought 
   contingency advice. If excess rain is reported, focus on waterlogging and 
   flood measures. Reference the weather data in your answer.
9. If the user asks about government support, subsidies, or insurance, prioritize 
   information from the 'Scheme' documents and explain eligibility or application 
   steps found in the context."""


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
            "temperature": 0.3,
            "num_predict": 1024,
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
    except requests.exceptions.ReadTimeout:
        print("\n✗ Ollama timed out. The model may still be loading.")
        print("  Try: ollama run mistral \"hello\"  (in a separate terminal)")
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
        print()
        return "".join(full_response)
    else:
        data = response.json()
        return data.get("response", "")


def ask(query, state_filter=None, verbose=False, use_weather=True):
    """Full RAG pipeline: detect location -> fetch weather -> retrieve -> generate."""

    # 1. Detect district from query
    detected_district, detected_state = detect_district(query)
    if detected_state and not state_filter:
        state_filter = detected_state

    # 2. Fetch weather if district detected
    weather_context = ""
    if use_weather and detected_district:
        print(f"  Fetching weather for {detected_district.title()}, {detected_state}...")
        weather_context = get_weather_context(detected_district, detected_state)
        if weather_context and verbose:
            print(weather_context)
            print()

    # 3. Retrieve from vector store
    vectorstore = get_vectorstore()
    results = retrieve(vectorstore, query, state_filter)

    # Filter out low-quality matches
    results = [(doc, score) for doc, score in results if score < 1.0]

    if not results:
        print("\nNo relevant documents found for this query.")
        print("This system covers: Bihar, Odisha, Maharashtra, Rajasthan, and Andhra Pradesh.")
        return

    if verbose:
        print(f"  Retrieved {len(results)} chunks:")
        for i, (doc, score) in enumerate(results, 1):
            state = doc.metadata.get("state", "?")
            district = doc.metadata.get("district", "?")
            print(f"   {i}. {state} > {district} (score: {score:.3f})")
        print()

    # 4. Build prompt with weather + document context
    doc_context = format_context(results)

    prompt_parts = [SYSTEM_PROMPT, "\n"]

    if weather_context:
        prompt_parts.append(f"REAL-TIME WEATHER DATA:\n{weather_context}\n\n")

    prompt_parts.append(f"CONTEXT DOCUMENTS:\n{doc_context}\n")
    prompt_parts.append(f"FARMER'S QUESTION: {query}\n\n")
    prompt_parts.append("Based on the context documents and weather data above, provide a helpful and specific answer:")

    prompt = "".join(prompt_parts)

    # 5. Generate
    weather_tag = " [live weather]" if weather_context else ""
    state_info = f" [{state_filter}]" if state_filter else ""
    print(f"\n  Answer{state_info}{weather_tag}:\n")
    response = query_ollama(prompt)

    # 6. Show sources
    print(f"\n  Sources:")
    seen = set()
    for doc, score in results:
        state = doc.metadata.get("state", "?")
        district = doc.metadata.get("district", "?")
        key = f"{state}>{district}"
        if key not in seen:
            seen.add(key)
            print(f"   - {state} -- {district} district")
    if weather_context:
        print(f"   - Open-Meteo weather API (real-time)")

    return response


def interactive_mode(state_filter=None, use_weather=True):
    """Interactive Q&A loop."""
    w_status = "ON" if use_weather else "OFF"
    print(f"""
{'='*55}
  Agriculture Advisory RAG System
  Weather integration: {w_status}
  
  Type your question, or:
    @Bihar ...     -> filter by state
    /weather Patna -> check weather only
    /help          -> show commands
    quit           -> exit
{'='*55}
""")

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        # Commands
        if query.lower() == "/help":
            print("""
  Commands:
    @State query    -> Filter by state (e.g. @Bihar delayed monsoon)
    /weather <dist> -> Show weather for a district
    /noweather      -> Toggle weather off
    /weather on     -> Toggle weather on
    quit            -> Exit
""")
            continue

        if query.lower().startswith("/weather on"):
            use_weather = True
            print("  Weather integration ON")
            continue

        if query.lower() == "/noweather":
            use_weather = False
            print("  Weather integration OFF")
            continue

        if query.lower().startswith("/weather "):
            district_name = query[9:].strip()
            detected, state = detect_district(district_name)
            if detected:
                ctx = get_weather_context(detected, state)
                print(ctx if ctx else f"  Could not fetch weather for {district_name}")
            else:
                ctx = get_weather_context(district_name)
                print(ctx if ctx else f"  District '{district_name}' not in database")
            print()
            continue

        # Check for @State prefix
        current_filter = state_filter
        if query.startswith("@"):
            parts = query.split(" ", 1)
            if len(parts) == 2:
                current_filter = parts[0][1:]
                query = parts[1]

        ask(query, state_filter=current_filter, verbose=True, use_weather=use_weather)
        print()


def main():
    global OLLAMA_MODEL

    ap = argparse.ArgumentParser(description="Agriculture RAG - Weather-Aware Query System")
    ap.add_argument("query", nargs="?", help="Your agriculture question")
    ap.add_argument("--state", type=str, help="Filter by state (e.g. Bihar, Odisha)")
    ap.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    ap.add_argument("--verbose", "-v", action="store_true", help="Show retrieval details")
    ap.add_argument("--model", default=OLLAMA_MODEL, help="Ollama model name")
    ap.add_argument("--no-weather", action="store_true", help="Disable weather integration")
    args = ap.parse_args()

    OLLAMA_MODEL = args.model
    use_weather = not args.no_weather

    if args.interactive:
        interactive_mode(args.state, use_weather)
    elif args.query:
        ask(args.query, state_filter=args.state, verbose=args.verbose, use_weather=use_weather)
    else:
        print("Usage:")
        print('  python query_rag.py "your question here"')
        print('  python query_rag.py --state Bihar "delayed monsoon advice"')
        print('  python query_rag.py --interactive')
        print('  python query_rag.py --no-weather "general query"')


if __name__ == "__main__":
    main()