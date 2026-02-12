from app.services.spoke_c_rag import RAGResult


def evaluate_results(results, expected_terms):
    hits = 0
    for term in expected_terms:
        if any(term.lower() in r.content.lower() for r in results):
            hits += 1
    precision = hits / max(len(results), 1)
    recall = hits / max(len(expected_terms), 1)
    return precision, recall


def test_rag_eval_basic():
    results = [
        RAGResult(chunk_id="1", content="Revenue increased due to pricing power", similarity=0.9),
        RAGResult(chunk_id="2", content="Debt maturity schedule", similarity=0.7),
    ]
    precision, recall = evaluate_results(results, ["revenue", "debt"])
    assert precision >= 0.5
    assert recall == 1.0
