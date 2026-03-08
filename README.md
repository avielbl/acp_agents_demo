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
┌────────────┐    task msg     ┌──────────────┐    result msg    ┌─────────────┐
│   Planner  │ ─────────────► │   Executor   │ ───────────────► │  Validator  │
│            │                │              │                  │             │
│ Segments   │                │ Extracts     │  ◄─────────────  │ Validates   │
│ transcript │                │ action items │  validation_fail  │ completeness│
│ by topic   │                │ per segment  │                  │ & quality   │
└────────────┘                └──────────────┘                  └─────────────┘
       │                             ▲                                  │
       │                             │      retry (up to 2x)            │
       │                             └──────────────────────────────────┘
       │
       ▼
  Shared BusState (LangGraph StateGraph)
       │
       ├── mailbox[]      append-only list of all ACPMessages
       ├── segments[]     transcript chunks from Planner
       ├── action_items[] structured items from Executor
       └── validation_issues[] feedback from Validator
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
│   └── agents/
│       ├── planner.py          # Segment transcript into topics
│       ├── executor.py         # Extract action items per segment
│       └── validator.py        # Validate completeness, flag issues
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

### 3. Run with the sample transcript

```bash
python main.py
```

### 4. Run with your own transcript

```bash
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

## Runtime Artifacts

| Path | Description |
|---|---|
| `logs/acp_<ts>.jsonl` | One JSON line per `ACPMessage` — full audit trail |
| `checkpoints/bus.sqlite` | LangGraph SQLite checkpoint — enables run resumption |

Both are git-ignored. Inspect the log with:
```bash
cat logs/acp_*.jsonl | python -m json.tool --no-ensure-ascii | less
```

---

## Key Design Patterns

### 1. Append-only Mailbox (reducer)
`BusState.mailbox` uses `Annotated[List[dict], operator.add]` — LangGraph's reducer pattern ensures messages are appended, never overwritten, even across retries.

### 2. Conditional Routing
After the Validator node, `route_after_validator()` inspects `state["done"]` and routes back to Executor or exits to `END`. This is LangGraph's `add_conditional_edges` in action.

### 3. Feedback-Driven Re-extraction
Validation issues are injected directly into the Executor's next prompt, giving the LLM precise, actionable feedback rather than starting from scratch.

### 4. Stateless Agents
Each agent function is a pure `(state) -> dict` — it reads from state and returns only the fields it modifies. LangGraph merges the deltas.

---

## Dependencies

| Package | Purpose |
|---|---|
| `langgraph` | StateGraph, checkpointing, conditional routing |
| `langchain-core` | Base abstractions used by LangGraph |
| `google-generativeai` | Gemini 2.0 Flash LLM client |
| `pydantic` | `ACPMessage` and `ActionItem` validation |
| `python-dotenv` | `.env` file loading |

---

## License

MIT
