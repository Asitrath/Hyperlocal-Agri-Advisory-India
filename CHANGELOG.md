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