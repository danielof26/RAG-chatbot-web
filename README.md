# RAG Chatbot Web

A web platform for building, configuring and evaluating RAG (Retrieval-Augmented Generation) chatbot agents over custom document collections.

## Requirements

- Python 3.10+
- Node.js 18+
- MongoDB running on `localhost:27017`
- [Ollama](https://ollama.com) with at least one LLM and one embedding model pulled — can run locally or on a remote server (configurable per agent via the LLM Server settings). OpenAI and Gemini are also supported as providers.

## Installation

**Backend**

```bash
cd backend
pip install -r requirements.txt
python app.py
```

**Frontend** (development)

```bash
cd frontend
npm install
npm run dev      # Vite dev server with hot reload — proxies /api to localhost:5001
```

**Frontend** (production / VM deployment)

```bash
cd frontend
npm install
npm run build    # Builds static files into frontend/dist/
```

Flask automatically serves the built frontend from `frontend/dist/` — no separate server needed.

## Configuration

Edit `backend/config.py` to change defaults:

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017/rag_chatbot` | MongoDB connection |
| `CHROMA_PATH` | `./chromadb_data` | ChromaDB vector store path |
| `UPLOADS_PATH` | `./uploads` | Uploaded document storage |
| `DEFAULT_LLM` | `llama3.2:3b` | Default LLM model |
| `DEFAULT_EMBED_MODEL` | `snowflake-arctic-embed2` | Default embedding model |
| `OLLAMA_LLM_URL` | `http://localhost:11434` | Ollama LLM server |
| `OLLAMA_EMBED_URL` | `http://localhost:11434` | Ollama embedding server |

## Project structure

```
RAG-chatbot-web/
├── backend/
│   ├── app.py                  # Flask entry point (port 5001)
│   ├── config.py               # Configuration
│   ├── requirements.txt
│   ├── routes/                 # API routes (agents, documents, evaluations…)
│   └── services/
│       ├── rag_engine.py       # RAG pipeline core
│       ├── rag_service.py      # Agent query & streaming
│       ├── query_strategies.py # Naive, HyDE, CRAG, Self-RAG, Router, Fusion
│       └── evaluation_service.py # Binary, ROUGE, BERTScore metrics
├── frontend/
│   └── src/
│       └── pages/
│           └── AgentDetail.jsx # Main UI — chat, Advanced config, Evaluation
└── datasets/                   # Evaluation datasets (not versioned)
```

## RAG pipeline stages

The Advanced tab exposes all configurable stages in order:

1. **Pre-retrieval** — Query transformation: Naive, HyDE Answer, HyDE Combined, Adaptive Router
2. **Indexing** — Knowledge base structure: Vector Store Index
3. **Chunking** — Document preprocessing: Fixed-size (chunk_size / chunk_overlap)
4. **Retrieval** — Retriever strategy: Vector Store (dense), Fusion (dense + sparse / BM25 + RRF)
5. **Post-retrieval** — Filtering & reranking: CRAG, Self-RAG, Reranking (cross-encoder), SimilarityPostprocessor
6. **Response synthesis** — Compact, Refine, Tree Summarize, Simple Summarize, Accumulate

## Evaluation metrics

| Metric | Description |
|---|---|
| **Binary** | Keyword-based score — checks how many expected keywords appear in the answer (0–1) |
| **Quality (ROUGE-1)** | Lexical overlap between generated and reference answer |
| **BERTScore** | Semantic similarity using `xlm-roberta-large` contextual embeddings |

Results can be downloaded as CSV (`Question;answer;Binary;Quality;BERT`) from the History panel in the Evaluation tab.
