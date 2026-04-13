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

## [0.6.0] - 2026-04-10
### Added
- `run_evaluations.py`: Introduced an automated regression testing suite to verify RAG accuracy.
- **Golden Dataset:** Implemented 5 initial test cases covering Weather-Awareness, Contingency, Schemes, and Safety Guardrails.
- **Automated Logging:** Results are now exported to timestamped JSON reports in `/evaluation_logs` for auditability.
- **Performance Monitoring:** Added latency tracking per query to monitor system speed as the database scales.

## [0.6.1] - 2026-04-13
### Added
- **v2 Evaluation Suite**: Upgraded `run_evaluations.py` with 10 "Golden" test cases across 5 functional categories.
- **LLM-as-a-Judge**: Integrated automated self-grading logic using Mistral to provide subjective quality scores (0-5) and diagnostic reasoning.
- **Markdown Report Generator**: Added automated conversion of JSON evaluation logs into readable Markdown summaries for `docs/EVALUATION.md`.

### Changed
- **Relevance Threshold Tuning**: Increased `RELEVANCE_THRESHOLD` from **1.0 to 1.15** to improve recall for noisier PDF text and resolve "null response" issues.
- **Category Filtering**: Updated evaluation script to allow targeted testing via the `--category` flag.

### Fixed
- **TC02 Regression**: Resolved the silent failure in Solapur district retrieval by adjusting vector distance parameters.
- **Hallucination Guardrails**: Refined the geographic refusal logic to prevent the model from associating out-of-scope cities with incorrect states.

## [0.7.0] - 2026-04-13
### Added
- `mandi_prices.py`: Real-time market data integration using the **Data.gov.in (Agmarknet)** API.
- **MSP Logic**: Hardcoded 2025-26 Minimum Support Prices for 20+ major crops for profit-margin analysis.
- **Market Comparison**: Automated calculation of price variance (Above/Below MSP) to assist in procurement decisions.
- **Commodity Normalization**: Comprehensive alias mapping for regional crop names (e.g., *pyaz, kanda, batata*).

## [0.8.0] - 2026-04-13
### Added
- `translator.py`: A new multilingual module supporting 10 Indian languages (Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, and Odia).
- **"Translation Sandwich" Architecture**: Automated detection and two-way translation of queries and responses to allow regional language interaction with English RAG sources.
- **Agricultural Term Protection**: Implemented a `PRESERVE_TERMS` layer to prevent the mistranslation of variety names (e.g., Prabhat), chemicals, and government schemes.
- **Regex-based Script Detection**: High-speed language detection using Unicode script ranges for Indian scripts.

### Changed
- **Bot Response Pipeline**: Integrated `translator.py` into the main execution flow, enabling the Telegram bot to automatically respond in the user's detected script.

### Technical Dependencies
- Added `deep-translator` as a core dependency for the Google Translate engine integration.