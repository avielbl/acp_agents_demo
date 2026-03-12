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


def build_graph():
    Path("checkpoints").mkdir(exist_ok=True)

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

    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    
    conn = sqlite3.connect("checkpoints/bus.sqlite", check_same_thread=False)
    
    # Silence msgpack warnings and allow deserialization for our custom types
    # The error message specifically asks for the [('module', 'class')] format
    serde = JsonPlusSerializer(allowed_msgpack_modules=[
        ("src.schema", "Role"),
        ("src.schema", "MsgType"),
        ("src.schema", "ACPMessage"),
        ("src.schema", "ActionItem")
    ])
    checkpointer = SqliteSaver(conn, serde=serde)
    
    app = graph.compile(checkpointer=checkpointer)
    return app
