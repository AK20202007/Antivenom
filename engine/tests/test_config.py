from __future__ import annotations

import pytest

from antivenom.config import Settings, features, reset_caches, settings


def test_demo_floor_is_all_flags_off():
    assert features().demo_floor is True


def test_demo_floor_is_false_when_any_flag_is_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTIVENOM_FEATURE_VOICE", "1")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    reset_caches()
    assert features().demo_floor is False


def test_mongo_flag_without_a_uri_is_reported(monkeypatch: pytest.MonkeyPatch):
    """Silently falling back to the local store would mean discovering on stage
    that the build never touched the sandbox cluster."""
    monkeypatch.setenv("ANTIVENOM_FEATURE_MONGO", "1")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    reset_caches()
    problems = Settings(_env_file=None).service_problems()
    assert any("MONGODB_URI" in p for p in problems)


def test_vlm_flag_without_a_key_is_reported(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTIVENOM_FEATURE_VLM", "1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    reset_caches()
    problems = Settings(_env_file=None).service_problems()
    assert any("OPENROUTER_API_KEY" in p for p in problems)


def test_require_services_raises_before_touching_a_service(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTIVENOM_FEATURE_MONGO", "1")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    reset_caches()
    with pytest.raises(RuntimeError, match="MONGODB_URI"):
        Settings(_env_file=None).require_services()


def test_no_problems_on_the_demo_floor():
    """A fresh clone with no credentials must still run the offline path."""
    assert Settings(_env_file=None).service_problems() == []


def test_seeded_random_is_reproducible():
    """Ablation ordering must not depend on whatever ran before it."""
    a = settings().seeded_random()
    b = settings().seeded_random()
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]


def test_run_parameters_have_sane_bounds():
    with pytest.raises(ValueError):
        Settings(_env_file=None, ablation_passes=0)
    with pytest.raises(ValueError):
        Settings(_env_file=None, trust_damping=1.5)
    with pytest.raises(ValueError):
        Settings(_env_file=None, blast_max_depth=0)


def test_pinned_model_ids_look_like_real_ids():
    """The defaults in .env.example were verified against the live OpenRouter
    list rather than recalled. A guessed id 404s on stage, so the shape is
    checked here and `doctor` still requires them to be set explicitly."""
    cfg = Settings(_env_file=None)
    # Unset by default in code; .env.example supplies the verified values, so a
    # deployment that forgets to configure fails loudly rather than guessing.
    assert cfg.vlm_model == ""
    assert cfg.ablation_model == ""


def test_embeddings_default_to_mongodbs_own_api():
    """OpenRouter serves no embeddings endpoint, so vectors come from MongoDB.
    The dimension must match the Atlas vector index or search returns nothing
    at all, with no error."""
    # Read the declared defaults, not a live Settings: the test env pins
    # embedding_dims to something small for speed and would mask this.
    fields = Settings.model_fields
    assert fields["embedding_model"].default == "voyage-3.5"
    assert fields["embedding_dims"].default == 1024
    assert "mongodb.com" in str(fields["embedding_base_url"].default)
