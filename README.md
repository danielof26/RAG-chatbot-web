# RAG Chatbot Web

A web platform for building, configuring and evaluating RAG (Retrieval-Augmented Generation) chatbot agents over custom document collections.

## Requirements

- Python 3.10+
- Node.js 18+
- MongoDB running on `localhost:27017`
- [Ollama](https://ollama.com) with at least one LLM and one embedding model pulled, can run locally or on a remote server (configurable per agent via the LLM Server settings). OpenAI and Gemini are also supported as providers.

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
npm run dev
```

**Frontend** (production / VM deployment)

```bash
cd frontend
npm install
npm run build
```

Flask automatically serves the built frontend from `frontend/dist/` — no separate server needed.

## Configuration

`backend/config.py` is not versioned (it contains secrets), so each environment creates its own. These are the settings it holds:

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017/rag_chatbot` | MongoDB connection |
| `CHROMA_PATH` | `./chromadb_data` | ChromaDB vector store path |
| `UPLOADS_PATH` | `./uploads` | Uploaded document storage |
| `DEFAULT_LLM` | `llama3.2:3b` | Default LLM model |
| `DEFAULT_EMBED_MODEL` | `snowflake-arctic-embed2` | Default embedding model |
| `JWT_SECRET` | — | Secret used to sign the session tokens (change it in every environment) |
| `JWT_EXPIRATION_HOURS` | `24` | Lifetime of a session token |
| `OLLAMA_LLM_URL` | `http://localhost:11434` | Declared for an Ollama LLM server (the servers actually used are the ones registered in the app) |
| `OLLAMA_EMBED_URL` | `http://localhost:11434` | Declared for an Ollama embedding server (same remark) |
| `ENCRYPTION_KEY` (optional) | — | Fernet key that protects the stored provider API keys. It can also come from the `RAG_ENCRYPTION_KEY` environment variable; if neither is set, `backend/.encryption_key` is created. Back it up: without it the stored keys cannot be recovered |

## Project structure

```
RAG-chatbot-web/
├── backend/
│   ├── app.py                  # Flask entry point (port 5001), also serves the built frontend
│   ├── config.py               # Configuration (not versioned)
│   ├── rag_catalog.py          # Catalog of RAG techniques and their incompatibilities
│   ├── states.py               # Document / evaluation-run states and allowed transitions
│   ├── requirements.txt
│   ├── routes/                 # API routes (auth, agents, llm_servers, api_keys, config_snapshots,
│   │                           #   evaluations, ollama-compatible API, openapi, rag_catalog)
│   ├── middleware/             # JWT authentication, agent ownership, API key check
│   ├── repositories/           # Agent lookup in MongoDB
│   ├── services/
│   │   ├── rag_service.py      # Indexing, engine builders, agent query & streaming
│   │   ├── rag_engine.py       # Engine used by the evaluation (same builders as the chat)
│   │   ├── rag_config.py       # RagConfig defaults and validation
│   │   ├── query_strategies.py # Naive, HyDE, CRAG, Self-RAG
│   │   ├── xai.py              # XAI citation verification
│   │   ├── raptor_retriever.py # RAPTOR tree retriever
│   │   ├── evaluation_service.py # Binary, ROUGE, BERTScore metrics, dataset parsing
│   │   ├── llm_providers.py    # Ollama, Gemini, OpenAI-compatible providers
│   │   └── job_state.py, agent_cleanup.py, secrets_box.py, secret_migration.py
│   └── tests/                  # pytest suite (in-memory fake MongoDB, scripted models)
├── frontend/
│   └── src/
│       ├── pages/              # Login, Agents, LLMServers, AgentDetail
│       │   └── agent/          # One component per tab: General, Documents, Advanced, Evaluation, Chat, API
│       ├── components/         # PrivateRoute, PasswordInput, DownloadDialog
│       ├── evaluation/         # Configuration summary and result export (CSV, JSON, TXT)
│       ├── rag/                # Helpers over the technique catalog
│       ├── api/                # apiClient and useApi
│       └── context/            # AuthContext
├── docs/                       # Pending improvements (not versioned)
├── memoria/                    # Thesis text and figures (not versioned)
└── datasets/                   # Evaluation datasets (not versioned)
```

## RAG pipeline stages

The Advanced tab exposes all configurable stages in order:

1. **Pre-retrieval** — Query transformation: Naive, HyDE Answer, HyDE Combined, Sub-question Engine, Adaptive Router
2. **Indexing** — Knowledge base structure: Vector Store Index
3. **Chunking** — Document preprocessing: Fixed-size (chunk_size / chunk_overlap)
4. **Retrieval** — Retriever strategy: Vector Store (dense), BM25 (sparse), Fusion (dense + sparse / BM25 + RRF), RAPTOR (hierarchical tree)
5. **Post-retrieval** — Filtering & reranking: CRAG, Self-RAG, Reranking (cross-encoder), SimilarityPostprocessor, LongContextReorder, XAI (citation verification, evaluations only)
6. **Response synthesis** — Compact, Refine, Tree Summarize, Simple Summarize, Accumulate

Techniques that cannot work together are locked in the interface (the catalog is served by `GET /api/rag/techniques`). The chat also offers conversational memory (Simple and Condense modes). Techniques marked *soon* in the interface are listed but not implemented yet.

## Evaluation metrics

| Metric | Description |
|---|---|
| **Binary** | Keyword-based score — checks how many expected keywords appear in the answer (0–1) |
| **Quality (ROUGE-1)** | Lexical overlap between generated and reference answer |
| **BERTScore** | Semantic similarity using `xlm-roberta-large` contextual embeddings |

Datasets are CSV (`;` or `,` separated) or Excel `.xlsx` files with the columns `Question`, `Keywords` and, optionally, `Answer`. Results can be downloaded as CSV (`Question;answer;Binary;Quality;BERT`), JSON or TXT from the History panel in the Evaluation tab; every file starts with the configuration of the run (techniques, top_k, LLM and embedding models…).

## Tests

```bash
cd backend && python -m pytest -q     # needs no MongoDB, Ollama or external provider
cd frontend && npm test
```
