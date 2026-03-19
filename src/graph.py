import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path

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


def build_graph():
    graph = StateGraph(BusState)
    graph.add_node("planner", planner_agent)
    graph.add_node("executor", executor_agent)
    graph.add_node("validator", validator_agent)

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
