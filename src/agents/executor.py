import src.patch_acp
import json

import httpx
from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart

from src.events import emit
from src.logger import log_message
from src.schema import BusState

EXECUTOR_URL = "http://127.0.0.1:8002"


async def executor_agent(state: BusState) -> dict:
    """Calls the Executor ACP microservice to extract action items from segments."""
    segments = state["segments"]
    issues = state.get("validation_issues", [])
    retry = state.get("retry_count", 0)

    if issues:
        log_msg = f"Re-extracting action items (retry {retry}/{2}). Fixing {len(issues)} issue(s)."
    else:
        log_msg = f"Extracting action items from {len(segments)} segment(s)..."

    print(f"\n[Executor] {log_msg}")
    emit("agent_start", {
        "agent": "executor",
        "step": state["step"] + 1,
        "retry": retry,
        "message": log_msg,
    })

    payload = json.dumps({"segments": segments, "validation_issues": issues})

    async with Client(base_url=EXECUTOR_URL) as client:
        try:
            run = await client.run_sync(
                Message(
                    role="user",
                    parts=[MessagePart(content_type="application/json", content=payload)],
                ),
                agent="executor",
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach the Executor microservice at {EXECUTOR_URL}. "
                "Run 'python start_agents.py' first."
            )

    result_content = run.output[0].parts[0].content
    try:
        all_items = json.loads(result_content)
    except json.JSONDecodeError:
        all_items = []

    print(f"[Executor] Extracted {len(all_items)} action items total.")

    msg = Message(
        role="agent",
        parts=[
            MessagePart(
                name="routing",
                content_type="application/json",
                content=json.dumps({
                    "sender": "executor",
                    "receiver": "validator",
                    "msg_type": "result",
                    "meta": {"item_count": len(all_items), "retry": retry},
                    "step": state["step"] + 1,
                }),
            ),
            MessagePart(
                name="payload",
                content_type="application/json",
                content=json.dumps(all_items),
            ),
        ],
    )
    log_message(msg)

    emit("acp_message", {
        "sender": "executor",
        "receiver": "validator",
        "msg_type": "result",
        "content_preview": f"{len(all_items)} action items extracted",
        "content": json.dumps(all_items),
        "meta": {"item_count": len(all_items), "retry": retry},
        "step": state["step"] + 1,
    })
    emit("agent_done", {
        "agent": "executor",
        "step": state["step"] + 1,
        "summary": f"Extracted {len(all_items)} action items.",
    })

    return {
        "action_items": all_items,
        "mailbox": [json.loads(msg.model_dump_json())],
        "active_role": "validator",
        "step": state["step"] + 1,
    }
