import os
import secrets
from typing import List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import status as http_status
from pydantic import BaseModel, Field

from claude_client import ClaudeClient
from document_processor import SUPPORTED_EXTENSIONS, load_document, split_documents
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


@app.post("/upload")
async def upload(file: UploadFile = File(...), _: str = Depends(require_auth)):
    try:
        filename = file.filename or "uploaded-document"
        if not any(filename.lower().endswith(extension) for extension in SUPPORTED_EXTENSIONS):
            raise ValueError(f"Unsupported file type. Supported types: {SUPPORTED_FILE_TYPES}")

        file_bytes = await file.read()
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError(f"Uploaded file is too large. Maximum size is {MAX_UPLOAD_MB} MB.")

        documents = load_document(file_bytes, filename)
        chunks = split_documents(documents)
        rag_engine.build_index(chunks, filename)
        summary = "Document processed and indexed."
        try:
            summary = claude.summarize_document(
                rag_engine.full_document_context(),
                rag_engine.document_name or "uploaded-document",
            )
        except Exception as exc:
            summary = f"Document processed and indexed. Summary unavailable: {exc}"
        return {
            "filename": rag_engine.document_name,
            "chunks": rag_engine.total_chunks,
            "summary": summary,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc


@app.post("/chat")
async def chat(request: ChatRequest, _: str = Depends(require_auth)):
    if not rag_engine.document_loaded:
        raise HTTPException(status_code=400, detail="Upload a document before chatting.")

    try:
        retrieved_context, sources = rag_engine.retrieve_context(request.question, k=4)
        answer, usage = claude.ask(
            question=request.question,
            document_context=rag_engine.full_document_context(),
            document_name=rag_engine.document_name or "uploaded-document",
            retrieved_context=retrieved_context,
            conversation_history=[message.model_dump() for message in request.conversation_history],
        )
        return {"answer": answer, "sources": sources, "usage": usage.to_dict()}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc


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
