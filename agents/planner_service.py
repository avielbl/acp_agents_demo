import src.patch_acp
"""Planner ACP microservice — segments a meeting transcript into topic chunks."""
import json

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from acp_sdk.models import Message, MessagePart
from acp_sdk.server.agent import agent
from acp_sdk.server.app import create_app

from src.llm import generate
from src.utils import clean_llm_json

PORT = 8001


@agent(name="planner", description="Segments a raw meeting transcript into distinct discussion topics.")
async def planner_agent(input: list[Message]) -> Message:
    transcript = input[0].parts[0].content

    prompt = (
        "You are a meeting analyst. Segment the following meeting transcript into distinct "
        "discussion topics. Return ONLY a JSON array of strings, where each string is a "
        "self-contained segment of the transcript covering one topic. "
        "Do not include any explanation or markdown — just the raw JSON array.\n\n"
        f"Transcript:\n{transcript}"
    )

    raw = generate(prompt)
    cleaned = clean_llm_json(raw)

    try:
        segments = json.loads(cleaned)
    except json.JSONDecodeError:
        segments = [transcript]

    return Message(
        role="agent",
        parts=[MessagePart(content_type="application/json", content=json.dumps(segments))],
    )


if __name__ == "__main__":
    app = create_app(planner_agent)
    uvicorn.run(app, host="127.0.0.1", port=PORT)
