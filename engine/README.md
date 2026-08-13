# antivenom (engine)

The Python side: the surgery engine, the victim agent, the adversary, and the
evaluation harness. See the [repository README](../README.md) for what any of
this is for, and [docs/LANES.md](../docs/LANES.md) for who owns what.

## Install

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"          # engine + test tooling, no network deps
uv pip install -e ".[dev,mongo,llm,voice]"   # everything
```

The extras are split so the demo floor — every feature flag off — installs
without a single network dependency. That path has to work on a plane.

## Run

```bash
antivenom doctor              # preflight: sandbox, keys, indexes, fixture
antivenom plant --local       # seed a deterministic poisoned store
antivenom demo --write        # synthesise the run stream for the dashboard
antivenom serve               # local WebSocket event channel on :8787
```

## Test

```bash
pytest                        # runs entirely offline, all flags forced off
pytest --cov=antivenom
ruff check . && ruff format --check .
mypy antivenom
```
