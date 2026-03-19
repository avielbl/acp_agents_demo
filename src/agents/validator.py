import src.patch_acp
import json

import httpx
from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart

from src.events import emit
from src.logger import log_message
from src.schema import BusState

MAX_RETRIES = 2
VALIDATOR_URL = "http://127.0.0.1:8003"


async def validator_agent(state: BusState) -> dict:
    """Calls the Validator ACP microservice to check action item completeness."""
    items = state.get("action_items", [])
    retry_count = state.get("retry_count", 0)

    log_msg = f"Validating {len(items)} action items..."
    print(f"\n[Validator] {log_msg}")
    emit("agent_start", {
        "agent": "validator",
        "step": state["step"] + 1,
        "message": log_msg,
    })

    async with Client(base_url=VALIDATOR_URL) as client:
        try:
            run = await client.run_sync(
                Message(
                    role="user",
                    parts=[MessagePart(content_type="application/json", content=json.dumps(items))],
                ),
                agent="validator",
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach the Validator microservice at {VALIDATOR_URL}. "
                "Run 'python start_agents.py' first."
            )

    result = json.loads(run.output[0].parts[0].content)
    passed: bool = result["passed"]
    issues: list[str] = result["issues"]

    if issues and retry_count < MAX_RETRIES:
        print(f"[Validator] Found {len(issues)} issue(s). Requesting re-extraction (retry {retry_count + 1}/{MAX_RETRIES}).")
        for issue in issues:
            print(f"  - {issue}")

        msg = Message(
            role="agent",
            parts=[
                MessagePart(
                    name="routing",
                    content_type="application/json",
                    content=json.dumps({
                        "sender": "validator",
                        "receiver": "executor",
                        "msg_type": "validation_fail",
                        "meta": {"issue_count": len(issues), "retry": retry_count + 1},
                        "step": state["step"] + 1,
                    }),
                ),
                MessagePart(
                    name="payload",
                    content_type="application/json",
                    content=json.dumps(issues),
                ),
            ],
        )
        log_message(msg)

        emit("acp_message", {
            "sender": "validator",
            "receiver": "executor",
            "msg_type": "validation_fail",
            "content_preview": f"{len(issues)} issue(s) found — requesting retry {retry_count + 1}/{MAX_RETRIES}",
            "content": json.dumps(issues),
            "meta": {"issue_count": len(issues), "retry": retry_count + 1},
            "step": state["step"] + 1,
        })
        emit("agent_done", {
            "agent": "validator",
            "step": state["step"] + 1,
            "summary": f"{len(issues)} issue(s) found. Retry {retry_count + 1}/{MAX_RETRIES}.",
        })

        return {
            "validation_issues": issues,
            "mailbox": [json.loads(msg.model_dump_json())],
            "active_role": "executor",
            "step": state["step"] + 1,
            "retry_count": retry_count + 1,
            "done": False,
        }
    else:
        if issues:
            print(f"[Validator] Max retries reached. Accepting {len(items)} items with {len(issues)} remaining issue(s).")
        else:
            print(f"[Validator] All {len(items)} action items passed validation.")

        msg = Message(
            role="agent",
            parts=[
                MessagePart(
                    name="routing",
                    content_type="application/json",
                    content=json.dumps({
                        "sender": "validator",
                        "receiver": "user",
                        "msg_type": "validation_pass",
                        "meta": {"item_count": len(items), "remaining_issues": len(issues)},
                        "step": state["step"] + 1,
                    }),
                ),
                MessagePart(
                    name="payload",
                    content_type="application/json",
                    content=json.dumps(items),
                ),
            ],
        )
        log_message(msg)

        emit("acp_message", {
            "sender": "validator",
            "receiver": "user",
            "msg_type": "validation_pass",
            "content_preview": f"{len(items)} items validated and delivered",
            "content": json.dumps(items),
            "meta": {"item_count": len(items), "remaining_issues": len(issues)},
            "step": state["step"] + 1,
        })
        emit("action_items", {"items": items})
        emit("agent_done", {
            "agent": "validator",
            "step": state["step"] + 1,
            "summary": f"All {len(items)} items validated successfully.",
        })

        return {
            "validation_issues": issues,
            "mailbox": [json.loads(msg.model_dump_json())],
            "active_role": "user",
            "step": state["step"] + 1,
            "done": True,
        }
