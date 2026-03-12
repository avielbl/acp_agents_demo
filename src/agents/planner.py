from src.events import emit
from src.llm import generate
from src.logger import log_message
from src.schema import ACPMessage, BusState, MsgType, Role
from src.utils import clean_llm_json


def planner_agent(state: BusState) -> dict:
    """Segments the meeting transcript into distinct discussion topics."""
    transcript = state["goal"]
    
    log_msg = "Segmenting transcript into discussion topics..."
    print(f"\n[Planner] {log_msg}")
    emit("agent_start", {
        "agent": "planner", 
        "step": state["step"] + 1,
        "message": log_msg
    })

    prompt = (
        "You are a meeting analyst. Segment the following meeting transcript into distinct "
        "discussion topics. Return ONLY a JSON array of strings, where each string is a "
        "self-contained segment of the transcript covering one topic. "
        "Do not include any explanation or markdown — just the raw JSON array.\n\n"
        f"Transcript:\n{transcript}"
    )

    raw_response = generate(prompt)
    cleaned_json = clean_llm_json(raw_response)

    try:
        segments = json.loads(cleaned_json)
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
        "content": msg.content,
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
