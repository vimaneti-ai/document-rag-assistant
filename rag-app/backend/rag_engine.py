import os
import uuid
from typing import Any, Callable, List, Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec


EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
STATE_RECORD_ID = "_document_state"
RECORD_TYPE_CHUNK = "chunk"
RECORD_TYPE_STATE = "state"
UPSERT_BATCH_SIZE = 100
FETCH_BATCH_SIZE = 100
ProgressCallback = Callable[[str, str, Optional[str]], None]


class RAGEngine:
    def __init__(self) -> None:
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "document-rag-assistant")
        self.namespace = os.getenv("PINECONE_NAMESPACE", "adaptive-rag")
        self.cloud = os.getenv("PINECONE_CLOUD", "aws")
        self.region = os.getenv("PINECONE_REGION", "us-east-1")
        self.max_context_chars = int(os.getenv("MAX_CACHED_CONTEXT_CHARS", "120000"))
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.client: Optional[Pinecone] = None
        self.index: Optional[Any] = None
        self.state: dict = {}
        self._context_cache = ""

    @property
    def document_loaded(self) -> bool:
        self._ensure_state()
        return bool(self.state.get("document_name") and self.state.get("document_id"))

    @property
    def document_name(self) -> Optional[str]:
        return self.state.get("document_name")

    @property
    def total_chunks(self) -> int:
        return int(self.state.get("total_chunks", 0))

    def build_index(
        self,
        chunks: List[Document],
        document_name: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> dict:
        if not chunks:
            raise ValueError("The document did not contain any readable text.")

        texts = [chunk.page_content for chunk in chunks]
        self._progress(on_progress, "embedding", "running", f"Encoding {len(texts)} chunks")
        vectors = self._get_embeddings().embed_documents(texts)
        if not vectors or len(vectors[0]) != EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Embedding model returned an unexpected dimension. Expected {EMBEDDING_DIMENSION}."
            )
        self._progress(
            on_progress,
            "embedding",
            "completed",
            f"{len(vectors)} vectors at {EMBEDDING_DIMENSION} dimensions",
        )

        self._progress(on_progress, "indexing", "running", "Connecting to Pinecone")
        index = self._get_index(create=True)
        document_id = uuid.uuid4().hex
        records = [
            {
                "id": self._chunk_id(document_id, position),
                "values": vector,
                "metadata": self._chunk_metadata(chunk, document_id),
            }
            for position, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]

        if self._namespace_exists(index):
            index.delete(delete_all=True, namespace=self.namespace)
        response = index.upsert(
            vectors=records,
            namespace=self.namespace,
            batch_size=UPSERT_BATCH_SIZE,
            show_progress=False,
        )
        if getattr(response, "has_errors", False):
            raise RuntimeError("Pinecone failed to store one or more document chunks.")

        state = {
            "document_name": document_name,
            "document_id": document_id,
            "total_chunks": len(chunks),
        }
        marker = [0.0] * EMBEDDING_DIMENSION
        marker[0] = 1.0
        index.upsert(
            vectors=[
                {
                    "id": STATE_RECORD_ID,
                    "values": marker,
                    "metadata": {**state, "record_type": RECORD_TYPE_STATE},
                }
            ],
            namespace=self.namespace,
        )

        self.state = state
        self._context_cache = self._format_full_context(chunks)
        self._progress(
            on_progress,
            "indexing",
            "completed",
            f"{len(records)} vectors stored in namespace {self.namespace}",
        )
        return self._ingestion_visualization(chunks, vectors, document_name)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[Document]:
        self._ensure_state()
        document_id = self.state.get("document_id")
        if not document_id:
            raise ValueError("No document has been uploaded yet.")

        self._progress(on_progress, "query_embedding", "running", "Encoding the question")
        query_vector = self._get_embeddings().embed_query(query)
        self._progress(
            on_progress,
            "query_embedding",
            "completed",
            f"Query vector has {len(query_vector)} dimensions",
        )
        self._progress(on_progress, "retrieval", "running", f"Requesting top {k} matches")
        result = self._get_index(create=False).query(
            vector=query_vector,
            top_k=k,
            namespace=self.namespace,
            include_metadata=True,
            filter={
                "$and": [
                    {"record_type": {"$eq": RECORD_TYPE_CHUNK}},
                    {"document_id": {"$eq": document_id}},
                ]
            },
        )
        matches = getattr(result, "matches", None) or []
        self._progress(
            on_progress,
            "retrieval",
            "completed",
            f"{len(matches)} relevant chunks retrieved",
        )
        return [self._document_from_metadata(self._metadata(match)) for match in matches]

    def retrieve_context(
        self,
        query: str,
        k: int = 4,
        on_progress: Optional[ProgressCallback] = None,
    ) -> tuple[str, List[str]]:
        documents = self.similarity_search(query, k=k, on_progress=on_progress)
        context_parts = []
        sources = []
        for rank, doc in enumerate(documents, start=1):
            source = self._source_label(doc)
            context_parts.append(f"[Retrieved chunk {rank}: {source}]\n{doc.page_content}")
            if source not in sources:
                sources.append(source)
        return "\n\n".join(context_parts), sources

    def full_document_context(self) -> str:
        if self._context_cache:
            return self._context_cache

        self._ensure_state()
        document_id = self.state.get("document_id")
        total_chunks = self.total_chunks
        if not document_id or not total_chunks:
            return ""

        index = self._get_index(create=False)
        parts = []
        current_length = 0
        ids = [self._chunk_id(document_id, position) for position in range(total_chunks)]
        for start in range(0, len(ids), FETCH_BATCH_SIZE):
            response = index.fetch(
                ids=ids[start : start + FETCH_BATCH_SIZE],
                namespace=self.namespace,
            )
            fetched = self._vectors(response)
            for vector_id in ids[start : start + FETCH_BATCH_SIZE]:
                record = fetched.get(vector_id)
                if record is None:
                    continue
                document = self._document_from_metadata(self._metadata(record))
                part = f"[{self._source_label(document)}]\n{document.page_content}"
                if current_length + len(part) > self.max_context_chars:
                    self._context_cache = "\n\n".join(parts)
                    return self._context_cache
                parts.append(part)
                current_length += len(part) + 2

        self._context_cache = "\n\n".join(parts)
        return self._context_cache

    def clear(self) -> None:
        index = self._get_index(create=False, required=False)
        if index is not None and self._namespace_exists(index):
            index.delete(delete_all=True, namespace=self.namespace)
        self.state = {}
        self._context_cache = ""

    def status(self) -> dict:
        self._refresh_state()
        return {
            "document_loaded": bool(
                self.state.get("document_name") and self.state.get("document_id")
            ),
            "document_name": self.document_name,
            "total_chunks": self.total_chunks,
        }

    def _get_client(self) -> Pinecone:
        if self.client is not None:
            return self.client
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY is not set in backend/.env")
        self.client = Pinecone(api_key=api_key)
        return self.client

    def _get_index(self, create: bool, required: bool = True):
        if self.index is not None:
            return self.index

        client = self._get_client()
        exists = client.indexes.exists(self.index_name)
        if not exists:
            if not create:
                if required:
                    raise RuntimeError(
                        f"Pinecone index '{self.index_name}' does not exist. Upload a document first."
                    )
                return None
            client.indexes.create(
                name=self.index_name,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud=self.cloud, region=self.region),
            )

        description = client.indexes.describe(self.index_name)
        if int(description.dimension) != EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Pinecone index '{self.index_name}' has dimension {description.dimension}; "
                f"{EMBEDDING_DIMENSION} is required for {EMBEDDING_MODEL}."
            )
        metric = getattr(description.metric, "value", description.metric)
        if str(metric).lower() != "cosine":
            raise RuntimeError(
                f"Pinecone index '{self.index_name}' must use the cosine metric."
            )

        self.index = client.index(name=self.index_name)
        return self.index

    def _ensure_state(self) -> None:
        if not self.state:
            self._refresh_state()

    def _namespace_exists(self, index: Any) -> bool:
        response = index.describe_index_stats()
        if isinstance(response, dict):
            namespaces = response.get("namespaces") or {}
        else:
            namespaces = getattr(response, "namespaces", None) or {}
        return self.namespace in namespaces

    def _refresh_state(self) -> None:
        index = self._get_index(create=False, required=False)
        if index is None:
            self.state = {}
            return
        response = index.fetch(ids=[STATE_RECORD_ID], namespace=self.namespace)
        marker = self._vectors(response).get(STATE_RECORD_ID)
        metadata = self._metadata(marker) if marker is not None else {}
        if metadata.get("record_type") != RECORD_TYPE_STATE:
            self.state = {}
            return
        self.state = {
            "document_name": metadata.get("document_name"),
            "document_id": metadata.get("document_id"),
            "total_chunks": int(metadata.get("total_chunks", 0)),
        }

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self.embeddings

    def _chunk_metadata(self, chunk: Document, document_id: str) -> dict:
        metadata = {
            "record_type": RECORD_TYPE_CHUNK,
            "document_id": document_id,
            "text": chunk.page_content,
            "source": str(chunk.metadata.get("source", "Uploaded document")),
        }
        page = chunk.metadata.get("page")
        chunk_index = chunk.metadata.get("chunk_index")
        char_start = chunk.metadata.get("char_start")
        char_end = chunk.metadata.get("char_end")
        if isinstance(page, int):
            metadata["page"] = page
        if isinstance(chunk_index, int):
            metadata["chunk_index"] = chunk_index
        if isinstance(char_start, int):
            metadata["char_start"] = char_start
        if isinstance(char_end, int):
            metadata["char_end"] = char_end
        return metadata

    def _document_from_metadata(self, metadata: dict) -> Document:
        document_metadata = {"source": metadata.get("source", "Uploaded document")}
        for key in ("page", "chunk_index", "char_start", "char_end"):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                document_metadata[key] = int(value)
        return Document(
            page_content=str(metadata.get("text", "")),
            metadata=document_metadata,
        )

    def _format_full_context(self, chunks: List[Document]) -> str:
        parts = []
        current_length = 0
        for chunk in chunks:
            part = f"[{self._source_label(chunk)}]\n{chunk.page_content}"
            if current_length + len(part) > self.max_context_chars:
                break
            parts.append(part)
            current_length += len(part) + 2
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

    def _chunk_id(self, document_id: str, position: int) -> str:
        return f"{document_id}:chunk:{position:06d}"

    def _ingestion_visualization(
        self,
        chunks: List[Document],
        vectors: List[List[float]],
        document_name: str,
    ) -> dict:
        recorded_ends = [int(chunk.metadata.get("char_end", 0)) for chunk in chunks]
        character_count = max(recorded_ends, default=0)
        if character_count == 0:
            character_count = sum(len(chunk.page_content) for chunk in chunks)
        previews = []
        previous_end = 0
        for position, (chunk, vector) in enumerate(zip(chunks[:3], vectors[:3])):
            start = int(chunk.metadata.get("char_start", 0))
            end = int(chunk.metadata.get("char_end", start + len(chunk.page_content)))
            previews.append(
                {
                    "index": position + 1,
                    "start": start,
                    "end": end,
                    "characters": len(chunk.page_content),
                    "overlap_with_previous": max(0, previous_end - start),
                    "embedding_preview": [round(float(value), 3) for value in vector[:3]],
                }
            )
            previous_end = end

        return {
            "document_name": document_name,
            "character_count": character_count,
            "estimated_tokens": round(character_count / 4),
            "total_chunks": len(chunks),
            "embedding_dimension": EMBEDDING_DIMENSION,
            "index_name": self.index_name,
            "namespace": self.namespace,
            "chunks": previews,
        }

    def _progress(
        self,
        callback: Optional[ProgressCallback],
        step_id: str,
        state: str,
        detail: Optional[str],
    ) -> None:
        if callback is not None:
            callback(step_id, state, detail)

    def _metadata(self, record: Any) -> dict:
        if isinstance(record, dict):
            return dict(record.get("metadata") or {})
        return dict(getattr(record, "metadata", None) or {})

    def _vectors(self, response: Any) -> dict:
        if isinstance(response, dict):
            return dict(response.get("vectors") or {})
        return dict(getattr(response, "vectors", None) or {})
