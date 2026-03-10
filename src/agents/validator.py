import json

from src.events import emit
from src.logger import log_message
from src.schema import ACPMessage, BusState, MsgType, Role

MAX_RETRIES = 2


def validator_agent(state: BusState) -> dict:
    items = state.get("action_items", [])
    retry_count = state.get("retry_count", 0)

    print(f"\n[Validator] Validating {len(items)} action items...")
    emit("agent_start", {"agent": "validator", "step": state["step"] + 1,
                         "message": f"Validating {len(items)} action items..."})

    issues: list[str] = []

    for i, item in enumerate(items):
        if not item.get("owner"):
            issues.append(f"Item {i} ('{item.get('description', '')}') is missing an owner.")

    for i, item in enumerate(items):
        if not item.get("deadline"):
            issues.append(f"Item {i} ('{item.get('description', '')}') is missing a deadline.")

    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        desc = item.get("description", "").lower().strip()
        if desc in seen:
            issues.append(
                f"Item {i} is a duplicate of item {seen[desc]}: '{item.get('description', '')}'."
            )
        else:
            seen[desc] = i

    if issues and retry_count < MAX_RETRIES:
        print(f"[Validator] Found {len(issues)} issue(s). Requesting re-extraction (retry {retry_count + 1}/{MAX_RETRIES}).")
        for issue in issues:
            print(f"  - {issue}")

        msg = ACPMessage(
            sender=Role.validator,
            receiver=Role.executor,
            msg_type=MsgType.validation_fail,
            content=json.dumps(issues),
            meta={"issue_count": len(issues), "retry": retry_count + 1},
            trace={"step": state["step"] + 1},
        )
        log_message(msg)

        emit("acp_message", {
            "sender": "validator", "receiver": "executor", "msg_type": "validation_fail",
            "content_preview": f"{len(issues)} issue(s) found — requesting retry {retry_count + 1}/{MAX_RETRIES}",
            "content": msg.content,
            "meta": msg.meta, "step": state["step"] + 1,
        })
        emit("agent_done", {"agent": "validator", "step": state["step"] + 1,
                            "summary": f"{len(issues)} issue(s) found. Retry {retry_count + 1}/{MAX_RETRIES}."})

        return {
            "validation_issues": issues,
            "mailbox": [msg.model_dump()],
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

        msg = ACPMessage(
            sender=Role.validator,
            receiver=Role.user,
            msg_type=MsgType.validation_pass,
            content=json.dumps(items),
            meta={"item_count": len(items), "remaining_issues": len(issues)},
            trace={"step": state["step"] + 1},
        )
        log_message(msg)

        emit("acp_message", {
            "sender": "validator", "receiver": "user", "msg_type": "validation_pass",
            "content_preview": f"{len(items)} items validated and delivered",
            "content": msg.content,
            "meta": msg.meta, "step": state["step"] + 1,
        })
        emit("action_items", {"items": items})
        emit("agent_done", {"agent": "validator", "step": state["step"] + 1,
                            "summary": f"All {len(items)} items validated successfully."})

        return {
            "validation_issues": issues,
            "mailbox": [msg.model_dump()],
            "active_role": "user",
            "step": state["step"] + 1,
            "done": True,
        }
