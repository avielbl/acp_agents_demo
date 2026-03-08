import os
import google.generativeai as genai

_model = None


def get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-2.0-flash")
    return _model


def generate(prompt: str) -> str:
    model = get_model()
    response = model.generate_content(prompt)
    return response.text
