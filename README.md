# ACP Multi-Agent Demo: Meeting Transcript → Action Item Tracker

A toy but production-shaped demo of a **multi-agent communication system** inspired by the [Agent Communication Protocol (ACP)](https://agentcommunicationprotocol.dev/) pattern described in the MarkTechPost article on production-grade multi-agent architectures.

Three specialised [LangGraph](https://github.com/langchain-ai/langgraph) agents — **Planner**, **Executor**, and **Validator** — collaborate through a shared message bus to transform a raw meeting transcript into a clean, validated list of action items.

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

```
┌────────────┐    task msg    ┌──────────────┐    result msg    ┌─────────────┐
│   Planner  │ ─────────────► │   Executor   │ ───────────────► │  Validator  │
│            │                │              │                  │             │
│ Segments   │                │ Extracts     │  ◄─────────────  │ Validates   │
│ transcript │                │ action items │  validation_fail │ completeness│
│ by topic   │                │ per segment  │                  │ & quality   │
└────────────┘                └──────────────┘                  └─────────────┘
       │                             ▲                                  │
       │                             │      retry (up to 2x)            │
       │                             └──────────────────────────────────┘
       │
       ▼
  Shared BusState (LangGraph StateGraph)
       │
       ├── mailbox[]            append-only list of all ACPMessages
       ├── segments[]           transcript chunks from Planner
       ├── action_items[]       structured items from Executor
       └── validation_issues[]  feedback from Validator
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
├── data/
│   └── sample_transcript.txt   # Realistic sprint planning transcript
├── src/
│   ├── schema.py               # ACPMessage, BusState, enums, ActionItem
│   ├── llm.py                  # Gemini 2.0 Flash singleton
│   ├── logger.py               # JSONL structured audit logger
│   ├── graph.py                # LangGraph StateGraph + SqliteSaver
│   ├── events.py               # Thread-safe SSE event emitter (ContextVar)
│   ├── utils.py                # LLM response cleaning and JSON parsing helpers
│   └── agents/
│       ├── planner.py          # Segment transcript into topics
│       ├── executor.py         # Extract action items per segment
│       └── validator.py        # Validate completeness, flag issues
├── static/
│   └── index.html              # Single-page demo UI (SVG graph + live feed)
├── server.py                   # FastAPI server with SSE streaming
├── main.py                     # CLI entry point
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

### 3. Launch the web UI (recommended)

```bash
uvicorn server:app --reload
```

Then open **http://localhost:8000** in your browser. The sample transcript is pre-loaded — click **▶ Run Pipeline** to watch the agents communicate in real time.

### 4. Run the CLI instead

```bash
python main.py
# or with a custom transcript:
python main.py --transcript path/to/your/meeting.txt
```

### 5. Resume a previous run (checkpointing)

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

The system is built using a modern AI-agent architecture:
- **Backend**: FastAPI (Python) provides the web server and SSE (Server-Sent Events) streaming.
- **Agent Orchestration**: LangGraph manages the state machine and agent transitions.
- **Persistence**: SQLite-based checkpointer (`checkpoints/bus.sqlite`) saves every state transition.
- **Frontend**: Vanilla HTML/JS with a dynamic SVG-based communication graph and real-time state inspector.

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

MIT
