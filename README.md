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
* * **Weather API:** [Open-Meteo](https://open-meteo.com/) (Free, no API key)
* **Bot Interface:** [python-telegram-bot](https://python-telegram-bot.org/) (Telegram)

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
├── weather.py            # Open-Meteo real-time weather integration
├── telegram_bot.py       # Telegram bot interface
├── .env                  # Bot token (not committed)
└── requirements.txt      # Project dependencies
````
## Data Coverage
125 district contingency plans across 5 agro-climatic zones:
| State | Districts | Climate Type |
|-------|-----------|-------------|
| Bihar | 38 | Eastern wet, flood-prone |
| Odisha | 30 | Coastal + tribal hinterland |
| Maharashtra | 34 | Semi-arid Deccan + Konkan coast |
| Rajasthan | 11 | Arid/semi-arid western India |
| Andhra Pradesh | 12 | Southern coastal + dryland |

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
### Connection Modes
* **Default:** `python query_rag.py` (Requires internet for live weather context).
* **Offline:** `python query_rag_v1_static.py` (No internet required; uses local PDF data only).

  
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
## Demo
```
$ python query_rag.py "What should I grow if monsoon is delayed by 4 weeks in Patna?"

  Fetching weather for Patna, Bihar...

  Answer [Bihar] [live weather]:

  In case of a 4-week delay in monsoon in Patna (Bihar), you should 
  consider: Rice varieties like Prabhat, Dhanlaxmi suitable for late 
  sowing. Short-duration vegetables such as cauliflower, cabbage, 
  brinjal. For pulses: Pigeonpea (Bahar, Narendra Arhar-1)...

  Sources:
   - Bihar — Patna district
   - Bihar — Aurangabad district
   - Open-Meteo weather API (real-time)
```
## Telegram Bot
For farmer-facing access, a Telegram bot wraps the full RAG pipeline.

1. Get a token from [@BotFather](https://t.me/BotFather)
2. Create `.env` with: `TELEGRAM_BOT_TOKEN=your-token`
3. Run: `python telegram_bot.py`

Bot commands: `/start`, `/weather Patna`, `/state Bihar`, or just type a question.


## Metadata Enrichment Logic

To ensure accuracy, the system prepends geographical context to every document chunk:
`[State: {State} | District: {District}] {Content}`
This ensures that the AI remains grounded in the specific local context during retrieval.

## License

This project is for research and educational purposes, utilizing public data provided by ICAR-CRIDA.

***
Note: Always verify AI-generated chemical dosages with local agricultural officers before application.
