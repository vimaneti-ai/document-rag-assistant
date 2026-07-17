import unittest

from langchain_core.documents import Document

from document_processor import split_documents


class DocumentProcessorTests(unittest.TestCase):
    def test_split_documents_records_real_character_ranges_and_overlap(self):
        content = " ".join(f"word-{index:03d}" for index in range(180))
        chunks = split_documents(
            [Document(page_content=content, metadata={"source": "sample.txt"})],
            chunk_size=300,
            chunk_overlap=60,
        )

        self.assertGreater(len(chunks), 2)
        first = chunks[0]
        second = chunks[1]
        self.assertEqual(first.metadata["char_start"], 0)
        self.assertEqual(
            first.metadata["char_end"],
            first.metadata["char_start"] + len(first.page_content),
        )
        self.assertLess(second.metadata["char_start"], first.metadata["char_end"])
        self.assertEqual(
            content[second.metadata["char_start"] : second.metadata["char_end"]],
            second.page_content,
        )


if __name__ == "__main__":
    unittest.main()
