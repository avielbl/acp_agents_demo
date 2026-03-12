import json

def clean_llm_json(raw: str) -> str:
    """
    Strips markdown code blocks from LLM responses and returns the raw JSON string.
    If no code blocks are found, returns the stripped input string.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first line (```json or ```)
        # Remove last line if it's just closing ```
        if lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = "\n".join(lines[1:])
    return cleaned.strip()
