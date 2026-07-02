# Production Notes

## Secrets

- Keep `ANTHROPIC_API_KEY` in environment variables or a secret manager.
- Do not commit `.env` files.
- `.env.example` files are safe templates and should not contain real keys.

## CORS

Use explicit frontend origins in `CORS_ORIGINS`. Avoid `*` for production.

Example:

```env
CORS_ORIGINS=https://rag.example.com
```

## FAISS Persistence

The app stores local index state in:

```text
rag-app/backend/faiss_index/
```

This directory is ignored by git. Persist it with a volume if deployed to a platform with ephemeral disks.

## Deserialization Safety

LangChain FAISS persistence uses pickle-backed metadata. Only load indexes created by this app in a trusted environment. Do not accept arbitrary FAISS index folders from users.

## Document Size

`MAX_CACHED_CONTEXT_CHARS` bounds the document context included in Claude's cached system prompt. Retrieved chunks are always sent with the user question, so answers still prioritize the most relevant excerpts.

For very large document collections, move from one local FAISS index to a managed vector database and add per-user/session isolation.

## Operational Checks

Before deploying:

```bash
cd rag-app/backend
source .venv/bin/activate
python -m py_compile main.py rag_engine.py claude_client.py document_processor.py
```

```bash
cd rag-app/frontend
npm run build
```

Smoke test:

```bash
curl https://your-api-domain.com/status
```
