# Deployment

Adaptive RAG is split into a backend API and a static frontend.

## Backend

Install dependencies:

```bash
cd rag-app/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables:

```env
ANTHROPIC_API_KEY=your_key_here
CORS_ORIGINS=https://your-frontend-domain.com
MAX_CACHED_CONTEXT_CHARS=120000
```

Run with a production ASGI server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

For a managed deployment, put this behind the platform's process manager or a reverse proxy. Persist `backend/faiss_index/` if you want uploaded indexes to survive restarts.

## Frontend

Set the API base URL:

```env
VITE_API_BASE_URL=https://your-api-domain.com
```

Build:

```bash
cd rag-app/frontend
npm install
npm run build
```

Deploy `frontend/dist/` to any static host.

## Local Proxy

During development, Vite proxies `/api/*` to `http://localhost:8000`. In production, use `VITE_API_BASE_URL` or a reverse proxy that routes `/api` to the backend.
