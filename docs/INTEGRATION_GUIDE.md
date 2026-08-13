# Integrating Antivenom with Your Custom Agent

Antivenom is designed as a **post-hoc surgical repair middleware** that plugs directly into any custom LLM Agent, vector database, or framework (LangChain, LlamaIndex, OpenAI Assistants, AutoGen, CrewAI, or custom Python loops).

---

## 3-Step Setup

### Step 1: Install Antivenom (1 Line) & Set Environment

Install Antivenom directly from GitHub:

```bash
pip install git+https://github.com/AK20202007/Antivenom.git
```

Set your MongoDB Atlas & OpenRouter keys in `.env`:

```ini
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
OPENROUTER_API_KEY=your-openrouter-key
ANTIVENOM_VLM_MODEL=google/gemini-2.5-flash
ANTIVENOM_ABLATION_MODEL=google/gemini-2.5-flash-lite
ANTIVENOM_AGENT_MODEL=google/gemini-2.5-flash
```

---

### Step 2: Initialize `AntivenomClient` in Your Agent

```python
from antivenom import AntivenomClient
from antivenom.schemas import SourceType, Channel, Outcome

# Connect client to MongoDB Atlas
client = AntivenomClient()
await client.connect()
```

---

### Step 3: Plug into Your Agent's Ingest, Retrieve, and Act Cycle

#### 1. Ingest Artifacts (User uploads / Web scraping)
```python
# Ingest untrusted content — Antivenom extracts atomic claims & stores provenance edges
beliefs = await client.ingest_artifact(
    uri="s3://my-bucket/untrusted_policy.png",
    type_=SourceType.IMAGE,
    channel=Channel.UPLOAD,
    label="policy.png"
)
```

#### 2. Retrieve Context for Agent Prompts
```python
# Retrieves live (non-invalidated) beliefs from MongoDB
retrieved_beliefs, retrieved_ids = await client.retrieve_context(user_prompt, limit=5)

# Build system prompt with retrieved context
context_str = "\n".join([b.text for b in retrieved_beliefs])
agent_prompt = f"Context:\n{context_str}\n\nUser Question: {user_prompt}"
```

#### 3. Log Decisions & Trigger Surgical Repair on Bad Actions
```python
# Log what action your agent took and what belief IDs were in its context
decision = await client.log_decision(
    prompt=user_prompt,
    action=agent_action_name,
    action_args=agent_action_args,
    retrieved_belief_ids=retrieved_ids,
    outcome=Outcome.HARMFUL if is_harmful_action else Outcome.OK
)

# If an exfiltration / harmful action fires, operate!
if decision.outcome == Outcome.HARMFUL:
    repair_summary = await client.repair_memory(decision)
    print("Culprit excised:", repair_summary["culprit_id"])
    print("Infected lineage excised:", repair_summary["excised"])
    print("Corroborated beliefs survived:", repair_summary["survived"])
```

---

## Live Dashboard Streaming

To visualize your agent's memory graph, blast radius, and surgical repairs live in the Web UI:
1. Start the event server: `python -m antivenom.main serve`
2. Open the dashboard at `http://localhost:5173`
3. Antivenom automatically streams all live agent events, causal ablation bar rankings, and graph dissections in real-time over WebSocket!
