# Production Notes

## Secrets

- Keep `ANTHROPIC_API_KEY` in environment variables or a secret manager.
- Keep `APP_BASIC_AUTH_PASSWORD` in environment variables or a secret manager.
- Do not commit `.env` files.
- `.env.example` files are safe templates and should not contain real keys.

## Authentication

The backend requires HTTP Basic authentication on every API endpoint. This protects your Claude API credits from anonymous public use.

Required variables:

```env
APP_BASIC_AUTH_USERNAME=admin
APP_BASIC_AUTH_PASSWORD=use-a-long-random-password
```

Use a long random password and serve the app only over HTTPS when public.

For team or customer-facing production use, replace Basic Auth with a proper identity provider such as Cognito, Auth0, or your organization's SSO.

## CORS

Use explicit frontend origins in `CORS_ORIGINS`. Avoid `*` for production.

Example:

```env
CORS_ORIGINS=https://rag.example.com
```

## FAISS Persistence

For demos, the app stores local index state in:

```text
rag-app/backend/faiss_index/
```

This directory is ignored by git. Persist it with a volume if deployed to a platform with ephemeral disks.

For real production, prefer:

- S3 for uploaded source files.
- PostgreSQL for metadata, users, sessions, and chat history.
- EFS for local FAISS persistence, or pgvector/Qdrant for vector storage.
- Per-user or per-tenant isolation for documents and indexes.

Local FAISS is fine for a single-user demo, but it is not enough for a public multi-user app by itself.

## Deserialization Safety

LangChain FAISS persistence uses pickle-backed metadata. Only load indexes created by this app in a trusted environment. Do not accept arbitrary FAISS index folders from users.

## Document Size

Uploads are restricted to supported extensions only:

```text
.pdf, .docx, .txt, .md, .csv
```

`MAX_UPLOAD_MB` controls upload size. Use `10` to `25` MB for public demos:

```env
MAX_UPLOAD_MB=25
```

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
curl -u admin:use-a-long-random-password https://your-api-domain.com/status
```
