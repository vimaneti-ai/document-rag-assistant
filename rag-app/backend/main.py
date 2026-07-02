import os
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from claude_client import ClaudeClient
from document_processor import load_document, split_documents
from rag_engine import RAGEngine


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


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_history: List[HistoryMessage] = Field(default_factory=list)


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")
        documents = load_document(file_bytes, file.filename or "uploaded-document")
        chunks = split_documents(documents)
        rag_engine.build_index(chunks, file.filename or "uploaded-document")
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
async def chat(request: ChatRequest):
    if not rag_engine.document_loaded:
        raise HTTPException(status_code=400, detail="Upload a document before chatting.")

    try:
        retrieved_context, sources = rag_engine.retrieve_context(request.question, k=4)
        answer, usage = claude.ask(
            question=request.question,
            document_context=rag_engine.full_document_context(),
            document_name=rag_engine.document_name or "uploaded-document",
            retrieved_context=retrieved_context,
            conversation_history=[message.dict() for message in request.conversation_history],
        )
        return {"answer": answer, "sources": sources, "usage": usage.to_dict()}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc


@app.get("/status")
async def status():
    return rag_engine.status()


@app.delete("/clear")
async def clear():
    rag_engine.clear()
    return {"success": True}
