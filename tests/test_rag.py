"""Offline tests for how retrieved handbook chunks are shown to the LLM (src/rag.py).

format_docs() does not call OpenAI, so these tests need no API key.
"""

from langchain_core.documents import Document

from src.rag import format_docs


def test_chunk_is_tagged_with_the_printed_page_number():
    # PyPDFLoader pages are 0-indexed; the handbook footer is 1-indexed.
    docs = [Document(page_content="EL accrues 1.5 days", metadata={"page": 17})]
    assert format_docs(docs) == "[Page 18]\nEL accrues 1.5 days"


def test_multiple_chunks_are_each_tagged_and_separated():
    docs = [
        Document(page_content="A", metadata={"page": 0}),
        Document(page_content="B", metadata={"page": 1}),
    ]
    assert format_docs(docs) == "[Page 1]\nA\n\n[Page 2]\nB"


def test_chunk_without_page_metadata_does_not_crash():
    docs = [Document(page_content="A", metadata={})]
    assert format_docs(docs) == "A"


def test_no_documents_gives_empty_string():
    assert format_docs([]) == ""