"""
Krishi Advisory Telegram Bot
==============================
Telegram interface for the Hyper-local Agriculture Advisory RAG system.
Farmers can ask questions in plain text and get weather-aware,
district-specific advice grounded in ICAR-CRIDA contingency plans.

Setup:
    1. Get a bot token from @BotFather on Telegram
    2. Set it: export TELEGRAM_BOT_TOKEN="your-token-here"
       Or create a .env file with: TELEGRAM_BOT_TOKEN=your-token-here
    3. Make sure Ollama is running: ollama serve
    4. Run: python telegram_bot.py

Commands:
    /start     - Welcome message and instructions
    /help      - Show available commands
    /weather   - Check weather for a district (e.g. /weather Patna)
    /state     - Set default state filter (e.g. /state Bihar)
    /reset     - Clear state filter
    Any text   - Ask an agriculture question
"""

import os
import sys
import json
import logging
import requests

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Import our RAG components
from weather import get_weather_context, detect_district
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# ── Configuration ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "agri_advisory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
TOP_K = 6
SCORE_THRESHOLD = 1.0  # Reject chunks with score above this

# Try loading from .env file if token not in environment
if not BOT_TOKEN:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    BOT_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")

if not BOT_TOKEN:
    print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable or create a .env file")
    print("  Get a token from @BotFather on Telegram")
    sys.exit(1)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── System prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a STRICT agricultural advisor for Indian farmers, 
answering ONLY from the provided CONTEXT DOCUMENTS (official ICAR-CRIDA 
district contingency plans and government agriculture handbooks).

STRICT RULES:
1. If the context does NOT explicitly cover the crop, location, or topic asked 
   about, say: "The ICAR-CRIDA plans in my database do not cover this query."
2. NEVER use outside knowledge.
3. Always cite the specific district and state.
4. Include specific crop varieties, chemical dosages, and timing when available.
5. Keep language simple — your audience is farmers.
6. For weather contingencies, structure as: (a) Situation (b) Recommended crops 
   (c) Agronomic measures (d) Government scheme linkages.
7. If REAL-TIME WEATHER data is provided, reference it in your answer.
8. Keep answers concise — under 300 words. Farmers read on small screens."""


# ── RAG components (loaded once at startup) ────────────────────────────────
print("Loading embedding model...")
_embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

print("Connecting to ChromaDB...")
_vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=_embeddings,
    collection_name=COLLECTION_NAME,
)
print("RAG system ready!")


# ── Core RAG function ─────────────────────────────────────────────────────
def rag_query(query, state_filter=None, use_weather=True):
    """
    Run the full RAG pipeline and return the answer as a string.
    Returns (answer_text, sources_list, weather_info)
    """
    # Detect district
    detected_district, detected_state = detect_district(query)
    if detected_state and not state_filter:
        state_filter = detected_state

    # Fetch weather
    weather_context = ""
    weather_summary = ""
    if use_weather and detected_district:
        weather_context = get_weather_context(detected_district, detected_state)
        if weather_context:
            weather_summary = f"Weather for {detected_district.title()}, {detected_state}"

    # Retrieve
    search_kwargs = {"k": TOP_K}
    if state_filter:
        search_kwargs["filter"] = {"state": state_filter}
    results = _vectorstore.similarity_search_with_score(query, **search_kwargs)

    # Filter low-quality matches
    results = [(doc, score) for doc, score in results if score < SCORE_THRESHOLD]

    if not results:
        return (
            "The ICAR-CRIDA contingency plans in my database do not have "
            "relevant information for this query.\n\n"
            "I cover districts in: Bihar, Odisha, Maharashtra, Rajasthan, "
            "and Andhra Pradesh.",
            [],
            weather_summary,
        )

    # Format context
    context_parts = []
    for i, (doc, score) in enumerate(results, 1):
        state = doc.metadata.get("state", "Unknown")
        district = doc.metadata.get("district", "Unknown")
        page = doc.metadata.get("page", "?")
        content = doc.page_content
        if content.startswith("["):
            content = content.split("] ", 1)[-1]
        context_parts.append(
            f"--- Document {i} ({state}, {district}, p.{page}) ---\n{content}\n"
        )
    doc_context = "\n".join(context_parts)

    # Build prompt
    prompt_parts = [SYSTEM_PROMPT, "\n"]
    if weather_context:
        prompt_parts.append(f"REAL-TIME WEATHER:\n{weather_context}\n\n")
    prompt_parts.append(f"CONTEXT DOCUMENTS:\n{doc_context}\n")
    prompt_parts.append(f"FARMER'S QUESTION: {query}\n\n")
    prompt_parts.append("Provide a helpful, concise answer:")
    prompt = "".join(prompt_parts)

    # Call Ollama (non-streaming for Telegram)
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 800, "top_p": 0.9},
            },
            timeout=300,
        )
        resp.raise_for_status()
        answer = resp.json().get("response", "Sorry, I could not generate an answer.")
    except requests.ConnectionError:
        answer = "Cannot connect to Ollama. Please make sure it is running (ollama serve)."
    except requests.exceptions.ReadTimeout:
        answer = "The AI model took too long to respond. Please try a shorter question."
    except Exception as e:
        answer = f"Error generating answer: {str(e)}"

    # Collect sources
    sources = []
    seen = set()
    for doc, score in results:
        state = doc.metadata.get("state", "?")
        district = doc.metadata.get("district", "?")
        key = f"{state}>{district}"
        if key not in seen:
            seen.add(key)
            sources.append(f"{state} — {district}")

    return answer, sources, weather_summary


# ── Telegram handlers ─────────────────────────────────────────────────────
WELCOME_MSG = """
🌾 *Krishi Advisory Bot*
District-level agriculture advice powered by ICAR-CRIDA contingency plans.

*How to use:*
Just type your question! For example:
• "What to grow if monsoon is delayed in Patna?"
• "Rice pest control in Sundargarh Odisha"
• "Drought management for Solapur"

*Commands:*
/weather Patna — Check live weather for a district
/state Bihar — Set state filter for all queries
/reset — Clear state filter
/help — Show this message

*Coverage:* Bihar, Odisha, Maharashtra, Rajasthan, Andhra Pradesh (125 districts)

⚠️ Always verify chemical dosages with your local agriculture officer.
"""

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(WELCOME_MSG, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(WELCOME_MSG, parse_mode="Markdown")


async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weather <district> command."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /weather <district name>\n"
            "Example: /weather Patna"
        )
        return

    district_name = " ".join(context.args)
    detected, state = detect_district(district_name)

    if detected:
        weather = get_weather_context(detected, state)
        if weather:
            await update.message.reply_text(f"```\n{weather}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Could not fetch weather for {district_name}.")
    else:
        # Try direct lookup
        weather = get_weather_context(district_name)
        if weather:
            await update.message.reply_text(f"```\n{weather}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"District '{district_name}' not found in my database.\n"
                "I cover districts in Bihar, Odisha, Maharashtra, Rajasthan, and Andhra Pradesh."
            )


async def cmd_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /state <name> - set default state filter."""
    if not context.args:
        current = context.user_data.get("state_filter")
        if current:
            await update.message.reply_text(f"Current filter: {current}\nUse /reset to clear.")
        else:
            await update.message.reply_text(
                "No state filter set.\n"
                "Usage: /state Bihar\n"
                "Options: Bihar, Odisha, Maharashtra, Rajasthan, Andhra Pradesh"
            )
        return

    state = " ".join(context.args)
    valid_states = ["Bihar", "Odisha", "Maharashtra", "Rajasthan", "Andhra Pradesh"]
    matched = [s for s in valid_states if s.lower().startswith(state.lower())]

    if matched:
        context.user_data["state_filter"] = matched[0]
        await update.message.reply_text(f"State filter set to: *{matched[0]}*", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Unknown state: {state}\n"
            f"Available: {', '.join(valid_states)}"
        )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset - clear state filter."""
    context.user_data.pop("state_filter", None)
    await update.message.reply_text("State filter cleared. Searching all states now.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message as an agriculture query."""
    query = update.message.text.strip()
    if not query:
        return

    user = update.effective_user
    logger.info(f"Query from {user.first_name} ({user.id}): {query}")

    # Send "typing" indicator
    await update.message.chat.send_action("typing")

    # Get state filter if set
    state_filter = context.user_data.get("state_filter")

    # Run RAG pipeline
    answer, sources, weather_info = rag_query(query, state_filter=state_filter)

    # Format response
    response_parts = []

    if weather_info:
        response_parts.append(f"🌤️ {weather_info}\n")

    response_parts.append(answer)

    if sources:
        response_parts.append("\n\n📍 *Sources:*")
        for src in sources[:5]:
            response_parts.append(f"  • {src}")

    response = "\n".join(response_parts)

    # Telegram has a 4096 char limit
    if len(response) > 4000:
        response = response[:3950] + "\n\n... (truncated)"

    try:
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception:
        # If Markdown parsing fails, send without formatting
        await update.message.reply_text(response)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Error: {context.error}", exc_info=context.error)


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print(f"Starting Krishi Advisory Bot...")
    print(f"  Ollama model: {OLLAMA_MODEL}")
    print(f"  ChromaDB: {CHROMA_DIR}")
    print(f"  Score threshold: {SCORE_THRESHOLD}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("weather", cmd_weather))
    app.add_handler(CommandHandler("state", cmd_state))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("\nBot is running! Send a message to your bot on Telegram.")
    print("Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()