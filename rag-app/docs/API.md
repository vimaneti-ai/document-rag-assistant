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

The frontend can include an operation UUID and read live stage progress while
the request runs. The final response includes the completed pipeline trace.

Supported file types:

- PDF
- TXT
- DOCX
- CSV
- MD

The backend rejects unsupported extensions and files larger than `MAX_UPLOAD_MB`. The default limit is `25` MB.

Form field:

- `file`: uploaded document
- `operation_id`: optional UUID used for progress tracking

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
  "summary": "Document processed and indexed.",
  "pipeline": {
    "operation_id": "37d1de9d-cf15-45cb-b76a-5ccf4957809b",
    "kind": "upload",
    "status": "completed",
    "elapsed_ms": 2840,
    "steps": []
  },
  "visualization": {
    "document_name": "example.pdf",
    "character_count": 14360,
    "estimated_tokens": 3590,
    "total_chunks": 18,
    "embedding_dimension": 384,
    "index_name": "document-rag-assistant",
    "namespace": "adaptive-rag",
    "chunks": [
      {
        "index": 1,
        "start": 0,
        "end": 996,
        "characters": 996,
        "overlap_with_previous": 0,
        "embedding_preview": [0.12, -0.08, 0.03]
      }
    ]
  }
}
```

The visualization contains up to three real chunk examples. Character ranges
come from the extracted source text, and embedding previews contain the first
three values of the actual 384-dimensional vectors sent to Pinecone.
`estimated_tokens` is approximate and appears with `~` in the interface.

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
  ],
  "operation_id": "37d1de9d-cf15-45cb-b76a-5ccf4957809b"
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
  },
  "pipeline": {
    "operation_id": "37d1de9d-cf15-45cb-b76a-5ccf4957809b",
    "kind": "chat",
    "status": "completed",
    "elapsed_ms": 1530,
    "steps": []
  },
  "visualization": {
    "question": "What are the main findings?",
    "query_embedding_preview": [0.14, -0.23, 0.08],
    "embedding_dimension": 384,
    "matches": [
      {
        "rank": 1,
        "source": "example.pdf - page 3 - chunk 8",
        "score": 0.8241,
        "characters": 944,
        "excerpt": "The report identifies..."
      }
    ],
    "retrieved_context_characters": 3820,
    "document_context_characters": 42180,
    "history_messages": 2,
    "model": "claude-haiku-4-5",
    "answer_characters": 612,
    "source_count": 4,
    "cache_status": "hit",
    "input_tokens": 1200,
    "output_tokens": 180,
    "cache_read_tokens": 8000,
    "cache_write_tokens": 0
  }
}
```

The question visualization contains the real query-vector preview, Pinecone
match scores and excerpts, prompt composition, cache event, Claude token usage,
and answer/citation counts. The UI uses these values to render the complete
question-to-answer flow.

## `GET /operations/{operation_id}`

Returns live progress for an upload or chat request. Authentication is
required. Each step includes its state, detail, and elapsed milliseconds.

```json
{
  "operation_id": "37d1de9d-cf15-45cb-b76a-5ccf4957809b",
  "kind": "chat",
  "status": "running",
  "elapsed_ms": 842,
  "steps": [
    {
      "id": "query_embedding",
      "label": "Embed question",
      "status": "completed",
      "detail": "Query vector has 384 dimensions",
      "duration_ms": 74
    },
    {
      "id": "retrieval",
      "label": "Search Pinecone",
      "status": "running",
      "detail": "Requesting top 4 matches",
      "duration_ms": 31
    }
  ]
}
```

Operation state remains in backend memory for one hour. It supports temporary
UI progress and is not persistent audit history.

## `DELETE /clear`

Deletes all vectors in the configured Pinecone namespace and resets backend
document state. It does not delete the Pinecone index itself.

Response:

```json
{
  "success": true
}
```
