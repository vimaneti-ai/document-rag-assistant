# Adaptive RAG

Adaptive RAG is a production-oriented Retrieval-Augmented Generation app with a FastAPI backend and a React + TypeScript frontend.

The application source lives in [`rag-app/`](./rag-app), with separate backend and frontend projects.

## What It Uses

- Backend: FastAPI, Claude API, FAISS, sentence-transformers
- Frontend: React 18, TypeScript, Tailwind CSS, Axios
- Vector store: local FAISS persisted under `rag-app/backend/faiss_index/`
- Embeddings: `all-MiniLM-L6-v2`
- LLM: `claude-haiku-4-5` with prompt caching
- Documents: PDF, TXT, DOCX, CSV, MD

## Quick Start

```bash
cd rag-app/backend
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

In another terminal:

```bash
cd rag-app/frontend
npm install
npm run dev
```

If your terminal is currently in `rag-app/backend`, use:

```bash
cd ../frontend
```

Open `http://localhost:5173`.

## Documentation

- [Setup](./rag-app/docs/SETUP.md)
- [API](./rag-app/docs/API.md)
- [Deployment](./rag-app/docs/DEPLOYMENT.md)
- [Production Notes](./rag-app/docs/PRODUCTION.md)
