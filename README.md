# Document RAG Assistant

Document RAG Assistant is a full-stack Retrieval-Augmented Generation
application built with a FastAPI backend and a React + TypeScript frontend.
Users can upload a document, ask grounded questions, inspect retrieved sources,
and monitor Claude token usage, prompt-cache activity, and estimated cost.

The application source lives in [`rag-app/`](./rag-app), with separate backend
and frontend projects.

## Current Stack

- Backend: Python 3.11, FastAPI, Uvicorn
- Frontend: React 18, TypeScript, Vite, Tailwind CSS, Axios
- LLM: Anthropic `claude-haiku-4-5`
- Vector database: Pinecone serverless
- Embeddings: local `all-MiniLM-L6-v2` sentence-transformer
- Document processing: LangChain text splitters, PyPDF, python-docx
- Supported documents: PDF, DOCX, TXT, MD, CSV
- Authentication: HTTP Basic Auth with frontend session controls

## Architecture

```text
Browser
  |
  | React chat UI, upload controls, session timeout
  v
FastAPI API
  |
  | validation, parsing, chunking
  v
all-MiniLM-L6-v2 local embeddings
  |
  | 384-dimensional dense vectors
  v
Pinecone serverless
  |
  | top 4 chunks + bounded document context
  v
Claude API with prompt caching
  |
  v
Answer, sources, token usage, cache status, and estimated cost
```

## Features

- Upload one active document and split it into overlapping 1,000-character
  chunks with 150-character overlap.
- Reject unsupported, empty, and oversized uploads before processing.
- Store vectors, chunk text, source metadata, and document state in Pinecone.
- Retrieve the four most relevant chunks for each question.
- Use Claude prompt caching for repeated questions over the same document.
- Support multi-turn conversation history.
- Display source citations, input/output/cache tokens, cache hit or miss, and
  estimated request cost.
- Protect API operations with HTTP Basic Auth.
- Automatically sign out after three minutes of frontend inactivity.
- Restore document state from Pinecone after backend restarts or deployments.
- Visualize upload and question processing with live backend stages, durations,
  vector dimensions, retrieval counts, cache behavior, and citations.
- Inspect the latest ingestion as a document-to-chunks-to-embeddings-to-Pinecone
  flow diagram backed by real chunk ranges and vector samples.
- Follow each question through its query embedding, ranked Pinecone matches,
  prompt composition, Claude cache behavior, and grounded answer citations.
- Provide an unauthenticated `/health` endpoint for platform health checks.

## Project Evolution

### FAISS to Pinecone

The first implementation used a local FAISS index. FAISS was appropriate for
local development, but its files lived on one machine and required a persistent
disk outside the application deployment directory. Application deployments or
instance replacement could otherwise remove the index, and multiple backend
instances could not share the same local state.

The current implementation uses Pinecone serverless:

- Dense vectors remain generated locally with `all-MiniLM-L6-v2`.
- The Pinecone index uses 384 dimensions and cosine similarity.
- Chunk text and citation metadata are stored with each vector.
- A state record stores the active document name, generated document ID, and
  chunk count.
- A configurable namespace isolates this application's records.
- The backend reconstructs the bounded Claude context from Pinecone after a
  restart.
- Clearing a document removes namespace records without deleting the index.
- First-upload handling checks that a namespace exists before trying to clear
  it, preventing a Pinecone `404 Namespace not found` error.

The application currently uses one namespace and one active document. A
multi-user version should assign namespaces by user, tenant, or collection and
enforce that ownership on the server.

### Security and Session Controls

- Basic Auth credentials are required for `/upload`, `/chat`, `/status`, and
  `/clear`.
- `/health` remains public so AWS or another hosting platform can check the
  process without credentials.
- The React app keeps credentials only in browser session storage.
- Keyboard, pointer, touch, and scroll activity reset the inactivity timer.
- After three inactive minutes, the frontend removes credentials, clears local
  chat state, and returns to the sign-in screen.
- Production deployments must use HTTPS because Basic Auth credentials are sent
  with each protected request.

### Reliability and Deployment Changes

- Upload size is configurable with `MAX_UPLOAD_MB`, defaulting to 25 MB.
- CSV files are read directly without pandas, reducing deployment size.
- LangChain and sentence-transformers versions are bounded for compatibility.
- The Pinecone SDK is pinned to the supported 9.x release range.
- Elastic Beanstalk includes a pip no-cache prebuild hook to reduce installation
  disk pressure.
- Pinecone removes the need for a persistent FAISS directory or EFS volume for
  vectors.
- Original uploaded files and chat history are not currently persisted.

Claude Haiku 4.5 requires at least 4,096 cacheable tokens. Shorter document
prompts still work normally, but Anthropic reports zero cache-write and
cache-read tokens. For an eligible document, the first question writes the
default five-minute cache and a follow-up with the same system prefix reads it.
See Anthropic's
[prompt caching documentation](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
for cache thresholds, TTL behavior, pricing, and usage fields.

## Configuration

Create `rag-app/backend/.env` from `.env.example`:

```env
ANTHROPIC_API_KEY=your_anthropic_key
PINECONE_API_KEY=your_pinecone_key
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

The backend can create the Pinecone index on the first upload. When creating it
manually, use:

```text
Vector type: Dense
Dimension: 384
Metric: Cosine
Capacity: Serverless
```

Optional frontend configuration in `rag-app/frontend/.env`:

```env
VITE_API_BASE_URL=/api
VITE_INACTIVITY_TIMEOUT_MS=180000
```

Use `120000` for a two-minute inactivity timeout or `180000` for three minutes.

## Run Locally

Start the backend:

```bash
cd rag-app/backend
cp .env.example .env
# Add real API keys and app credentials to .env.
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Verify the backend:

```bash
curl http://localhost:8000/health
curl -u admin:your-password http://localhost:8000/status
```

Start the frontend in another terminal:

```bash
cd rag-app/frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173` and sign in with the credentials configured in the
backend `.env`.

## API

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | No | Lightweight process health check |
| `GET` | `/status` | Basic Auth | Return active document state |
| `POST` | `/upload` | Basic Auth | Validate, process, embed, and index a document |
| `POST` | `/chat` | Basic Auth | Retrieve context and ask Claude |
| `GET` | `/operations/{id}` | Basic Auth | Read live upload or chat pipeline progress |
| `DELETE` | `/clear` | Basic Auth | Delete records in the configured namespace |

During local development, Vite proxies `/api/*` to
`http://localhost:8000`.

## Verification

Backend:

```bash
cd rag-app/backend
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m py_compile main.py rag_engine.py claude_client.py document_processor.py
pip check
```

Frontend:

```bash
cd rag-app/frontend
npm run build
```

## Production Notes

- Current S3 frontend:
  `http://rag-assistant-vinod.s3-website.us-east-2.amazonaws.com`
- Current backend API:
  `https://d27o32245p2wf.cloudfront.net`
- Store API keys and passwords in AWS Secrets Manager, SSM Parameter Store, or
  protected environment variables.
- Rotate any credential exposed in chat, screenshots, logs, or documentation.
- Put HTTPS in front of the backend before allowing public access.
- Replace Basic Auth with Cognito, Auth0, or organizational SSO for multi-user
  production.
- Use S3 if original uploaded files must persist.
- Use PostgreSQL if users, metadata, sessions, or chat history must persist.
- Use a separate Pinecone namespace per user, tenant, or document collection.

## Documentation

- [Setup](./rag-app/docs/SETUP.md)
- [API Reference](./rag-app/docs/API.md)
- [Deployment](./rag-app/docs/DEPLOYMENT.md)
- [Production Notes](./rag-app/docs/PRODUCTION.md)
- [Complete Project Overview](./rag-app/docs/PROJECT_OVERVIEW.md)
