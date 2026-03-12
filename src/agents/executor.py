from src.events import emit
from src.llm import generate
from src.logger import log_message
from src.schema import ACPMessage, BusState, MsgType, Role
from src.utils import clean_llm_json


def executor_agent(state: BusState) -> dict:
    """Extracts action items from transcript segments."""
    segments = state["segments"]
    issues = state.get("validation_issues", [])
    retry = state.get("retry_count", 0)

    if issues:
        log_msg = f"Re-extracting action items (retry {retry}/{2}). Fixing {len(issues)} issue(s)."
        print(f"\n[Executor] {log_msg}")
        emit("agent_start", {
            "agent": "executor", 
            "step": state["step"] + 1, 
            "retry": retry,
            "message": log_msg
        })
    else:
        log_msg = f"Extracting action items from {len(segments)} segment(s)..."
        print(f"\n[Executor] {log_msg}")
        emit("agent_start", {
            "agent": "executor", 
            "step": state["step"] + 1, 
            "retry": 0,
            "message": log_msg
        })

    issues_str = "\n".join(f"- {i}" for i in issues) if issues else "None"
    all_items: list[dict] = []

    for idx, segment in enumerate(segments):
        emit("progress", {
            "agent": "executor", 
            "current": idx + 1, 
            "total": len(segments),
            "message": f"Processing segment {idx + 1} of {len(segments)}..."
        })

        prompt = (
            "Extract all action items from the following meeting transcript segment. "
            "Return ONLY a JSON array of objects with keys: "
            '"description" (string), "owner" (string or null), "deadline" (string or null). '
            "Every action item MUST have a non-null, non-empty owner and deadline. "
            "Do not include any explanation or markdown — just the raw JSON array.\n\n"
            f"Previous validation issues to fix (if any):\n{issues_str}\n\n"
            f"Segment:\n{segment}"
        )

        raw_response = generate(prompt)
        cleaned_json = clean_llm_json(raw_response)

        try:
            items = json.loads(cleaned_json)
        except json.JSONDecodeError:
            items = []

        for item in items:
            item["segment_id"] = idx
        all_items.extend(items)

    print(f"[Executor] Extracted {len(all_items)} action items total.")

    msg = ACPMessage(
        sender=Role.executor,
        receiver=Role.validator,
        msg_type=MsgType.result,
        content=json.dumps(all_items),
        meta={"item_count": len(all_items), "retry": retry},
        trace={"step": state["step"] + 1},
    )
    log_message(msg)

    emit("acp_message", {
        "sender": "executor", "receiver": "validator", "msg_type": "result",
        "content_preview": f"{len(all_items)} action items extracted",
        "content": msg.content,
        "meta": msg.meta, "step": state["step"] + 1,
    })
    emit("agent_done", {"agent": "executor", "step": state["step"] + 1,
                        "summary": f"Extracted {len(all_items)} action items."})

    return {
        "action_items": all_items,
        "mailbox": [msg.model_dump()],
        "active_role": "validator",
        "step": state["step"] + 1,
    }
