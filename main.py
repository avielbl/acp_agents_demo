#!/usr/bin/env python3
"""
ACP Multi-Agent Demo: Meeting Transcript → Action Item Tracker
Usage: python main.py [--transcript data/sample_transcript.txt] [--thread-id <uuid>]
"""
import argparse
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.graph import build_graph
from src.logger import get_log_path


def print_table(action_items: list[dict]) -> None:
    if not action_items:
        print("\nNo action items found.")
        return

    print("\n" + "=" * 80)
    print("FINAL ACTION ITEMS")
    print("=" * 80)

    col_desc = 38
    col_owner = 18
    col_deadline = 16
    col_seg = 5

    header = (
        f"{'#':<3}  "
        f"{'Description':<{col_desc}}  "
        f"{'Owner':<{col_owner}}  "
        f"{'Deadline':<{col_deadline}}  "
        f"{'Seg':>{col_seg}}"
    )
    print(header)
    print("-" * 80)

    for i, item in enumerate(action_items, 1):
        desc = str(item.get("description", ""))[:col_desc]
        owner = str(item.get("owner") or "—")[:col_owner]
        deadline = str(item.get("deadline") or "—")[:col_deadline]
        seg = str(item.get("segment_id", "?"))
        print(
            f"{i:<3}  "
            f"{desc:<{col_desc}}  "
            f"{owner:<{col_owner}}  "
            f"{deadline:<{col_deadline}}  "
            f"{seg:>{col_seg}}"
        )

    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="Meeting Transcript → Action Item Tracker")
    parser.add_argument(
        "--transcript",
        default="data/sample_transcript.txt",
        help="Path to the meeting transcript file",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="LangGraph thread ID for checkpointing (default: random UUID)",
    )
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"Error: transcript file not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)

    transcript = transcript_path.read_text(encoding="utf-8")
    thread_id = args.thread_id or str(uuid.uuid4())

    print(f"Thread ID : {thread_id}")
    print(f"Transcript: {transcript_path} ({len(transcript)} chars)")

    from src.schema import create_initial_state
    initial_state = create_initial_state(transcript)

    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}

    print("\nStarting multi-agent pipeline...\n")
    final_state = app.invoke(initial_state, config=config)

    print_table(final_state.get("action_items", []))

    log_path = get_log_path()
    print(f"\nAudit log : {log_path}")
    print(f"Checkpoint: checkpoints/bus.sqlite")
    print(f"Messages  : {len(final_state.get('mailbox', []))} total ACP messages exchanged\n")


if __name__ == "__main__":
    main()
