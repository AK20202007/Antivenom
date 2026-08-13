from __future__ import annotations

import pytest

from antivenom.attack.seed import plant
from antivenom.config import reset_caches
from antivenom.core.trust import reset_channel_learning
from antivenom.db.local import LocalStore
from antivenom.events import BUS


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test runs on the demo floor with a clean bus.

    Flags off means no test can accidentally reach Atlas, OpenRouter or
    ElevenLabs — which also means the suite runs on a plane, which is where
    quite a lot of hackathon code gets written.
    """
    monkeypatch.setenv("ANTIVENOM_FEATURE_MONGO", "0")
    monkeypatch.setenv("ANTIVENOM_FEATURE_VLM", "0")
    monkeypatch.setenv("ANTIVENOM_FEATURE_VOICE", "0")
    # Small enough to keep fixtures fast, large enough that the hashing-trick
    # embedding does not collide into noise. At 32 dimensions retrieval becomes
    # effectively random and the tests stop testing anything real.
    monkeypatch.setenv("ANTIVENOM_EMBEDDING_DIMS", "512")
    reset_caches()
    BUS.clear()
    # Channel learning is process-wide state. Without this, one test's surgery
    # raises the survival bar for every test that runs after it.
    reset_channel_learning()
    yield
    reset_caches()
    BUS.clear()
    reset_channel_learning()


@pytest.fixture
async def store() -> LocalStore:
    """An empty in-memory store."""
    s = LocalStore()
    await s.connect()
    return s


@pytest.fixture
async def planted(store: LocalStore) -> LocalStore:
    """A store seeded with the full poisoned scenario."""
    await plant(store)
    return store
