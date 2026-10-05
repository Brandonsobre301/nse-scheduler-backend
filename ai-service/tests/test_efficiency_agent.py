"""
test_efficiency_agent.py — unit tests for the AI efficiency inference agent.

Traceability: docs/estimation-engine/test_plan.md §6.4 (TC-A*).
MongoDB and the embedding model are mocked — see conftest.py for the stub
modules and the _patch_backend() helper below for per-test wiring.
"""

from services import efficiency_agent as ea


class _FakeModel:
    def encode(self, text: str):
        return [0.0] * 384  # content is irrelevant; the fake Mongo client ignores it


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def aggregate(self, pipeline):
        return self._docs


class _FakeDB:
    def __init__(self, docs):
        self._docs = docs

    def __getitem__(self, name):
        return _FakeCollection(self._docs)


class _FakeMongoClient:
    def __init__(self, docs):
        self._docs = docs

    def __getitem__(self, name):
        return _FakeDB(self._docs)

    def close(self):
        pass


def _patch_backend(monkeypatch, docs):
    monkeypatch.setattr(ea, "_get_model", lambda: _FakeModel())
    monkeypatch.setattr(ea, "MongoClient", lambda uri: _FakeMongoClient(docs))


def test_no_matches_falls_back_to_default(monkeypatch):  # TC-A02
    _patch_backend(monkeypatch, docs=[
        {"jobNumber": "1", "jobName": "X", "actualEfficiency": 0.9, "score": 0.2},
    ])
    result = ea.infer_efficiency(project_type="Unrepresented Type")
    assert result.matchCount == 0
    assert result.inferredEfficiency == 0.80
    assert result.confidence == 0.0
    assert "industry default" in result.warning


def test_sparse_matches_warn_low_count(monkeypatch):  # TC-A03
    _patch_backend(monkeypatch, docs=[
        {"jobNumber": "1", "jobName": "A", "actualEfficiency": 0.80, "score": 0.9},
    ])
    result = ea.infer_efficiency(project_type="Office TI")
    assert result.matchCount == 1
    assert "Only 1 similar project" in result.warning


def test_moderate_confidence_warns(monkeypatch):  # TC-A04
    docs = [
        {"jobNumber": str(i), "jobName": f"Job{i}", "actualEfficiency": 0.8, "score": 0.6}
        for i in range(3)
    ]
    _patch_backend(monkeypatch, docs)
    result = ea.infer_efficiency(project_type="Office TI")
    assert result.matchCount == 3
    assert result.confidence < 0.70
    assert "moderate" in result.warning


def test_weighted_average_is_correct(monkeypatch):  # TC-A05
    docs = [
        {"jobNumber": "1", "jobName": "A", "actualEfficiency": 1.0, "score": 0.9},
        {"jobNumber": "2", "jobName": "B", "actualEfficiency": 0.5, "score": 0.1},
    ]
    _patch_backend(monkeypatch, docs)
    result = ea.infer_efficiency(project_type="Office TI")
    expected = (1.0 * 0.9 + 0.5 * 0.1) / (0.9 + 0.1)
    assert result.inferredEfficiency == round(expected, 4)
    assert result.matchCount == 2


def test_matches_missing_efficiency_are_discarded(monkeypatch):
    docs = [
        {"jobNumber": "1", "jobName": "A", "actualEfficiency": None, "score": 0.95},
        {"jobNumber": "2", "jobName": "B", "actualEfficiency": 0.75, "score": 0.80},
    ]
    _patch_backend(monkeypatch, docs)
    result = ea.infer_efficiency(project_type="Office TI")
    assert result.matchCount == 1
    assert result.inferredEfficiency == 0.75


def test_matches_below_min_score_are_discarded(monkeypatch):
    docs = [
        {"jobNumber": "1", "jobName": "A", "actualEfficiency": 0.9, "score": 0.49},  # just under MIN_SCORE
        {"jobNumber": "2", "jobName": "B", "actualEfficiency": 0.75, "score": 0.80},
    ]
    _patch_backend(monkeypatch, docs)
    result = ea.infer_efficiency(project_type="Office TI")
    assert result.matchCount == 1
    assert result.inferredEfficiency == 0.75


def test_build_query_text_handles_missing_fields():  # TC-A08 (template consistency)
    text = ea._build_query_text(None, None, None, None)
    assert text == "unknown type, unknown budget, unknown supervisor"


def test_build_query_text_includes_all_signals():
    text = ea._build_query_text("Office TI", 1200, "Joe Lawhorn", "Acme HQ")
    assert text == "Office TI, 1200 hours budgeted, supervisor Joe Lawhorn, Acme HQ"
