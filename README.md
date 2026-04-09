# Hyper-local Agricultural Advisory System for India

An AI-powered, RAG-based (Retrieval-Augmented Generation) system designed to provide district-level, climate-resilient agricultural advice to Indian farmers. By digitizing and processing **ICAR-CRIDA District Agriculture Contingency Plans**, this system transforms static PDFs into an interactive expert advisor.

## The Vision
Indian agriculture is highly diverse, spanning 127 agro-climatic zones. Most advice is too general; our system provides **hyper-local** strategies for specific weather contingencies like:
* **Delayed Monsoons:** Alternative crop recommendations.
* **Drought Management:** Mid-season and terminal drought agronomic measures.
* **Pest & Disease Outbreaks:** Precise chemical dosages and organic management based on district profiles.

## Technical Stack
* **Language:** Python 3.11+
* **Orchestration:** [LangChain](https://github.com/langchain-ai/langchain)
* **Vector Database:** [ChromaDB](https://www.trychroma.com/) (Local persistent storage)
* **Embeddings:** `all-MiniLM-L6-v2` (Sentence-Transformers)
* **LLM Backend:** [Ollama](https://ollama.com/) running **Mistral 7B**
* **PDF Processing:** `PyPDF`

## Project Structure
```text
.
├── crida_plans/          # Downloaded PDF knowledge base
├── chroma_db/            # Persistent vector database
├── logs/                 # Download and execution logs
├── docs/                 # Detailed Wiki and evaluation files
├── Download_crida_plans.py     # Data acquisition script
├── ingest_pdfs.py        # Vectorization & metadata enrichment pipeline
├── query_rag.py          # LLM-powered advisory interface
└── requirements.txt      # Project dependencies
````

## Installation & Setup

1. Prerequisites

    Python 3.11+

    Ollama: [Download here](https://ollama.com/)
   
    After installing, run: `ollama pull mistral`

2. Environment Setup
```bash
  # Create and activate virtual environment
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  # Install dependencies
  `pip install -r requirements.txt`
````

## Usage Flow
### Phase 1: Data Acquisition

Download the contingency plans for your target states.

`python download_crida_plans.py --states Bihar,Odisha,Maharashtra --extras`

### Phase 2: Ingestion & Vectorization

Process the PDFs into the vector database. This adds location-aware metadata to every chunk.
Bash

`python ingest_pdfs.py`

### Phase 3: Query the Advisor

Ask complex agricultural questions.
```bash
# Interactive Mode
python query_rag.py --interactive

# Direct Query
python query_rag.py "What are the alternative crops for delayed monsoon in Patna?"
````
## Metadata Enrichment Logic

To ensure accuracy, the system prepends geographical context to every document chunk:
`[State: {State} | District: {District}] {Content}`
This ensures that the AI remains grounded in the specific local context during retrieval.

## License

This project is for research and educational purposes, utilizing public data provided by ICAR-CRIDA.

***
Note: Always verify AI-generated chemical dosages with local agricultural officers before application.
