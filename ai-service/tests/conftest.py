"""
conftest.py — pytest fixtures and import setup for the ai-service test suite.

Stubs heavy/optional runtime dependencies (`pymongo`, `sentence-transformers`,
`dotenv`) so unit and contract tests can import `efficiency_agent`/`main`
without installing torch or connecting to a real Atlas cluster. Tests that
need the real backend monkeypatch the specific functions they need
(`_get_model`, `MongoClient`) — see test_efficiency_agent.py.
"""

import sys
import types
from pathlib import Path

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))


def _install_stub(name: str, **attrs) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(module, attr_name, value)
    sys.modules[name] = module


_install_stub("dotenv", load_dotenv=lambda *a, **k: None)


class _UnconfiguredMongoClient:
    """Raised only if a test forgets to monkeypatch MongoClient for a path that queries Atlas."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __getitem__(self, name: str):
        raise RuntimeError(
            "MongoClient stub was not monkeypatched for this test. "
            "Patch 'services.efficiency_agent.MongoClient' before calling infer_efficiency()."
        )

    def close(self) -> None:
        pass


_install_stub("pymongo", MongoClient=_UnconfiguredMongoClient)


class _UnconfiguredSentenceTransformer:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def encode(self, text: str):
        raise RuntimeError(
            "SentenceTransformer stub was not monkeypatched for this test. "
            "Patch 'services.efficiency_agent._get_model' before calling infer_efficiency()."
        )


_install_stub("sentence_transformers", SentenceTransformer=_UnconfiguredSentenceTransformer)
