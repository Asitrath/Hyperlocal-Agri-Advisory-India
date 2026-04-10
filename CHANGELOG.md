# Changelog

## [0.1.1] - 2026-04-07
### Added
- Executed initial download for Bihar and Odisha.
- Successfully retrieved 68 district PDFs.
- Completed full 5-state download (Andhra, Rajasthan, Maharashtra, Bihar, Odisha) totaling 125 PDFs.
- Acquired 4 core ICAR agricultural handbooks into `_handbooks` directory.
- Installed core RAG stack: `langchain`, `langchain-community`, `chromadb`, `pypdf`.
- Added `sentence-transformers` for local vector embeddings.
- Verified `pypdf` compatibility with CRIDA PDF formats.

## [0.2.0] - 2026-04-08
### Added
- `ingest_pdfs.py`: Core ingestion pipeline for vectorization.
- Metadata extraction logic for States, Districts, and Agro-climatic zones.
- Vector database integration using ChromaDB.
- Local embedding support via `all-MiniLM-L6-v2`.
- Location-aware search: Prefixed location context to chunks for better retrieval.
- Created `evaluation.md` to track RAG retrieval accuracy and identify "Table Fragmentation" issues.

### Changed
- Increased chunk size to 1500 to accommodate dense agricultural tables.

## [0.3.0] - 2026-04-08
### Added
- `query_rag.py`: Generative pipeline using Ollama and Mistral.
- Streaming response support for a better user experience.
- Interactive mode with `@State` filtering shortcuts.
- Strict System Prompting to minimize LLM hallucinations.
- Documented external dependency: Ollama (Mistral 7B).
- Added hardware recommendations and setup commands to Wiki.
- **Created "Page 7: Safety & AI Ethics" in Wiki to document hallucination risks and advisory limitations.**

### Changed
- Shifted from raw chunk display to natural language advisory generation.

## [0.4.0] - 2026-04-09
### Added
- Integrated `weather.py` into the main `query_rag.py` pipeline.
- Added `/weather` and `/noweather` commands to the Interactive Mode.
- Implemented automatic district/state detection from natural language queries.
- Added WMO weather code interpretation for human-readable weather descriptions.

### Changed
- Updated `SYSTEM_PROMPT` to prioritize weather data when available.
- Improved error handling for Ollama connection timeouts.
- Suppressed TensorFlow/Tokenizer parallelism warnings for a cleaner CLI output.

## [0.5.0] - 2026-04-10
### Added
- `telegram_bot.py`: Launched an asynchronous Telegram interface for mobile accessibility.
- Implemented core bot commands: `/start`, `/help`, `/weather`, `/state`, and `/reset`.
- Integrated "Typing" indicators to improve user experience during RAG processing.
- Added `SCORE_THRESHOLD` logic to ensure only high-relevance document chunks are used for generation.
- Created "Page 9: Telegram Bot Interface" in the Wiki to document mobile architecture.

### Changed
- **Mobile-Optimized Prompting:** Updated the system prompt to enforce a 300-word limit for readable mobile advisories.
- **Non-Streaming Inference:** Optimized Ollama calls for Telegram's message delivery model to prevent fragmented responses.
- **Persistence:** Enabled `user_data` session tracking to remember a user's selected State filter across multiple queries.

### Fixed
- Improved district detection logic to handle natural language mentions within Telegram messages.
- Resolved Markdown parsing issues for Telegram when rendering weather code blocks.

## [0.5.1] - 2026-04-10
### Added
- Created `_schemes` directory to house major national agricultural policy documents.
- Ingested PMFBY (Insurance), PM-KISAN (Direct Income), and RKVY (Infrastructure) PDFs.
- Updated `ingest_pdfs.py` with scheme-specific metadata tagging for higher retrieval precision.