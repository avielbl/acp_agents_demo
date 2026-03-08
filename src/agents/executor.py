import json

from src.llm import generate
from src.logger import log_message
from src.schema import ACPMessage, BusState, MsgType, Role


def executor_agent(state: BusState) -> dict:
    segments = state["segments"]
    issues = state.get("validation_issues", [])
    retry = state.get("retry_count", 0)

    if issues:
        print(f"\n[Executor] Re-extracting action items (retry {retry}). Issues to fix: {issues}")
    else:
        print("\n[Executor] Extracting action items from each segment...")

    issues_str = "\n".join(f"- {i}" for i in issues) if issues else "None"
    all_items: list[dict] = []

    for idx, segment in enumerate(segments):
        prompt = (
            "Extract all action items from the following meeting transcript segment. "
            "Return ONLY a JSON array of objects with keys: "
            '"description" (string), "owner" (string or null), "deadline" (string or null). '
            "Every action item MUST have a non-null, non-empty owner and deadline. "
            "Do not include any explanation or markdown — just the raw JSON array.\n\n"
            f"Previous validation issues to fix (if any):\n{issues_str}\n\n"
            f"Segment:\n{segment}"
        )

        raw = generate(prompt)

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        items = json.loads(cleaned)
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

    return {
        "action_items": all_items,
        "mailbox": [msg.model_dump()],
        "active_role": "validator",
        "step": state["step"] + 1,
    }
