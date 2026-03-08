import json

from src.llm import generate
from src.logger import log_message
from src.schema import ACPMessage, BusState, MsgType, Role


def planner_agent(state: BusState) -> dict:
    transcript = state["goal"]
    print("\n[Planner] Segmenting transcript into discussion topics...")

    prompt = (
        "You are a meeting analyst. Segment the following meeting transcript into distinct "
        "discussion topics. Return ONLY a JSON array of strings, where each string is a "
        "self-contained segment of the transcript covering one topic. "
        "Do not include any explanation or markdown — just the raw JSON array.\n\n"
        f"Transcript:\n{transcript}"
    )

    raw = generate(prompt)

    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    segments = json.loads(cleaned)
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

    return {
        "segments": segments,
        "mailbox": [msg.model_dump()],
        "active_role": "executor",
        "step": state["step"] + 1,
    }
