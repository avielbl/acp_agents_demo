import src.patch_acp
import json

import httpx
from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart

from src.events import emit
from src.logger import log_message
from src.schema import BusState


PLANNER_URL = "http://127.0.0.1:8001"


async def planner_agent(state: BusState) -> dict:
    """Calls the Planner ACP microservice to segment the transcript."""
    transcript = state["goal"]

    log_msg = "Segmenting transcript into discussion topics..."
    print(f"\n[Planner] {log_msg}")
    emit("agent_start", {
        "agent": "planner",
        "step": state["step"] + 1,
        "message": log_msg,
    })

    async with Client(base_url=PLANNER_URL) as client:
        try:
            run = await client.run_sync(
                Message(
                    role="user",
                    parts=[MessagePart(content_type="text/plain", content=transcript)],
                ),
                agent="planner",
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach the Planner microservice at {PLANNER_URL}. "
                "Run 'python start_agents.py' first."
            )

    result_content = run.output[0].parts[0].content
    try:
        segments = json.loads(result_content)
    except json.JSONDecodeError:
        segments = [transcript]

    print(f"[Planner] Identified {len(segments)} topic segments.")

    msg = Message(
        role="agent",
        parts=[
            MessagePart(
                name="routing",
                content_type="application/json",
                content=json.dumps({
                    "sender": "planner",
                    "receiver": "executor",
                    "msg_type": "task",
                    "meta": {"segment_count": len(segments)},
                    "step": state["step"] + 1,
                }),
            ),
            MessagePart(
                name="payload",
                content_type="application/json",
                content=json.dumps(segments),
            ),
        ],
    )
    log_message(msg)

    emit("acp_message", {
        "sender": "planner",
        "receiver": "executor",
        "msg_type": "task",
        "content_preview": f"{len(segments)} segments dispatched",
        "content": json.dumps(segments),
        "meta": {"segment_count": len(segments)},
        "step": state["step"] + 1,
    })
    emit("agent_done", {
        "agent": "planner",
        "step": state["step"] + 1,
        "summary": f"Identified {len(segments)} topic segments.",
    })

    return {
        "segments": segments,
        "mailbox": [json.loads(msg.model_dump_json())],
        "active_role": "executor",
        "step": state["step"] + 1,
    }
