import os
from google import genai
import traceback

_client = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable not set")
        _client = genai.Client(api_key=api_key)
    return _client


def generate(prompt: str) -> str:
    print(f"[LLM] Generating content for prompt length: {len(prompt)}")
    try:
        client = get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        print("[LLM] Generation successful")
        return response.text
    except Exception as e:
        print(f"[LLM] Generation failed ERROR:\n{e}")
        traceback.print_exc()
        raise
