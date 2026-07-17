# API

Base URL during local development: `http://localhost:8000`

All application endpoints except `GET /health` require HTTP Basic
authentication. Use the credentials configured in backend environment
variables:

```env
APP_BASIC_AUTH_USERNAME=admin
APP_BASIC_AUTH_PASSWORD=use-a-long-random-password
```

Example:

```bash
curl -u admin:use-a-long-random-password http://localhost:8000/status
```

## `GET /health`

Returns a lightweight process health check without contacting Anthropic or
Pinecone. This endpoint does not require authentication and is suitable for a
load balancer or hosting-platform health check.

Response:

```json
{
  "status": "ok"
}
```

## `GET /status`

Returns the current document/index state.

Response:

```json
{
  "document_loaded": true,
  "document_name": "example.pdf",
  "total_chunks": 42
}
```

## `POST /upload`

Uploads, chunks, embeds, and indexes one document.

Supported file types:

- PDF
- TXT
- DOCX
- CSV
- MD

The backend rejects unsupported extensions and files larger than `MAX_UPLOAD_MB`. The default limit is `25` MB.

Form field:

- `file`: uploaded document

Example:

```bash
curl -u admin:use-a-long-random-password \
  -F "file=@example.pdf" \
  http://localhost:8000/upload
```

Response:

```json
{
  "filename": "example.pdf",
  "chunks": 42,
  "summary": "Document processed and indexed."
}
```

Possible upload errors:

- `Unsupported file type. Supported types: .csv, .docx, .md, .pdf, .txt`
- `Uploaded file is too large. Maximum size is 25 MB.`
- `Uploaded file is empty.`

## `POST /chat`

Retrieves relevant chunks and asks Claude to answer from the uploaded document.

Request:

```json
{
  "question": "What are the main findings?",
  "conversation_history": [
    {
      "role": "user",
      "content": "Summarize the document"
    },
    {
      "role": "assistant",
      "content": "The document discusses..."
    }
  ]
}
```

Example:

```bash
curl -u admin:use-a-long-random-password \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the main findings?","conversation_history":[]}' \
  http://localhost:8000/chat
```

Response:

```json
{
  "answer": "The main findings are...",
  "sources": ["example.pdf - page 3 - chunk 8"],
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 180,
    "cache_read_tokens": 8000,
    "cache_write_tokens": 0,
    "cost_usd": 0.003,
    "cache_hit": true
  }
}
```

## `DELETE /clear`

Deletes all vectors in the configured Pinecone namespace and resets backend
document state. It does not delete the Pinecone index itself.

Response:

```json
{
  "success": true
}
```
