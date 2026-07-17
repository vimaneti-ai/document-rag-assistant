import os
import secrets
from typing import List
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import status as http_status
from pydantic import BaseModel, Field

from claude_client import ClaudeClient
from document_processor import SUPPORTED_EXTENSIONS, load_document, split_documents
from pipeline_progress import OperationTracker
from rag_engine import RAGEngine

load_dotenv()

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
SUPPORTED_FILE_TYPES = ", ".join(sorted(SUPPORTED_EXTENSIONS))


app = FastAPI(title="Adaptive RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_engine = RAGEngine()
claude = ClaudeClient()
security = HTTPBasic()
operations = OperationTracker()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_username = os.getenv("APP_BASIC_AUTH_USERNAME", "")
    expected_password = os.getenv("APP_BASIC_AUTH_PASSWORD", "")
    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Basic authentication is not configured.",
        )

    valid_username = secrets.compare_digest(credentials.username, expected_username)
    valid_password = secrets.compare_digest(credentials.password, expected_password)
    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_history: List[HistoryMessage] = Field(default_factory=list)
    operation_id: str | None = None


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    operation_id: str | None = Form(default=None),
    _: str = Depends(require_auth),
):
    current_operation_id = _operation_id(operation_id)
    operations.start(current_operation_id, "upload")
    try:
        operations.begin_step(current_operation_id, "validation", "Reading uploaded file")
        filename = file.filename or "uploaded-document"
        if not any(filename.lower().endswith(extension) for extension in SUPPORTED_EXTENSIONS):
            raise ValueError(f"Unsupported file type. Supported types: {SUPPORTED_FILE_TYPES}")

        file_bytes = await file.read()
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError(f"Uploaded file is too large. Maximum size is {MAX_UPLOAD_MB} MB.")
        operations.finish_step(
            current_operation_id,
            "validation",
            f"{filename} ({_format_bytes(len(file_bytes))}) accepted",
        )

        operations.begin_step(current_operation_id, "parsing", "Extracting readable content")
        documents = await run_in_threadpool(load_document, file_bytes, filename)
        operations.finish_step(
            current_operation_id,
            "parsing",
            f"{len(documents)} document section{'s' if len(documents) != 1 else ''} extracted",
        )

        operations.begin_step(current_operation_id, "chunking", "Splitting with overlap")
        chunks = await run_in_threadpool(split_documents, documents)
        operations.finish_step(
            current_operation_id,
            "chunking",
            f"{len(chunks)} chunks created (1,000 characters, 150 overlap)",
        )

        visualization = await run_in_threadpool(
            rag_engine.build_index,
            chunks,
            filename,
            _progress_callback(current_operation_id),
        )
        summary = "Document processed and indexed."
        operations.begin_step(current_operation_id, "summary", "Asking Claude for a summary")
        try:
            document_context = await run_in_threadpool(rag_engine.full_document_context)
            summary = await run_in_threadpool(
                claude.summarize_document,
                document_context,
                rag_engine.document_name or "uploaded-document",
            )
            operations.finish_step(current_operation_id, "summary", "Summary ready")
        except Exception as exc:
            summary = f"Document processed and indexed. Summary unavailable: {exc}"
            operations.finish_step(current_operation_id, "summary", "Indexed; summary unavailable")
        pipeline = operations.complete(current_operation_id)
        return {
            "filename": rag_engine.document_name,
            "chunks": rag_engine.total_chunks,
            "summary": summary,
            "pipeline": pipeline,
            "visualization": visualization,
        }
    except ValueError as exc:
        operations.fail(current_operation_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        operations.fail(current_operation_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc


@app.post("/chat")
async def chat(request: ChatRequest, _: str = Depends(require_auth)):
    if not rag_engine.document_loaded:
        raise HTTPException(status_code=400, detail="Upload a document before chatting.")

    current_operation_id = _operation_id(request.operation_id)
    operations.start(current_operation_id, "chat")
    try:
        retrieved_context, sources, visualization = await run_in_threadpool(
            rag_engine.retrieve_context_with_trace,
            request.question,
            4,
            _progress_callback(current_operation_id),
        )
        operations.begin_step(current_operation_id, "prompt", "Combining context and history")
        document_context = await run_in_threadpool(rag_engine.full_document_context)
        history = [message.model_dump() for message in request.conversation_history]
        operations.finish_step(
            current_operation_id,
            "prompt",
            f"{len(retrieved_context):,} retrieved characters; {len(history)} history messages",
        )

        operations.begin_step(current_operation_id, "generation", "Waiting for Claude Haiku 4.5")
        answer, usage = await run_in_threadpool(
            claude.ask,
            request.question,
            document_context,
            rag_engine.document_name or "uploaded-document",
            retrieved_context,
            history,
        )
        cache_detail = (
            f"Cache hit: {usage.cache_read_tokens:,} tokens reused"
            if usage.cache_hit
            else (
                f"Cache created: {usage.cache_write_tokens:,} tokens"
                if usage.cache_write_tokens
                else "Response generated without a cache event"
            )
        )
        operations.finish_step(current_operation_id, "generation", cache_detail)
        operations.begin_step(current_operation_id, "citations", "Linking retrieved sources")
        operations.finish_step(
            current_operation_id,
            "citations",
            f"{len(sources)} source citation{'s' if len(sources) != 1 else ''} attached",
        )
        pipeline = operations.complete(current_operation_id)
        visualization.update(
            {
                "question": request.question,
                "retrieved_context_characters": len(retrieved_context),
                "document_context_characters": len(document_context),
                "history_messages": len(history),
                "model": "claude-haiku-4-5",
                "answer_characters": len(answer),
                "source_count": len(sources),
                "cache_status": (
                    "hit"
                    if usage.cache_hit
                    else "write"
                    if usage.cache_write_tokens
                    else "none"
                ),
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": usage.cache_read_tokens,
                "cache_write_tokens": usage.cache_write_tokens,
            }
        )
        return {
            "answer": answer,
            "sources": sources,
            "usage": usage.to_dict(),
            "pipeline": pipeline,
            "visualization": visualization,
        }
    except RuntimeError as exc:
        operations.fail(current_operation_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        operations.fail(current_operation_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc


@app.get("/operations/{operation_id}")
async def operation_status(operation_id: str, _: str = Depends(require_auth)):
    _operation_id(operation_id)
    operation = operations.get(operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found.")
    return JSONResponse(operation, headers={"Cache-Control": "no-store"})


@app.get("/status")
async def status(_: str = Depends(require_auth)):
    try:
        return rag_engine.status()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.delete("/clear")
async def clear(_: str = Depends(require_auth)):
    try:
        rag_engine.clear()
        return {"success": True}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health")
async def health():
    return {"status": "ok"}


def _operation_id(value: str | None) -> str:
    if not value:
        return str(uuid4())
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid operation ID.") from exc


def _progress_callback(operation_id: str):
    def report(step_id: str, state: str, detail: str | None) -> None:
        if state == "running":
            operations.begin_step(operation_id, step_id, detail)
        elif state == "completed":
            operations.finish_step(operation_id, step_id, detail)

    return report


def _format_bytes(size: int) -> str:
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
