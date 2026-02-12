from app.services.spoke_c_rag import RAGEngine, RetrievalEvaluator, Document, RetrievalResult
from typing import List, Dict, Any, Tuple
import pytest

# --- Existing Test ---
def test_chunk_document_basic():
    # This test targets the in-memory RAGService and TextChunker behavior.
    from app.services.spoke_c_rag import RAGService, TextChunker
    
    # Mock chunker for RAGService
    mock_chunker = TextChunker()
    mock_chunker.chunk = lambda text, source: [
        Document(id="1", content=text[:1000], source=source),
        Document(id="2", content=text[900:1900], source=source),
        Document(id="3", content=text[1800:], source=source),
    ] if len(text) > 1000 else [Document(id="1", content=text, source=source)]

    engine = RAGService(chunker=mock_chunker) # Use RAGService for this test
    text = "A" * 2500
    # Chunking is implemented in TextChunker, which RAGService uses internally.
    
    chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
    chunks = chunker.chunk(text, source="test_source")
    assert len(chunks) == 3
    assert chunks[0].content.startswith("A" * 1000)
    assert chunks[1].content.startswith("A" * 900)
    assert chunks[2].content.startswith("A" * 500) # (2500 - 1800) for the last chunk
    assert all("content" in c.metadata or "char_count" in c.metadata for c in chunks) # check if metadata is present

# --- Mock RAGEngine for RetrievalEvaluator Tests ---
class MockRAGEngine:
    async def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        # Simulate retrieval results based on a simple pattern
        if "financial" in query:
            return [
                RetrievalResult(document=Document(id="doc_1", content="financial report"), score=0.9, rank=1),
                RetrievalResult(document=Document(id="doc_3", content="stock analysis"), score=0.7, rank=2),
                RetrievalResult(document=Document(id="doc_5", content="market trends"), score=0.6, rank=3),
            ][:top_k]
        elif "economic" in query:
            return [
                RetrievalResult(document=Document(id="doc_2", content="economic indicators"), score=0.8, rank=1),
                RetrievalResult(document=Document(id="doc_4", content="global economy"), score=0.75, rank=2),
            ][:top_k]
        return []

    def _get_document_ids_from_results(self, results: List[RetrievalResult]) -> List[str]:
        return [res.document.id for res in results]

@pytest.fixture
def mock_rag_engine():
    return MockRAGEngine()

@pytest.fixture
def evaluator(mock_rag_engine):
    return RetrievalEvaluator(rag_engine=mock_rag_engine)

# --- Test Cases for Static Methods ---
def test_calculate_precision_at_k():
    retrieved = ["A", "B", "C", "D"]
    ground_truth = ["A", "C", "E"]
    assert RetrievalEvaluator._calculate_precision_at_k(retrieved, ground_truth, 3) == 2/3
    assert RetrievalEvaluator._calculate_precision_at_k(retrieved, ground_truth, 2) == 1/2
    assert RetrievalEvaluator._calculate_precision_at_k(retrieved, ground_truth, 0) == 0.0
    assert RetrievalEvaluator._calculate_precision_at_k([], ground_truth, 1) == 0.0

def test_calculate_recall_at_k():
    retrieved = ["A", "B", "C", "D"]
    ground_truth = ["A", "C", "E"]
    assert RetrievalEvaluator._calculate_recall_at_k(retrieved, ground_truth, 4) == 2/3
    assert RetrievalEvaluator._calculate_recall_at_k(retrieved, ground_truth, 2) == 1/3
    assert RetrievalEvaluator._calculate_recall_at_k([], ground_truth, 1) == 0.0
    assert RetrievalEvaluator._calculate_recall_at_k(["A"], [], 1) == 1.0 # No relevant docs, if none retrieved, perfect recall

def test_calculate_mrr():
    # Relevant item at rank 1
    assert RetrievalEvaluator._calculate_mrr(["A", "B", "C"], ["A"]) == 1.0
    # Relevant item at rank 2
    assert RetrievalEvaluator._calculate_mrr(["B", "A", "C"], ["A"]) == 0.5
    # Relevant item at rank 3
    assert RetrievalEvaluator._calculate_mrr(["B", "C", "A"], ["A"]) == 1/3
    # No relevant item
    assert RetrievalEvaluator._calculate_mrr(["B", "C"], ["A"]) == 0.0
    # Multiple relevant items, only first one counts for MRR
    assert RetrievalEvaluator._calculate_mrr(["A", "B", "C"], ["A", "C"]) == 1.0

# --- Test Cases for RetrievalEvaluator Methods ---
@pytest.mark.asyncio
async def test_evaluate_query(evaluator, mock_rag_engine):
    query = "financial reports"
    ground_truth = ["doc_1", "doc_3", "doc_6"]
    
    result = await evaluator.evaluate_query(query, ground_truth, top_k=3)
    
    assert result["query"] == query
    assert "doc_1" in result["retrieved_doc_ids"]
    assert "doc_3" in result["retrieved_doc_ids"]
    assert "doc_5" in result["retrieved_doc_ids"] # Mock data, not ground truth
    assert result["precision_at_k"] == 2/3 # doc_1, doc_3 are in top 3 retrieved and ground truth
    assert result["recall_at_k"] == 2/3 # doc_1, doc_3 found out of 3 ground truth
    assert result["mrr"] == 1.0 # doc_1 is at rank 1
    assert result["retrieved_count"] == 3

@pytest.mark.asyncio
async def test_evaluate_retrieval_suite(evaluator, mock_rag_engine):
    test_suite = [
        ("financial performance", ["doc_1", "doc_3"]),
        ("economic outlook", ["doc_2", "doc_4"]),
        ("market analysis", ["doc_5", "doc_7"]) # Query that returns no results from mock
    ]
    
    results = await evaluator.evaluate_retrieval_suite(test_suite, top_k=2)
    
    assert "overall_metrics" in results
    assert "individual_results" in results
    assert len(results["individual_results"]) == 3

    # Check first query
    first_query_result = results["individual_results"][0]
    assert first_query_result["query"] == "financial performance"
    assert first_query_result["precision_at_k"] == 1.0 # doc_1 in top 2, doc_3 in top 2 from mock
    assert first_query_result["recall_at_k"] == 1.0 # doc_1, doc_3 found out of 2 ground truth

    # Check second query
    second_query_result = results["individual_results"][1]
    assert second_query_result["query"] == "economic outlook"
    assert second_query_result["precision_at_k"] == 1.0 # doc_2 in top 2, doc_4 in top 2 from mock
    assert second_query_result["recall_at_k"] == 1.0 # doc_2, doc_4 found out of 2 ground truth

    # Check third query (no results from mock)
    third_query_result = results["individual_results"][2]
    assert third_query_result["query"] == "market analysis"
    assert third_query_result["precision_at_k"] == 0.0
    assert third_query_result["recall_at_k"] == 0.0
    assert third_query_result["mrr"] == 0.0
    assert third_query_result["retrieved_count"] == 0

    # Overall averages - these would vary based on mock data. For now, check non-zero for successful run
    assert results["overall_metrics"]["average_precision_at_k"] > 0
    assert results["overall_metrics"]["average_recall_at_k"] > 0
    assert results["overall_metrics"]["average_mrr"] > 0
