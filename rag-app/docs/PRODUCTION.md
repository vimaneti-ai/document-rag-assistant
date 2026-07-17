# Production Notes

## Secrets

- Keep `ANTHROPIC_API_KEY` in environment variables or a secret manager.
- Keep `PINECONE_API_KEY` in environment variables or a secret manager.
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

The frontend inactivity timeout is configured at build time:

```env
VITE_INACTIVITY_TIMEOUT_MS=180000
```

This clears credentials stored in the browser session after three inactive
minutes. It is a frontend safeguard, not a replacement for server-issued,
expiring sessions in a multi-user production system.

## CORS

Use explicit frontend origins in `CORS_ORIGINS`. Avoid `*` for production.

Example:

```env
CORS_ORIGINS=https://rag.example.com
```

## Pinecone Persistence

Vectors, chunk text, source metadata, and the active-document state are stored
in the configured Pinecone namespace:

```env
PINECONE_INDEX_NAME=document-rag-assistant
PINECONE_NAMESPACE=adaptive-rag
```

The backend creates a serverless index on first upload when it does not exist.
The index must use 384 dimensions and cosine similarity because the app embeds
text locally with `all-MiniLM-L6-v2`.

For real production, prefer:

- S3 for uploaded source files.
- PostgreSQL for metadata, users, sessions, and chat history.
- A separate Pinecone namespace per user, tenant, or collection.
- Server-side authorization that prevents users from selecting another tenant's namespace.

The current fixed namespace and Basic Auth model are suitable for one trusted
user or a controlled demo. They are not a multi-tenant authorization design.

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

For large document collections, add document IDs, pagination, background
ingestion, and per-user or per-tenant namespaces.

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
