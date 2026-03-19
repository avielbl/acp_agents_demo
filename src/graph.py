import asyncio
import sqlite3
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.schema import BusState
from src.agents.planner import planner_agent
from src.agents.executor import executor_agent
from src.agents.validator import validator_agent


def route_after_validator(state: BusState) -> str:
    if state.get("done"):
        return END
    return "executor"


_shared_conn = None
_shared_checkpointer = None


def get_checkpointer():
    global _shared_conn, _shared_checkpointer
    if _shared_checkpointer is None:
        Path("checkpoints").mkdir(exist_ok=True)
        _shared_conn = sqlite3.connect("checkpoints/bus.sqlite", check_same_thread=False)
        _shared_checkpointer = SqliteSaver(_shared_conn)
    return _shared_checkpointer


def close_db():
    global _shared_conn, _shared_checkpointer
    if _shared_conn:
        try:
            _shared_conn.close()
        except Exception:
            pass
        _shared_conn = None
        _shared_checkpointer = None


def _wrap_async(async_fn):
    """Wrap an async agent function so LangGraph can call it synchronously."""
    def sync_wrapper(state: BusState) -> dict:
        return asyncio.run(async_fn(state))
    sync_wrapper.__name__ = async_fn.__name__
    return sync_wrapper


def build_graph():
    graph = StateGraph(BusState)
    graph.add_node("planner", _wrap_async(planner_agent))
    graph.add_node("executor", _wrap_async(executor_agent))
    graph.add_node("validator", _wrap_async(validator_agent))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {END: END, "executor": "executor"},
    )

    checkpointer = get_checkpointer()
    app = graph.compile(checkpointer=checkpointer)
    return app
