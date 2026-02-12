from app.services.preciso_mathematics import visibility_graph_edges, exponential_gradient_update, PrecisoMathematicsService


def test_visibility_graph_edges_basic():
    values = [1.0, 3.0, 2.0, 4.0]
    edges = visibility_graph_edges(values)
    assert (0, 1) in edges
    assert (1, 2) in edges
    assert (2, 3) in edges


def test_exponential_gradient_update_normalizes():
    w = [0.5, 0.5]
    x = [1.02, 0.98]
    out = exponential_gradient_update(w, x, eta=0.1)
    assert abs(sum(out) - 1.0) < 1e-9
    assert out[0] > out[1]


def test_mathematics_service_extracts_series():
    facts = [
        {"entity": "A", "metric": "revenue", "period": "2024", "value": "10"},
        {"entity": "A", "metric": "revenue", "period": "2023", "value": "8"},
        {"entity": "A", "metric": "revenue", "period": "2022", "value": "6"},
    ]
    analysis = PrecisoMathematicsService().analyze(facts)
    assert analysis.series["A"]["revenue"]["2024"] == 10.0
    key = "A::revenue"
    assert key in analysis.derived
    assert analysis.visibility_graph[key]["edge_count"] >= 1
