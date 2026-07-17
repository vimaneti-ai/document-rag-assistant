# Setup

## Prerequisites

- macOS, Linux, or another Unix-like environment
- Python 3.11 recommended
- Node.js 18 or newer
- An Anthropic API key
- A Pinecone account and API key
- A strong app username and password for Basic authentication

## Backend

```bash
cd rag-app/backend
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=your_key_here
PINECONE_API_KEY=your_pinecone_key_here
PINECONE_INDEX_NAME=document-rag-assistant
PINECONE_NAMESPACE=adaptive-rag
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
APP_BASIC_AUTH_USERNAME=admin
APP_BASIC_AUTH_PASSWORD=use-a-long-random-password
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_UPLOAD_MB=25
MAX_CACHED_CONTEXT_CHARS=120000
```

Install and run:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend creates the Pinecone serverless index automatically on the first
upload if `PINECONE_INDEX_NAME` does not already exist. The index uses 384
dimensions and cosine similarity for `all-MiniLM-L6-v2`.

Health and authenticated status checks:

```bash
curl http://127.0.0.1:8000/health
curl -u admin:use-a-long-random-password http://127.0.0.1:8000/status
```

## Frontend

From the repository root:

```bash
cd rag-app/frontend
cp .env.example .env
npm install
npm run dev
```

If your terminal is still inside `rag-app/backend`, use `cd ../frontend` instead.

Open `http://localhost:5173`.

Sign in with the `APP_BASIC_AUTH_USERNAME` and `APP_BASIC_AUTH_PASSWORD` values from `rag-app/backend/.env`.

The frontend signs users out after three minutes without keyboard, pointer,
touch, or scroll activity. Change the local timeout in `frontend/.env`:

```env
VITE_INACTIVITY_TIMEOUT_MS=180000
```

Use `120000` for two minutes or `180000` for three minutes. Restart the Vite
development server after changing a frontend environment variable.

## First Run Notes

- The embedding model downloads from Hugging Face on first use.
- Uploaded document vectors and chunk metadata are stored in Pinecone.
- The configured Pinecone namespace contains one active document at a time.
- The Pinecone API key must have permission to create and use the configured index.
- Uploads are limited by `MAX_UPLOAD_MB`; use 10-25 MB for public demos.
- Python virtual environments and `node_modules/` are generated locally and intentionally ignored by git.
- The first Claude request after upload usually writes the prompt cache.
- Later requests can read the cache and should show cache-hit status in the UI.
- Claude Haiku 4.5 requires at least 4,096 cacheable tokens. Shorter documents
  work normally but display `Not cached`.
- The default cache lifetime is five minutes and is refreshed by cache hits.
- Reference: [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).
