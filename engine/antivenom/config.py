"""Configuration and feature flags.

Three flags, each degrading to a local fallback:

===========  =========================  ==========================================
flag         on                         off (the fallback)
===========  =========================  ==========================================
``mongo``    Atlas: $graphLookup,       in-memory NetworkX graph with the same
             $vectorSearch, change      store interface
             streams
``vlm``      OpenRouter vision model    cached extraction replayed from disk
``voice``    ElevenLabs cross-exam      the same words rendered as text on screen
===========  =========================  ==========================================

All three off is the **demo floor**: plant -> fire -> diagnose -> operate must
still run end to end and the cascade must still render. That path is the
insurance policy for venue WiFi, so it is a tested requirement, not a courtesy.
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ENGINE_ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
CACHE_DIR = DATA_DIR / "cache"
FIXTURES_DIR = DATA_DIR / "fixtures"


class Features(BaseSettings):
    """Independently disableable integrations."""

    model_config = SettingsConfigDict(env_prefix="ANTIVENOM_FEATURE_", extra="ignore")

    mongo: bool = True
    vlm: bool = True
    voice: bool = True

    @property
    def demo_floor(self) -> bool:
        """True when every integration is off — the offline insurance path."""
        return not (self.mongo or self.vlm or self.voice)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANTIVENOM_",
        env_file=(REPO_ROOT / ".env", ENGINE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── services ────────────────────────────────────────────────────────────
    # Read without the ANTIVENOM_ prefix; these are conventional names.
    mongodb_uri: str = Field(default="", validation_alias="MONGODB_URI")
    mongodb_db: str = Field(default="antivenom", validation_alias="MONGODB_DB")
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )
    elevenlabs_api_key: str = Field(default="", validation_alias="ELEVENLABS_API_KEY")
    elevenlabs_agent_id: str = Field(default="", validation_alias="ELEVENLABS_AGENT_ID")
    elevenlabs_voice_id: str = Field(default="", validation_alias="ELEVENLABS_VOICE_ID")

    # ─── models ──────────────────────────────────────────────────────────────
    # Deliberately unset. Read the OpenRouter model list at build time and pin
    # a current id — model ids churn and a hardcoded guess will 404 on stage.
    vlm_model: str = ""
    ablation_model: str = ""
    agent_model: str = ""
    embedding_dims: int = 1536

    # ─── run parameters (demo-tuned) ─────────────────────────────────────────
    ablation_passes: int = Field(default=3, ge=1, le=25)
    """Counterfactual re-runs per candidate belief. Higher is more stable and
    slower; 3 is the tuned trade-off for a live stage."""

    blast_max_depth: int = Field(default=6, ge=1, le=32)
    support_threshold: int = Field(default=1, ge=0)
    """Independent clean sources a descendant needs to survive excision."""

    trust_damping: float = Field(default=0.6, ge=0.0, le=1.0)
    """Per-hop attenuation of the distrust signal. This is what stops one bad
    image from nuking a third of the store — a judge will ask about it."""

    random_seed: int = 1337
    benign_sessions: int = Field(default=20, ge=0)

    # ─── event server ────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8787

    def service_problems(self) -> list[str]:
        """Flags that are on without the credential they need.

        Checked explicitly by ``antivenom doctor`` and by any command that
        actually reaches a service, rather than raised from a model validator.
        Validating at construction time would mean a fresh clone could not run
        ``antivenom demo`` or the test suite, which is the opposite of the
        offline-first behaviour the feature flags exist to provide.
        """
        f = features()
        problems: list[str] = []
        if f.mongo and not self.mongodb_uri:
            problems.append(
                "FEATURE_MONGO is on but MONGODB_URI is empty. Point it at the Atlas "
                "Hackathon Sandbox cluster, or set ANTIVENOM_FEATURE_MONGO=0 to run on "
                "the in-memory store."
            )
        if f.vlm and not self.openrouter_api_key:
            problems.append(
                "FEATURE_VLM is on but OPENROUTER_API_KEY is empty. Set the key, or set "
                "ANTIVENOM_FEATURE_VLM=0 to replay cached extractions."
            )
        if f.voice and not self.elevenlabs_api_key:
            problems.append(
                "FEATURE_VOICE is on but ELEVENLABS_API_KEY is empty. Set the key, or set "
                "ANTIVENOM_FEATURE_VOICE=0 to render the interrogation as text."
            )
        return problems

    def require_services(self) -> None:
        """Fail loudly before touching a service. Silently degrading to the local
        store would mean discovering on stage that the build never reached the
        sandbox cluster."""
        problems = self.service_problems()
        if problems:
            raise RuntimeError("\n".join(problems))

    def seeded_random(self) -> random.Random:
        """A fresh seeded RNG. Never use the global ``random`` module — a shared
        global makes ablation ordering depend on whatever ran before it, and the
        cascade then animates differently on every run."""
        return random.Random(self.random_seed)


@lru_cache(maxsize=1)
def features() -> Features:
    return Features()


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()


def reset_caches() -> None:
    """Drop memoised config. Tests use this after monkeypatching the env."""
    features.cache_clear()
    settings.cache_clear()
