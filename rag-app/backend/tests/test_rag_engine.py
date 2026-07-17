import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from rag_engine import EMBEDDING_DIMENSION, RAGEngine


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[1.0] + [0.0] * (EMBEDDING_DIMENSION - 1) for _ in texts]

    def embed_query(self, _query):
        return [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)


class FakeIndex:
    def __init__(self):
        self.records = {}

    def delete(self, *, delete_all=False, namespace="", **_kwargs):
        if delete_all:
            if namespace not in self.records:
                raise RuntimeError("404 Namespace not found")
            self.records[namespace] = {}

    def describe_index_stats(self):
        return SimpleNamespace(
            namespaces={
                namespace: SimpleNamespace(vector_count=len(records))
                for namespace, records in self.records.items()
                if records
            }
        )

    def upsert(self, *, vectors, namespace="", **_kwargs):
        namespace_records = self.records.setdefault(namespace, {})
        for vector in vectors:
            namespace_records[vector["id"]] = SimpleNamespace(
                metadata=vector.get("metadata", {})
            )
        return SimpleNamespace(has_errors=False)

    def query(self, *, top_k, namespace="", filter=None, **_kwargs):
        records = self.records.get(namespace, {}).values()
        document_id = filter["$and"][1]["document_id"]["$eq"]
        matches = [
            record
            for record in records
            if record.metadata.get("record_type") == "chunk"
            and record.metadata.get("document_id") == document_id
        ]
        return SimpleNamespace(matches=matches[:top_k])

    def fetch(self, *, ids, namespace="", **_kwargs):
        records = self.records.get(namespace, {})
        return SimpleNamespace(
            vectors={record_id: records[record_id] for record_id in ids if record_id in records}
        )


class RAGEngineTests(unittest.TestCase):
    def setUp(self):
        self.index = FakeIndex()
        self.engine = RAGEngine()
        self.engine.embeddings = FakeEmbeddings()
        self.engine.index = self.index

    def test_build_retrieve_reload_and_clear(self):
        chunks = [
            Document(
                page_content="Revenue increased by 12 percent.",
                metadata={"source": "report.pdf", "page": 1, "chunk_index": 0},
            ),
            Document(
                page_content="Operating margin reached 18 percent.",
                metadata={"source": "report.pdf", "page": 2, "chunk_index": 1},
            ),
        ]

        self.engine.build_index(chunks, "report.pdf")

        self.assertEqual(
            self.engine.status(),
            {
                "document_loaded": True,
                "document_name": "report.pdf",
                "total_chunks": 2,
            },
        )
        context, sources = self.engine.retrieve_context("What was the margin?", k=1)
        self.assertIn("Revenue increased", context)
        self.assertEqual(sources, ["report.pdf - page 2 - chunk 1"])

        restarted = RAGEngine()
        restarted.embeddings = FakeEmbeddings()
        restarted.index = self.index
        self.assertTrue(restarted.document_loaded)
        self.assertIn("Operating margin", restarted.full_document_context())

        restarted.clear()
        self.assertEqual(restarted.status()["document_loaded"], False)

    def test_missing_api_key_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            engine = RAGEngine()
            with self.assertRaisesRegex(RuntimeError, "PINECONE_API_KEY"):
                engine.status()


if __name__ == "__main__":
    unittest.main()
