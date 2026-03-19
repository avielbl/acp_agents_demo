import src.patch_acp
"""Executor ACP microservice — extracts action items from transcript segments."""
import json

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from acp_sdk.models import Message, MessagePart
from acp_sdk.server.agent import agent
from acp_sdk.server.app import create_app

from src.llm import generate
from src.utils import clean_llm_json

PORT = 8002


@agent(name="executor", description="Extracts action items from a list of transcript segments.")
async def executor_agent(input: list[Message]) -> Message:
    payload = json.loads(input[0].parts[0].content)
    segments: list[str] = payload["segments"]
    issues: list[str] = payload.get("validation_issues", [])

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
        cleaned = clean_llm_json(raw)

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError:
            items = []

        for item in items:
            item["segment_id"] = idx
        all_items.extend(items)

    return Message(
        role="agent",
        parts=[MessagePart(content_type="application/json", content=json.dumps(all_items))],
    )


if __name__ == "__main__":
    app = create_app(executor_agent)
    uvicorn.run(app, host="127.0.0.1", port=PORT)
