# Document RAG Assistant Overview

Built by Vinod Kumar Maneti. Last updated: July 16, 2026.

## Purpose

Document RAG Assistant is a full-stack Retrieval-Augmented Generation application. Users upload a document, the backend generates local embeddings and stores them in Pinecone, and Claude answers questions using retrieved document context plus conversation history.

This is not a Streamlit app. It has a separate FastAPI backend and React + TypeScript frontend.

## Capabilities

- Upload one active document at a time.
- Supported file types: PDF, DOCX, TXT, MD, CSV.
- Split documents into overlapping chunks.
- Generate local embeddings with `sentence-transformers` using `all-MiniLM-L6-v2`.
- Store vectors and chunk metadata in Pinecone.
- Retrieve the top 4 relevant chunks for each question.
- Ask Claude using document context, retrieved chunks, and chat history.
- Use Claude prompt caching for repeated document-context questions.
- Show token usage, cache hit/miss, and estimated cost in the UI.
- Show live, timed processing stages for document uploads and questions.
- Protect all backend API routes with HTTP Basic authentication.
- Enforce upload extension checks and a configurable file-size limit.

## Current Architecture

```text
Browser
  |
  | React + TypeScript frontend
  v
FastAPI backend
  |
  | document parsing and chunking
  v
sentence-transformers embeddings
  |
  v
Pinecone serverless vector index
  |
  | retrieved chunks + cached document context
  v
Anthropic Claude API
```

## Backend

The backend lives in `rag-app/backend`.

Important files:

- `main.py`: FastAPI app, CORS, Basic Auth, upload/chat/status/clear routes.
- `document_processor.py`: PDF, DOCX, TXT, MD, and CSV loading plus text splitting.
- `rag_engine.py`: embeddings, Pinecone index creation, namespace state, retrieval, and clear logic.
- `claude_client.py`: Anthropic API calls, prompt caching, usage parsing, and cost calculation.
- `requirements.txt`: Python dependencies.
- `.platform/hooks/prebuild/`: Elastic Beanstalk hook that disables pip's download cache.

Backend endpoints:

- `GET /status`
- `GET /operations/{operation_id}`
- `POST /upload`
- `POST /chat`
- `DELETE /clear`
- `GET /health`

All endpoints except the lightweight `GET /health` process check require HTTP
Basic Auth.

## Frontend

The frontend lives in `rag-app/frontend`.

Important files:

- `src/App.tsx`: top-level app state, login screen, layout, document upload, chat flow.
- `src/api/client.ts`: Axios client and API types.
- `src/components/`: chat, upload, sidebar, and cost UI components.
- `package.json`: React/Vite/Tailwind dependencies and scripts.

The frontend stores Basic Auth credentials in session storage for the active
browser session and sends them to the backend with each API request. Keyboard,
pointer, touch, and scroll activity reset a configurable inactivity timer.
After three inactive minutes by default, the frontend clears the credentials
and returns to the sign-in screen.

## Document Flow

```text
1. User uploads PDF, DOCX, TXT, MD, or CSV.
2. Frontend sends multipart form data to POST /upload.
3. Backend validates extension, size, and non-empty content.
4. Document processor extracts text.
5. RecursiveCharacterTextSplitter creates chunks.
6. RAG engine embeds each chunk locally.
7. Pinecone stores vectors, chunk text, source metadata, and active-document state.
8. The backend keeps a bounded document-context cache and can reconstruct it from Pinecone after restart.
9. Claude attempts to summarize the uploaded document.
10. Frontend receives filename, chunk count, summary, and the completed trace.
11. While the request runs, the UI shows validation, extraction, chunking,
    embedding, Pinecone indexing, and summary progress.
12. After indexing, a document-flow diagram displays actual source character
    ranges, neighboring overlap, sample embedding values, and the Pinecone
    index and namespace.
13. The latest document map remains visible while questions run. It is removed
    only when the document is cleared or replaced, or the authenticated browser
    session ends.
```

## Chat Flow

```text
1. User asks a question.
2. Frontend sends POST /chat with question and conversation history.
3. Backend checks that a document is loaded.
4. RAG engine searches the active Pinecone namespace for the top 4 relevant chunks.
5. Claude receives the question, retrieved chunks, cached document context, and history.
6. Backend returns answer, source labels, token usage, cache tokens, and estimated cost.
7. Frontend displays the answer, source citations, cost, and cache hit/miss.
8. The execution trace shows query embedding, retrieval, prompt assembly,
   Claude generation, prompt-cache behavior, and citation attachment.
9. A question-flow diagram shows the real query vector sample, ranked Pinecone
   similarity scores, retrieved excerpts, prompt composition, Claude/cache
   usage, and grounded answer output. The diagram is attached directly below
   its assistant answer so each conversation turn keeps its own trace.
```

## Environment Variables

Backend:

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

For Elastic Beanstalk, also use:

```env
PIP_NO_CACHE_DIR=true
```

Frontend:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_INACTIVITY_TIMEOUT_MS=180000
```

## Persistence

Pinecone persists vectors independently of the local backend filesystem. Each
chunk record contains its text, source, page/chunk metadata, and a generated
document ID. A state record in the same namespace stores the active document
name, document ID, and chunk count.

After a backend restart or deploy, `GET /status` reloads the state record and
the backend can reconstruct the bounded Claude prompt context from chunk
records. `DELETE /clear` removes the namespace records but leaves the reusable
Pinecone index in place.

The current app uses one configured namespace and therefore supports one active
document. Add per-user or per-tenant namespaces before multi-user production.
Use S3 for original documents and PostgreSQL for users, metadata, and chat
history when those records also need durable storage.

## Deployment Options

Current AWS path:

```text
Backend: Elastic Beanstalk Python 3.11
Frontend: Amplify or static hosting
```

Elastic Beanstalk notes:

- Use `backend/Procfile` to run Uvicorn.
- Use `gp3` storage with enough disk for `torch` and related ML packages.
- Use `t3.medium` or larger if dependency install or embedding model memory is tight.
- Use `PIP_NO_CACHE_DIR=true` and the included prebuild hook to reduce pip disk pressure.
- Add the Pinecone API key, index, namespace, cloud, and region variables.
- Single-instance EB is HTTP by default; put HTTPS in front before public use.

Recommended production direction:

```text
Frontend: AWS Amplify or S3 + CloudFront
Backend: ECS Fargate + ECR container image
TLS: ALB + ACM or CloudFront + ACM
Secrets: AWS Secrets Manager or platform environment variables
```

ECS Fargate is more reliable for this app than EB because the heavy Python/ML dependency stack is baked into a Docker image instead of installed during every deploy.

## Security Notes

- Do not commit `.env` files.
- Rotate any API key or password that is pasted into chat, screenshots, logs, or documentation.
- Do not expose Basic Auth over plain HTTP on a public network.
- For public use, put CloudFront or an ALB with ACM HTTPS in front of the backend.
- Replace Basic Auth with Cognito/Auth0/SSO for real multi-user production.
- Keep `CORS_ORIGINS` explicit.

## Known Limits

- One active document/index at a time.
- The fixed Pinecone namespace is not multi-tenant.
- Original uploaded files and chat history are not persisted.
- Large files and large dependency installs require more disk and memory than a tiny EC2 instance provides.
- Prompt caching reduces repeated document-context cost, but the first request after upload can be slower and more expensive.

## Verification

Backend:

```bash
cd rag-app/backend
source .venv/bin/activate
python -m py_compile main.py rag_engine.py claude_client.py document_processor.py
curl -u admin:your-password http://localhost:8000/status
```

Frontend:

```bash
cd rag-app/frontend
npm run build
```
