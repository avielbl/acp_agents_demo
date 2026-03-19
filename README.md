# ACP Multi-Agent Demo: Meeting Transcript → Action Item Tracker

A production-shaped demo of a **distributed multi-agent system** built on the [Agent Communication Protocol (ACP)](https://agentcommunicationprotocol.dev/) SDK.

Three specialised agents — **Planner**, **Executor**, and **Validator** — each run as an **independent ACP microservice** and communicate over HTTP, orchestrated by a [LangGraph](https://github.com/langchain-ai/langgraph) state machine. Together they transform a raw meeting transcript into a clean, validated list of action items.

---

## Why This Demo?

Real-world agentic systems need more than "call an LLM in a loop." They need:

- **Clear agent roles** — each agent owns a single responsibility
- **Structured inter-agent messaging** — typed, traceable messages instead of raw strings
- **State persistence** — resume interrupted runs; audit past executions
- **Validation feedback loops** — agents can reject and request rework, not just pass output forward

This demo implements all four patterns using open-source tools, keeping the codebase small enough to read in one sitting.

---

## Architecture

### Distributed Microservice Architecture

Each agent runs as a standalone ACP HTTP server. The LangGraph orchestrator calls them over the network:

```
┌──────────────────────────────────────────────────────────────────┐
│         Orchestrator  (LangGraph + FastAPI / CLI)                │
│                                                                  │
│  planner_agent()  ──── HTTP POST ──►  localhost:8001/runs        │
│  executor_agent() ──── HTTP POST ──►  localhost:8002/runs        │
│  validator_agent() ─── HTTP POST ──►  localhost:8003/runs        │
│                                                                  │
│  Shared BusState (LangGraph StateGraph + SQLite checkpoint)      │
│    ├── mailbox[]           ACP messages exchanged                │
│    ├── segments[]          Planner output                        │
│    ├── action_items[]      Executor output                       │
│    └── validation_issues[] Validator feedback                    │
└──────────────────────────────────────────────────────────────────┘
         │                    │                   │
         ▼                    ▼                   ▼
  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
  │   Planner   │    │   Executor   │    │  Validator   │
  │  :8001      │    │   :8002      │    │   :8003      │
  │  ACP Server │    │  ACP Server  │    │  ACP Server  │
  └─────────────┘    └──────────────┘    └──────────────┘
```

### Agent Message Flow

```
Planner ──task──► Executor ──result──► Validator
                    ▲                      │
                    └──── validation_fail ──┘  (retry up to 2×)
```

### Agent Roles

| Agent | Input | Output | LLM? |
|---|---|---|---|
| **Planner** | Raw transcript | Topic segments | Yes (Gemini) |
| **Executor** | Segments + validation issues | Action items `{description, owner, deadline}` | Yes (Gemini) |
| **Validator** | Action items | Pass / fail + issues list | No (rule-based) |

### Validation Rules (Validator)
1. Every action item must have a non-empty **owner**
2. Every action item must have a non-empty **deadline**
3. No **duplicate** descriptions (case-insensitive)

If any rule fails and `retry_count < 2`, the Validator sends a `validation_fail` message back to the Executor with the specific issues. The Executor re-extracts with the feedback in its prompt.

### Message Bus (ACPMessage)

Every inter-agent communication is a typed `ACPMessage`:

```python
{
  "msg_id":   "uuid4",
  "ts":       "2026-03-08T10:23:01.123456+00:00",
  "sender":   "planner" | "executor" | "validator" | "user",
  "receiver": "...",
  "msg_type": "task" | "result" | "validation_pass" | "validation_fail",
  "content":  "<JSON payload>",
  "meta":     { ... },
  "trace":    { "step": 3 }
}
```

All messages are written to a **JSONL audit log** (`logs/acp_<timestamp>.jsonl`) and the full bus state is **checkpointed to SQLite** after every node via LangGraph's `SqliteSaver`.

---

## Project Structure

```
acp_agents_demo/
├── agents/                       # ACP microservice entry points
│   ├── planner_service.py        # Planner ACP Server  (port 8001)
│   ├── executor_service.py       # Executor ACP Server (port 8002)
│   └── validator_service.py      # Validator ACP Server (port 8003)
├── data/
│   └── sample_transcript.txt     # Realistic sprint planning transcript
├── src/
│   ├── schema.py                 # BusState, ActionItem TypedDicts
│   ├── llm.py                    # Gemini 2.0 Flash singleton
│   ├── logger.py                 # JSONL structured audit logger
│   ├── graph.py                  # LangGraph StateGraph + SqliteSaver
│   ├── events.py                 # Thread-safe SSE event emitter
│   ├── utils.py                  # LLM response cleaning helpers
│   └── agents/
│       ├── planner.py            # Orchestrator node → calls :8001
│       ├── executor.py           # Orchestrator node → calls :8002
│       └── validator.py          # Orchestrator node → calls :8003
├── static/
│   └── index.html                # Single-page demo UI (SVG + live feed)
├── start_agents.py               # Starts all 3 agent microservices
├── server.py                     # FastAPI UI server with SSE streaming
├── main.py                       # CLI entry point
├── requirements.txt
└── .env.example
```

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/avielbl/acp_agents_demo.git
cd acp_agents_demo
pip install -r requirements.txt
```

### 2. Set up your API key

```bash
cp .env.example .env
# Open .env and add your Gemini API key:
# GEMINI_API_KEY=your_key_here
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com/app/apikey).

### 3. Start the agent microservices

In a dedicated terminal, launch all three ACP agent servers:

```bash
python start_agents.py
```

This starts Planner (`:8001`), Executor (`:8002`), and Validator (`:8003`) as independent processes and waits until all are healthy.

> You can also start them individually:
> ```bash
> python agents/planner_service.py
> python agents/executor_service.py
> python agents/validator_service.py
> ```

### 4. Launch the web UI (recommended)

In a second terminal:

```bash
uvicorn server:app --reload
```

Then open **http://localhost:8000** in your browser. Click **▶ Run Pipeline** to watch the agents communicate in real time.

### 5. Run the CLI instead

```bash
python main.py
# or with a custom transcript:
python main.py --transcript path/to/your/meeting.txt
```

### 6. Resume a previous run (checkpointing)

```bash
python main.py --thread-id <uuid-from-previous-run>
```

---

## Example Output

```
Thread ID : a1b2c3d4-...
Transcript: data/sample_transcript.txt (1821 chars)

Starting multi-agent pipeline...

[Planner] Segmenting transcript into discussion topics...
[Planner] Identified 4 topic segments.

[Executor] Extracting action items from each segment...
[Executor] Extracted 8 action items total.

[Validator] Validating 8 action items...
[Validator] Found 2 issue(s). Requesting re-extraction (retry 1/2).
  - Item 5 ('Define integration test criteria for billing cutover') is missing a deadline.
  - Item 6 ('Update team working agreement') is missing a deadline.

[Executor] Re-extracting action items (retry 1). Issues to fix: [...]
[Executor] Extracted 8 action items total.

[Validator] All 8 action items passed validation.

================================================================================
FINAL ACTION ITEMS
================================================================================
#    Description                             Owner               Deadline          Seg
--------------------------------------------------------------------------------
1    Implement onboarding screens frontend   Carol               2026-03-11            0
2    Document and share onboarding API spec  Bob                 2026-03-04            0
3    Write regression tests for onboarding   Dave                2026-03-13            0
4    Get legal sign-off on privacy notice    Alice               2026-03-08            0
5    Draft billing microservice design doc   Bob                 2026-03-05            1
6    Provision K8s namespace and CI/CD pipe  Eve                 2 days after des      1
7    Define integration test criteria        Dave                2026-03-20            1
8    Upgrade Kubernetes cluster to 1.30      Eve                 2026-03-21            2
================================================================================

Audit log : logs/acp_20260308T102301.jsonl
Checkpoint: checkpoints/bus.sqlite
Messages  : 5 total ACP messages exchanged
```

---

---

## Technical Developer Guide

This section provides a detailed walk-through of the project's internals for developers.

### 🏗️ Architecture Overview

The system is built using a modern distributed AI-agent architecture:
- **Agent Microservices**: Each agent (Planner, Executor, Validator) is a standalone HTTP process powered by the `acp-sdk` `Server` class.
- **Agent Orchestration**: LangGraph manages state, routing, and retry logic. Each LangGraph node calls its corresponding agent over HTTP via the `acp-sdk` `Client`.
- **Backend**: FastAPI provides the web UI server and SSE (Server-Sent Events) streaming.
- **Persistence**: SQLite-based checkpointer (`checkpoints/bus.sqlite`) saves every state transition.
- **Frontend**: Vanilla HTML/JS with a dynamic SVG-based communication graph and real-time state inspector.

---

### 🔌 ACP SDK Integration

This demo uses the [ACP SDK](https://github.com/i-am-bee/acp-sdk) at two layers:

#### Agent Servers (`acp_sdk.server.app.create_app`)

Each agent is exposed as a real HTTP endpoint using the `create_app` function and the `@agent` decorator:

```python
import uvicorn
from acp_sdk.server.agent import agent
from acp_sdk.server.app import create_app
from acp_sdk.models import Message, MessagePart

@agent(name="planner", description="...")
async def planner_agent(input: list[Message]) -> Message:
    transcript = input[0].parts[0].content
    # ... run LLM ...
    return Message(role="agent", parts=[MessagePart(...)])

if __name__ == "__main__":
    app = create_app(planner_agent)
    uvicorn.run(app, host="127.0.0.1", port=8001)
```

The SDK automatically exposes standard ACP REST endpoints:
- `GET /agents` — list registered agents and their manifests
- `POST /runs` — execute an agent (sync, async, or streaming)
- `GET /ping` — health check

#### Orchestrator Client (`acp_sdk.client.Client`)

The LangGraph orchestrator calls each remote agent using the ACP `Client`:

```python
from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart

async with Client(base_url="http://127.0.0.1:8001") as client:
    run = await client.run_sync(
        Message(role="user", parts=[MessagePart(content_type="text/plain", content=transcript)]),
        agent="planner",
    )
segments = json.loads(run.output[0].parts[0].content)
```

This replaces what was previously a plain Python function call with a real cross-process HTTP request — turning the monolith into a true distributed system.

### 📊 Data Modeling (`src/schema.py`)

The system centers around two main structures:

#### 1. `BusState` (The "Blackboard")
This is the shared state passed between all agents.
```python
class BusState(TypedDict):
    goal: str              # The initial transcript
    done: bool             # Terminal flag
    mailbox: Annotated[List[dict], operator.add] # History of ACPMessages
    active_role: str       # Currently active agent
    segments: List[str]    # Transcript chunks (Planner output)
    action_items: List[dict] # Extracted items (Executor output)
    retry_count: int       # Number of validation retries
```

#### 2. `ACPMessage` (The Protocol)
Agents communicate using a standardized message format:
```python
class ACPMessage(BaseModel):
    msg_id: str
    ts: str
    sender: Role
    receiver: Role
    msg_type: MsgType      # task, result, validation_pass/fail
    content: str           # JSON payload
```

---

### 🤖 Agent Components

#### 1. Planner (`src/agents/planner.py`)
- **Role**: Meeting Analyst.
- **Task**: Uses LLM to segment the raw transcript into topical chunks.
- **Output**: Sets the `segments` list in the state and hands off to the **Executor**.

#### 2. Executor (`src/agents/executor.py`)
- **Role**: Item Extractor.
- **Task**: Iterates through each segment and extracts action items (Description, Owner, Deadline).
- **Retry Logic**: Can receive feedback from the Validator to correct previously identified issues.

#### 3. Validator (`src/agents/validator.py`)
- **Role**: Quality Gate.
- **Task**: Synchronously validates the extracted items for missing fields or duplicates.
- **Transitions**:
  - If valid: Marks `done=True`.
  - If invalid: Increments `retry_count` and sends a `validation_fail` message back to the **Executor**.

---

### 🔄 Real-Time Event System (`src/events.py`)

The UI updates in real-time without polling using **Server-Sent Events (SSE)**.

1. **ContextVar Isolation**: `src/events.py` uses `ContextVar` to ensure that each request (run) sees its own event emitter, even in a multi-threaded FastAPI environment.
2. **Intermediate States**: In `server.py`, we use `graph_app.stream(..., stream_mode="values")` to capture intermediate states as they happen.
3. **SSE Mapping**: Backend events like `agent_start`, `acp_message`, and `state_update` are sent to the frontend where they trigger SVG animations and log updates.

---

### 💾 Persistence & Debugging

- **Checkpoints**: Every step of the graph is recorded in `checkpoints/bus.sqlite`. This allows for time-travel debugging and resuming interrupted runs through the `--thread-id` flag.
- **DB Inspector**: The built-in Database Inspector provides a raw view of these internal tables directly from the browser UI.

---

## License

[MIT](LICENSE)
