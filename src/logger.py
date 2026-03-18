from datetime import datetime, timezone
from pathlib import Path

from acp_sdk.models import Message

_log_file = None


def _get_log_file():
    global _log_file
    if _log_file is None:
        Path("logs").mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        _log_file = open(f"logs/acp_{ts}.jsonl", "a", encoding="utf-8")
    return _log_file


def log_message(msg: Message) -> None:
    f = _get_log_file()
    f.write(msg.model_dump_json() + "\n")
    f.flush()


def get_log_path() -> str:
    f = _get_log_file()
    return f.name
