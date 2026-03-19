import src.patch_acp
"""Validator ACP microservice — validates extracted action items."""
import json

import uvicorn

from acp_sdk.models import Message, MessagePart
from acp_sdk.server.agent import agent
from acp_sdk.server.app import create_app

PORT = 8003


@agent(name="validator", description="Validates action items for completeness and uniqueness.")
async def validator_agent(input: list[Message]) -> Message:
    items: list[dict] = json.loads(input[0].parts[0].content)
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

    result = {"passed": len(issues) == 0, "issues": issues}

    return Message(
        role="agent",
        parts=[MessagePart(content_type="application/json", content=json.dumps(result))],
    )


if __name__ == "__main__":
    app = create_app(validator_agent)
    uvicorn.run(app, host="127.0.0.1", port=PORT)
