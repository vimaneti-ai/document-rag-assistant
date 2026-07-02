# API

Base URL during local development: `http://localhost:8000`

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

Form field:

- `file`: uploaded document

Response:

```json
{
  "filename": "example.pdf",
  "chunks": 42,
  "summary": "Document processed and indexed."
}
```

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

Deletes the local FAISS index and resets backend document state.

Response:

```json
{
  "success": true
}
```
