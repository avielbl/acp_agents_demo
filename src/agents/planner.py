import json

from src.events import emit
from src.llm import generate
from src.logger import log_message
from src.schema import ACPMessage, BusState, MsgType, Role


def planner_agent(state: BusState) -> dict:
    transcript = state["goal"]
    print("\n[Planner] Segmenting transcript into discussion topics...")
    emit("agent_start", {"agent": "planner", "step": state["step"] + 1,
                         "message": "Segmenting transcript into discussion topics..."})

    prompt = (
        "You are a meeting analyst. Segment the following meeting transcript into distinct "
        "discussion topics. Return ONLY a JSON array of strings, where each string is a "
        "self-contained segment of the transcript covering one topic. "
        "Do not include any explanation or markdown — just the raw JSON array.\n\n"
        f"Transcript:\n{transcript}"
    )

    raw = generate(prompt)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        segments = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: treat whole transcript as one segment
        segments = [transcript]

    print(f"[Planner] Identified {len(segments)} topic segments.")

    msg = ACPMessage(
        sender=Role.planner,
        receiver=Role.executor,
        msg_type=MsgType.task,
        content=json.dumps(segments),
        meta={"segment_count": len(segments)},
        trace={"step": state["step"] + 1},
    )
    log_message(msg)

    emit("acp_message", {
        "sender": "planner", "receiver": "executor", "msg_type": "task",
        "content_preview": f"{len(segments)} segments dispatched",
        "meta": msg.meta, "step": state["step"] + 1,
    })
    emit("agent_done", {"agent": "planner", "step": state["step"] + 1,
                        "summary": f"Identified {len(segments)} topic segments."})

    return {
        "segments": segments,
        "mailbox": [msg.model_dump()],
        "active_role": "executor",
        "step": state["step"] + 1,
    }
