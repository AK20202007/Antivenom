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

**OpenRouter serves no embeddings endpoint.** If you want real semantic
embeddings rather than the offline lexical ones, they have to come from
Fireworks or Atlas's own embedding API, and `ANTIVENOM_EMBEDDING_DIMS` must
match whatever you pick or the vector index returns nothing.

To run on Fireworks instead:

```bash
ANTIVENOM_PROVIDER=fireworks
FIREWORKS_API_KEY=...
# ids look like accounts/fireworks/models/<name>
```

Both providers speak the OpenAI wire format, so nothing else changes.
`ANTIVENOM_USE_LANGCHAIN=1` routes through LangChain for provider-agnostic
handles and tracing; behaviour is identical either way.

## 3. Cloudflare auto-deploy

The site is already live at [antivenom.pages.dev](https://antivenom.pages.dev)
and manual deploys work today:

```bash
cd web && npm run build && npx wrangler pages deploy dist --project-name antivenom
```

Auto-deploy on push needs two repo secrets. **Wrangler's stored credential is an
OAuth token and cannot be reused here**, so the API token has to be created in
the dashboard:

1. [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
   → **Create Token** → template **Edit Cloudflare Workers**, or a custom token
   with **Account · Cloudflare Pages · Edit**.
2. Copy it once; it is not shown again.

```bash
gh secret set CLOUDFLARE_API_TOKEN --repo AK20202007/Antivenom --body "<token>"
gh secret set CLOUDFLARE_ACCOUNT_ID --repo AK20202007/Antivenom --body "e5e342f3ca2f33158f6f1dd40c039be0"
```

Then every push to `main` publishes, and every PR gets its own preview URL.

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
