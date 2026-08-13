# Setup

Everything below is optional. The full loop already runs with none of it:

```bash
cd engine && uv venv --python 3.11 && uv pip install -e ".[dev]"
antivenom doctor && antivenom full --local && antivenom eval
```

What the four steps buy you is the live path, and step 1 is the only one that
affects eligibility.

---

## 1. Atlas sandbox  ·  **the eligibility blocker**

A build outside the Hackathon Sandbox is ineligible for the finalist round.

1. From the sandbox page, click **Provision an Atlas Sandbox Project**.
2. Inside it, **Create a cluster** (M0 free tier is fine).
3. **Database Access** → add a user, note the password.
4. **Network Access** → add your IP, or `0.0.0.0/0` for the day.
5. **Connect → Drivers → Python** → copy the connection string.

```bash
cp .env.example .env
# set MONGODB_URI to the string, with the password substituted in

cd engine
antivenom db init     # standard indexes + the vector search index
antivenom doctor      # run until "vector index: ok"
```

**The one that catches people:** the Atlas vector index builds asynchronously.
Until it reports queryable, `$vectorSearch` returns nothing with no error, which
looks exactly like broken retrieval. `doctor` checks for it specifically, so run
it until it passes rather than assuming.

## 2. Model ids

`.env.example` ships with ids verified against the live OpenRouter list on
2026-08-13. Re-check before the event, since ids churn and a stale one 404s on
stage.

| variable | default | why |
|---|---|---|
| `ANTIVENOM_VLM_MODEL` | `google/gemini-2.5-flash` | reads 8.5px low-contrast footer text; needs to be good, not cheap |
| `ANTIVENOM_ABLATION_MODEL` | `openai/gpt-5-nano` | runs 24x per diagnosis, so cost and latency bite here |
| `ANTIVENOM_AGENT_MODEL` | `openai/gpt-5-mini` | tool calling, follows a stored policy unprompted |

**Embeddings come from MongoDB, not from the chat provider.** OpenRouter serves
no embeddings endpoint at all, so vectors come from MongoDB's Embedding and
Reranking API (Voyage AI) at `https://ai.mongodb.com/v1/embeddings`. That keeps
embeddings, the vector index and the graph traversal on one platform, and it
means OpenRouter credits alone are enough to run everything.

```bash
MONGODB_EMBEDDING_API_KEY=...          # from the Atlas UI
ANTIVENOM_EMBEDDING_MODEL=voyage-3.5
ANTIVENOM_EMBEDDING_DIMS=1024          # must match the vector index exactly
```

Leave the key blank and it falls back to the offline lexical embedding, which
works but is not semantic.

To run chat on Fireworks instead:

```bash
ANTIVENOM_PROVIDER=fireworks
FIREWORKS_API_KEY=...
# ids look like accounts/fireworks/models/<name>
```

Both providers speak the OpenAI wire format, so nothing else changes.
`ANTIVENOM_USE_LANGCHAIN=1` routes through LangChain for provider-agnostic
handles and tracing; behaviour is identical either way.

## 3. Deploying the site

Deploys are manual, on purpose. CI builds and tests the front end but does not
publish, so no API token has to exist anywhere. Your local `wrangler` OAuth
login is the only credential involved.

```bash
cd web && npm run build && npx wrangler pages deploy dist --project-name antivenom
```

That publishes to [antivenom.pages.dev](https://antivenom.pages.dev).

## 4. ElevenLabs

Defense side only, never used to generate a payload. `FEATURE_VOICE=0` renders
the same words as text, so the beat survives without it.

```bash
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...
```

## Repo metadata  ·  needs the owner

`AK20202007` owns the repo and `KarthikSubramanian07` has write, not admin.
Description and topics require admin, and GitHub returns a confusing `404`
rather than `403` when you lack it. Either have the owner grant admin, or have
them run the command in [issue #5](https://github.com/AK20202007/Antivenom/issues).
