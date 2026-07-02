# Setup

## Prerequisites

- macOS, Linux, or another Unix-like environment
- Python 3.11 recommended
- Node.js 18 or newer
- An Anthropic API key
- A strong app username and password for Basic authentication

## Backend

```bash
cd rag-app/backend
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=your_key_here
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

Health check:

```bash
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

## First Run Notes

- The embedding model downloads from Hugging Face on first use.
- Uploaded document vectors are stored in `backend/faiss_index/`.
- `backend/faiss_index/` is runtime state and is intentionally ignored by git.
- Uploads are limited by `MAX_UPLOAD_MB`; use 10-25 MB for public demos.
- Python virtual environments and `node_modules/` are generated locally and intentionally ignored by git.
- The first Claude request after upload usually writes the prompt cache.
- Later requests can read the cache and should show cache-hit status in the UI.
