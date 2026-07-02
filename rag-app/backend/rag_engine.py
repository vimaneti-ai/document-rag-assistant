import json
import shutil
from pathlib import Path
from typing import List, Optional

import faiss
from langchain_core.documents import Document
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


INDEX_DIR = Path("faiss_index")
STATE_FILE = INDEX_DIR / "document_state.json"
CONTEXT_FILE = INDEX_DIR / "document_context.txt"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class RAGEngine:
    def __init__(self) -> None:
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.vectorstore: Optional[FAISS] = None
        self.state = self._load_state()

    @property
    def document_loaded(self) -> bool:
        return bool(self.state.get("document_name")) and self._index_files_exist()

    @property
    def document_name(self) -> Optional[str]:
        return self.state.get("document_name")

    @property
    def total_chunks(self) -> int:
        return int(self.state.get("total_chunks", 0))

    def build_index(self, chunks: List[Document], document_name: str) -> None:
        if not chunks:
            raise ValueError("The document did not contain any readable text.")

        INDEX_DIR.mkdir(exist_ok=True)
        texts = [chunk.page_content for chunk in chunks]
        embeddings = self._get_embeddings()
        vectors = embeddings.embed_documents(texts)
        dimension = len(vectors[0])

        index = faiss.IndexFlatIP(dimension)
        index.add(self._as_float32_matrix(vectors))

        docstore = InMemoryDocstore({str(i): chunk for i, chunk in enumerate(chunks)})
        id_map = {i: str(i) for i in range(len(chunks))}
        self.vectorstore = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=docstore,
            index_to_docstore_id=id_map,
        )
        self.vectorstore.save_local(str(INDEX_DIR))

        context = self._format_full_context(chunks)
        CONTEXT_FILE.write_text(context, encoding="utf-8")
        self.state = {"document_name": document_name, "total_chunks": len(chunks)}
        STATE_FILE.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        if self.vectorstore is None and self._index_files_exist():
            self.vectorstore = self._load_index()
        if self.vectorstore is None:
            raise ValueError("No document has been uploaded yet.")
        return self.vectorstore.similarity_search(query, k=k)

    def retrieve_context(self, query: str, k: int = 4) -> tuple[str, List[str]]:
        documents = self.similarity_search(query, k=k)
        context_parts = []
        sources = []
        for rank, doc in enumerate(documents, start=1):
            source = self._source_label(doc)
            context_parts.append(f"[Retrieved chunk {rank}: {source}]\n{doc.page_content}")
            if source not in sources:
                sources.append(source)
        return "\n\n".join(context_parts), sources

    def full_document_context(self) -> str:
        if CONTEXT_FILE.exists():
            return CONTEXT_FILE.read_text(encoding="utf-8")
        return ""

    def clear(self) -> None:
        self.vectorstore = None
        self.state = {}
        if INDEX_DIR.exists():
            shutil.rmtree(INDEX_DIR)

    def status(self) -> dict:
        return {
            "document_loaded": self.document_loaded,
            "document_name": self.document_name,
            "total_chunks": self.total_chunks,
        }

    def _load_index(self) -> Optional[FAISS]:
        if not self._index_files_exist():
            return None
        return FAISS.load_local(
            str(INDEX_DIR),
            self._get_embeddings(),
            allow_dangerous_deserialization=True,
        )

    def _index_files_exist(self) -> bool:
        return (INDEX_DIR / "index.faiss").exists() and (INDEX_DIR / "index.pkl").exists()

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self.embeddings

    def _load_state(self) -> dict:
        if not STATE_FILE.exists():
            return {}
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))

    def _format_full_context(self, chunks: List[Document]) -> str:
        parts = []
        for chunk in chunks:
            label = self._source_label(chunk)
            parts.append(f"[{label}]\n{chunk.page_content}")
        return "\n\n".join(parts)

    def _source_label(self, doc: Document) -> str:
        source = doc.metadata.get("source", "Uploaded document")
        page = doc.metadata.get("page")
        chunk = doc.metadata.get("chunk_index")
        bits = [str(source)]
        if isinstance(page, int):
            bits.append(f"page {page + 1}")
        if isinstance(chunk, int):
            bits.append(f"chunk {chunk + 1}")
        return " - ".join(bits)

    def _as_float32_matrix(self, vectors: List[List[float]]):
        import numpy as np

        return np.array(vectors, dtype="float32")
