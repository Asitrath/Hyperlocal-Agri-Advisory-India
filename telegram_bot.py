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
    /price     - Check mandi prices (e.g. /price onion Maharashtra)
    /lang      - Show supported languages
    /stats     - Show feedback statistics
    Any text   - Ask an agriculture question
"""

import os
import sys
import json
import logging
import requests
import time

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Import our RAG components
from weather import get_weather_context, detect_district
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from mandi_prices import get_price_context, detect_commodity
from translator import detect_language, translate_query, translate_response, get_language_flag
from feedback import FeedbackStore

# ── Configuration ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "agri_advisory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
TOP_K = 8
SCORE_THRESHOLD = 1.15  # Reject chunks with score above this

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

# Bilingual safety disclaimer appended to every response
DISCLAIMER = (
    "\n\n⚠️ सत्यापन: रासायनिक खुराक की पुष्टि अपने स्थानीय KVK से करें।"
    "\n⚠️ Verify dosages with your local KVK before application."
)


# ── System prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a STRICT agricultural advisor for Indian farmers, 
answering ONLY from the provided CONTEXT DOCUMENTS (official ICAR-CRIDA 
district contingency plans and government agriculture handbooks).

STRICT RULES:
1a. If the context does NOT explicitly cover the crop, location, or topic asked 
   about, you MUST say: "The official ICAR-CRIDA contingency plans in my 
   database do not cover this specific query."
1b. After stating the query is not covered, STOP. Do NOT add "However" or 
    any general advice. Your response must end after the refusal.
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
   steps found in the context.
10. If MARKET PRICE DATA is provided, reference the actual prices in your answer.
   Compare with MSP when available. If market price is BELOW MSP, clearly warn 
   the farmer and suggest: (a) selling through government procurement centres, 
   (b) storing if they have facilities, (c) checking PMFBY claim eligibility.
   If NO MSP exists for the crop (onion, potato, tomato), note this and suggest 
   the farmer compare prices across nearby mandis before selling.
11. NEVER generate URLs or website links. If the farmer needs online resources, 
    say "contact your local KVK or agriculture extension office."""


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

print("Initializing feedback store...")
feedback_store = FeedbackStore()
print("Feedback store ready!")


# ── Core RAG function ─────────────────────────────────────────────────────
def rag_query(query, state_filter=None, use_weather=True):
    """
    Run the full RAG pipeline and return the answer as a string.
    Returns (answer_text, sources_list, weather_info, prices_used)
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

    # Fetch mandi prices if commodity detected
    price_context = ""
    prices_used = False
    detected_commodity = detect_commodity(query)
    if detected_commodity:
        price_context = get_price_context(detected_commodity, state_filter)
        if price_context:
            prices_used = True

    # Retrieve
    search_kwargs = {"k": TOP_K}
    if state_filter:
        search_kwargs["filter"] = {"state": state_filter}
    results = _vectorstore.similarity_search_with_score(query, **search_kwargs)

    # Filter low-quality matches
    threshold = 1.3 if state_filter else SCORE_THRESHOLD
    results = [(doc, score) for doc, score in results if score < threshold]

    if not results:
        return (
            "The ICAR-CRIDA contingency plans in my database do not have "
            "relevant information for this query.\n\n"
            "I cover districts in: Bihar, Odisha, Maharashtra, Rajasthan, "
            "and Andhra Pradesh.",
            [],
            weather_summary,
            prices_used,
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
    if price_context:
        prompt_parts.append(f"MARKET PRICE DATA:\n{price_context}\n\n")
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

    return answer, sources, weather_summary, prices_used


# ── Telegram handlers ─────────────────────────────────────────────────────
WELCOME_MSG = """
🌾 *Krishi Advisory Bot*
District-level agriculture advice powered by ICAR-CRIDA contingency plans.

*How to use:*
Just type your question in any language! For example:
• "What to grow if monsoon is delayed in Patna?"
• "पटना में सूखा पड़ रहा है, कौन सी फसल उगाऊं?"
• "Rice pest control in Sundargarh Odisha"

*Commands:*
/weather Patna — Check live weather for a district
/price onion Maharashtra — Check mandi prices
/state Bihar — Set state filter for all queries
/reset — Clear state filter
/lang — Show supported languages
/help — Show this message

*Coverage:* Bihar, Odisha, Maharashtra, Rajasthan, Andhra Pradesh (125 districts)
*Languages:* Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, English

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


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price <commodity> [state] command."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /price <commodity> [state]\n"
            "Examples:\n"
            "  /price wheat Bihar\n"
            "  /price onion Maharashtra\n"
            "  /price rice"
        )
        return

    commodity = context.args[0]
    state = " ".join(context.args[1:]) if len(context.args) > 1 else None

    await update.message.chat.send_action("typing")
    ctx = get_price_context(commodity, state)
    if ctx:
        await update.message.reply_text(f"```\n{ctx}\n```", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"No price data found for {commodity}" +
            (f" in {state}" if state else "") +
            ".\nTry: /price wheat Bihar"
        )


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /lang command — show supported languages."""
    await update.message.reply_text(
        "*Supported Languages*\n\n"
        "Just type your question in any of these languages:\n\n"
        "हिंदी (Hindi)\n"
        "मराठी (Marathi)\n"
        "বাংলা (Bengali)\n"
        "తెలుగు (Telugu)\n"
        "தமிழ் (Tamil)\n"
        "ગુજરાતી (Gujarati)\n"
        "ಕನ್ನಡ (Kannada)\n"
        "മലയാളം (Malayalam)\n"
        "ਪੰਜਾਬੀ (Punjabi)\n"
        "ଓଡ଼ିଆ (Odia)\n"
        "English\n\n"
        "The bot auto-detects your language — no setup needed!",
        parse_mode="Markdown"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show feedback statistics."""
    stats = feedback_store.get_stats()

    lang_lines = ""
    for lang, count in stats["languages"].items():
        lang_lines += f"    {lang}: {count}\n"

    msg = (
        f"📊 *Bot Statistics*\n\n"
        f"Total queries: {stats['total_queries']}\n"
        f"Unique users: {stats['unique_users']}\n"
        f"👍 Positive: {stats['positive']}\n"
        f"👎 Negative: {stats['negative']}\n"
        f"No feedback: {stats['no_feedback']}\n"
        f"Satisfaction: {stats['satisfaction_rate']}\n"
        f"Avg latency: {stats['avg_latency_sec']}s\n"
    )
    if lang_lines:
        msg += f"\nLanguages:\n{lang_lines}"

    try:
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message as an agriculture query."""
    query = update.message.text.strip()
    if not query:
        return

    user = update.effective_user
    logger.info(f"Query from {user.first_name} ({user.id}): {query}")

    # Send "typing" indicator
    await update.message.chat.send_action("typing")

    # 1. Detect language and translate if needed
    user_lang = detect_language(query)
    english_query = query

    if user_lang != "en":
        english_query, user_lang = translate_query(query, user_lang)
        lang_label = get_language_flag(user_lang)
        logger.info(f"  Translated from {lang_label}: {english_query}")

    # 2. Get state filter if set
    state_filter = context.user_data.get("state_filter")

    # 3. Run RAG pipeline with English query
    start_time = time.time()
    answer, sources, weather_info, prices_used = rag_query(
        english_query, state_filter=state_filter
    )
    latency = round(time.time() - start_time, 2)

    # 4. Translate response back if needed
    if user_lang != "en":
        answer = translate_response(answer, user_lang)

    # 5. Format response with disclaimer
    response_parts = []

    if weather_info:
        response_parts.append(f"🌤️ {weather_info}\n")

    response_parts.append(answer)

    if sources:
        response_parts.append("\n\n📍 Sources:")
        for src in sources[:5]:
            response_parts.append(f"  • {src}")

    response_parts.append(DISCLAIMER)

    response = "\n".join(response_parts)

    if len(response) > 4000:
        response = response[:3900] + "\n\n..." + DISCLAIMER

    # 6. Log to feedback database
    query_id = feedback_store.log_query(
        user_id=user.id,
        username=user.first_name,
        query=query,
        translated_query=english_query,
        language=user_lang,
        response=answer,
        sources=sources,
        weather_used=bool(weather_info),
        prices_used=prices_used,
        latency=latency,
    )

    # 7. Create action + feedback buttons
    keyboard_rows = []

    # Quick-action buttons based on what was in the response
    quick_actions = []
    if "PMFBY" in answer or "insurance" in answer.lower() or "bima" in answer.lower():
        quick_actions.append(
            InlineKeyboardButton("📋 PMFBY Claim Steps", callback_data="qa_pmfby")
        )
    if "PM-KISAN" in answer or "pm-kisan" in english_query.lower():
        quick_actions.append(
            InlineKeyboardButton("💰 PM-KISAN Info", callback_data="qa_pmkisan")
        )
    if prices_used or "price" in english_query.lower() or "mandi" in english_query.lower():
        quick_actions.append(
            InlineKeyboardButton("📊 Latest Prices", callback_data="qa_prices")
        )
    if "urea" in answer.lower() or "fertili" in answer.lower():
        quick_actions.append(
            InlineKeyboardButton("🌱 Fertilizer Alts", callback_data="qa_fertilizer")
        )
    if weather_info:
        quick_actions.append(
            InlineKeyboardButton("🌤️ 7-day Forecast", callback_data="qa_weather")
        )

    # Always include a "tell me more" option
    quick_actions.append(
        InlineKeyboardButton("❓ More Details", callback_data=f"qa_more_{query_id}")
    )

    # Arrange in rows of 2
    for i in range(0, len(quick_actions), 2):
        keyboard_rows.append(quick_actions[i:i + 2])

    # Feedback row at the bottom
    keyboard_rows.append([
        InlineKeyboardButton("👍 Helpful", callback_data=f"fb_pos_{query_id}"),
        InlineKeyboardButton("👎 Not helpful", callback_data=f"fb_neg_{query_id}"),
    ])

    keyboard = InlineKeyboardMarkup(keyboard_rows)

    # 8. Send with feedback buttons
    try:
        await update.message.reply_text(response, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(response, reply_markup=keyboard)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button presses (feedback + quick actions)."""
    callback = update.callback_query
    await callback.answer()
    data = callback.data

    # Feedback buttons
    if data.startswith("fb_pos_"):
        query_id = int(data.replace("fb_pos_", ""))
        feedback_store.record_feedback(query_id, "positive")
        await callback.edit_message_reply_markup(reply_markup=None)
        await callback.message.reply_text("🙏 Thank you for your feedback!")
        return

    if data.startswith("fb_neg_"):
        query_id = int(data.replace("fb_neg_", ""))
        feedback_store.record_feedback(query_id, "negative")
        await callback.edit_message_reply_markup(reply_markup=None)
        await callback.message.reply_text(
            "🙏 Thank you. We'll use this to improve our advice."
        )
        return

    # Quick-action buttons — re-query the RAG with expanded prompts
    quick_queries = {
        "qa_pmfby": "How do I file a PMFBY claim? Step by step process",
        "qa_pmkisan": "PM-KISAN eligibility and application process",
        "qa_prices": "Latest mandi prices for major crops in my region",
        "qa_fertilizer": "What are alternatives to urea if there is a shortage?",
        "qa_weather": "What is the 7-day weather forecast and what should I do?",
    }

    if data in quick_queries:
        await callback.message.chat.send_action("typing")
        query = quick_queries[data]
        state_filter = context.user_data.get("state_filter")

        answer, sources, weather_info, _ = rag_query(query, state_filter=state_filter)

        response_parts = [answer]
        if sources:
            response_parts.append("\n\n📍 Sources:")
            for src in sources[:5]:
                response_parts.append(f"  • {src}")
        response_parts.append(DISCLAIMER)

        response = "\n".join(response_parts)
        if len(response) > 4000:
            response = response[:3900] + "\n\n..." + DISCLAIMER

        try:
            await callback.message.reply_text(response, parse_mode="Markdown")
        except Exception:
            await callback.message.reply_text(response)
        return


    # "More details" button — re-query with expansion prompt
    if data.startswith("qa_more_"):
        original_id = int(data.replace("qa_more_", ""))
        conn = feedback_store.conn
        row = conn.execute(
            "SELECT english_query, language FROM queries WHERE id = ?", (original_id,)
        ).fetchone()
        if row:
            original, lang = row
            expanded = f"Give more specific details and exact varieties/dosages for: {original}"
            await callback.message.chat.send_action("typing")
            state_filter = context.user_data.get("state_filter")

            start_time = time.time()
            answer, sources, weather_info, prices_used = rag_query(
                expanded, state_filter=state_filter
            )
            latency = round(time.time() - start_time, 2)

            # Translate back if needed
            if lang and lang != "en":
                answer = translate_response(answer, lang)

            response_parts = [answer]
            if sources:
                response_parts.append("\n\n📍 Sources:")
                for src in sources[:5]:
                    response_parts.append(f"  • {src}")
            response_parts.append(DISCLAIMER)
            response = "\n".join(response_parts)
            if len(response) > 4000:
                response = response[:3900] + "..." + DISCLAIMER

            # Log the expanded query too
            new_id = feedback_store.log_query(
                user_id=callback.from_user.id,
                username=callback.from_user.first_name,
                query=expanded,
                translated_query=expanded,
                language=lang or "en",
                response=answer,
                sources=sources,
                weather_used=bool(weather_info),
                prices_used=prices_used,
                latency=latency,
            )

            # Add feedback buttons
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("👍 Helpful", callback_data=f"fb_pos_{new_id}"),
                InlineKeyboardButton("👎 Not helpful", callback_data=f"fb_neg_{new_id}"),
            ]])

            try:
                await callback.message.reply_text(response, reply_markup=keyboard, parse_mode="Markdown")
            except Exception:
                await callback.message.reply_text(response, reply_markup=keyboard)
        return


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
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(handle_feedback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("\nBot is running! Send a message to your bot on Telegram.")
    print("Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()