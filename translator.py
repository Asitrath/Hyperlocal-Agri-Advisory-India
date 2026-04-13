"""
Translation Module - Hindi & Multilingual Support
====================================================
Provides a "translation sandwich" for the RAG pipeline:
  1. Detect language of incoming query
  2. Translate to English for RAG processing
  3. Translate response back to user's language

Uses deep-translator (Google Translate backend) — free, no API key.

Supported Indian languages:
  hi (Hindi), bn (Bengali), ta (Tamil), te (Telugu), mr (Marathi),
  gu (Gujarati), kn (Kannada), ml (Malayalam), pa (Punjabi), or (Odia)

Usage:
    from translator import translate_query, translate_response, detect_language

    lang = detect_language("मेरे खेत में धान की फसल सूख रही है")
    # Returns: "hi"

    english = translate_query("मेरे खेत में धान की फसल सूख रही है")
    # Returns: "The rice crop in my field is drying up"

    hindi = translate_response("Apply life-saving irrigation immediately", "hi")
    # Returns: "तुरंत जीवन रक्षक सिंचाई लगाएं"

Setup:
    pip install deep-translator
"""

from deep_translator import GoogleTranslator, single_detection
import re


# ── Supported languages ───────────────────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "en": "English",
}

# Agriculture-specific terms that should NOT be translated
# (variety names, chemical names, scheme names)
PRESERVE_TERMS = [
    "PMFBY", "PM-KISAN", "RKVY", "NFSM", "MIDH", "MSP", "KVK",
    "ICAR", "CRIDA", "NPK", "DAP", "MOP",
    "Trichoderma", "Pseudomonas", "Carbendazim", "Mancozeb",
    "Chlorpyriphos", "Imidacloprid", "Propiconazole",
]


def detect_language(text):
    """
    Detect the language of input text.
    Returns language code (e.g., 'hi', 'en', 'mr').
    """
    if not text or not text.strip():
        return "en"

    try:
        # Quick heuristic: check for Devanagari script (Hindi/Marathi)
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"

        # Bengali script
        if re.search(r'[\u0980-\u09FF]', text):
            return "bn"

        # Tamil script
        if re.search(r'[\u0B80-\u0BFF]', text):
            return "ta"

        # Telugu script
        if re.search(r'[\u0C00-\u0C7F]', text):
            return "te"

        # Gujarati script
        if re.search(r'[\u0A80-\u0AFF]', text):
            return "gu"

        # Kannada script
        if re.search(r'[\u0C80-\u0CFF]', text):
            return "kn"

        # Malayalam script
        if re.search(r'[\u0D00-\u0D7F]', text):
            return "ml"

        # Gurmukhi (Punjabi) script
        if re.search(r'[\u0A00-\u0A7F]', text):
            return "pa"

        # Odia script
        if re.search(r'[\u0B00-\u0B7F]', text):
            return "or"

        # Default: assume English
        return "en"

    except Exception:
        return "en"


def translate_query(text, source_lang=None):
    """
    Translate a user query to English for RAG processing.

    Args:
        text: Query in any supported language
        source_lang: Source language code (auto-detected if None)

    Returns:
        (english_text, detected_lang) tuple
    """
    if not text or not text.strip():
        return text, "en"

    if source_lang is None:
        source_lang = detect_language(text)

    # Already English
    if source_lang == "en":
        return text, "en"

    try:
        translated = GoogleTranslator(
            source=source_lang,
            target="en"
        ).translate(text)
        return translated or text, source_lang
    except Exception as e:
        print(f"  Warning: Translation failed ({e}), using original text")
        return text, source_lang


def translate_response(text, target_lang):
    """
    Translate an English response back to the user's language.

    Args:
        text: English response text
        target_lang: Target language code (e.g., 'hi')

    Returns:
        Translated text
    """
    if not text or not text.strip():
        return text

    if target_lang == "en":
        return text

    if target_lang not in SUPPORTED_LANGUAGES:
        return text

    try:
        # Protect agriculture terms from translation
        protected = {}
        for i, term in enumerate(PRESERVE_TERMS):
            placeholder = f"XAGRI{i}X"
            if term in text:
                protected[placeholder] = term
                text = text.replace(term, placeholder)

        # Translate in chunks (Google has character limits)
        chunks = _split_text(text, max_len=4500)
        translated_chunks = []

        for chunk in chunks:
            translated = GoogleTranslator(
                source="en",
                target=target_lang
            ).translate(chunk)
            translated_chunks.append(translated or chunk)

        result = " ".join(translated_chunks)

        # Restore protected terms
        for placeholder, term in protected.items():
            result = result.replace(placeholder, term)

        return result

    except Exception as e:
        print(f"  Warning: Response translation failed ({e})")
        return text


def _split_text(text, max_len=4500):
    """Split text into chunks for translation API limits."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for sentence in text.split(". "):
        if len(current) + len(sentence) + 2 > max_len:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = current + ". " + sentence if current else sentence

    if current:
        chunks.append(current)

    return chunks if chunks else [text]


def get_language_name(code):
    """Get human-readable language name from code."""
    return SUPPORTED_LANGUAGES.get(code, "Unknown")


def get_language_flag(code):
    """Get a display label for the language."""
    flags = {
        "hi": "हिंदी", "bn": "বাংলা", "ta": "தமிழ்",
        "te": "తెలుగు", "mr": "मराठी", "gu": "ગુજરાતી",
        "kn": "ಕನ್ನಡ", "ml": "മലയാളം", "pa": "ਪੰਜਾਬੀ",
        "or": "ଓଡ଼ିଆ", "en": "English",
    }
    return flags.get(code, code)


# ── CLI testing ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        lang = detect_language(text)
        print(f"Detected language: {lang} ({get_language_name(lang)})")

        if lang != "en":
            english, _ = translate_query(text)
            print(f"English: {english}")

            back = translate_response(english, lang)
            print(f"Back to {get_language_name(lang)}: {back}")
        else:
            print("Text is already in English.")
            hindi = translate_response(text, "hi")
            print(f"Hindi: {hindi}")
    else:
        print("Translation Module — Test Mode\n")
        tests = [
            "पटना में बारिश नहीं हो रही है, क्या मुझे सिंचाई करनी चाहिए?",
            "सोलापुर में प्याज का भाव क्या है?",
            "मेरी गेहूं की फसल में रोग लग गया है, क्या करूं?",
            "PMFBY में धान का बीमा कैसे करें?",
            "What crops to grow in delayed monsoon in Patna?",
        ]

        for test in tests:
            lang = detect_language(test)
            print(f"[{lang}] {test[:60]}...")
            if lang != "en":
                eng, _ = translate_query(test)
                print(f"  → EN: {eng}")
            print()