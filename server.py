"""FastAPI server for ACP Multi-Agent Demo UI."""
from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.events import make_threadsafe_emitter, set_emitter
from src.graph import build_graph

app = FastAPI(title="ACP Agents Demo")

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# run_id → asyncio.Queue of SSE strings (None = end-of-stream sentinel)
active_runs: dict[str, asyncio.Queue] = {}
_executor = ThreadPoolExecutor(max_workers=4)


class RunRequest(BaseModel):
    transcript: str


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/sample-transcript")
async def sample_transcript() -> PlainTextResponse:
    p = Path("data/sample_transcript.txt")
    if not p.exists():
        raise HTTPException(status_code=404, detail="Sample transcript not found")
    return PlainTextResponse(p.read_text(encoding="utf-8"))


@app.get("/history/latest")
async def get_latest_history() -> dict:
    import sqlite3
    db_path = Path("checkpoints/bus.sqlite")
    if not db_path.exists():
        return {"thread_id": None}
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # Find the thread with the most recent activity
        cursor.execute("SELECT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 1")
        res = cursor.fetchone()
        conn.close()
        return {"thread_id": res[0] if res else None}
    except Exception:
        return {"thread_id": None}


@app.get("/history/steps/{thread_id}")
async def get_history_steps(thread_id: str) -> dict:
    try:
        graph_app = build_graph()
        config = {"configurable": {"thread_id": thread_id}}
        history = list(graph_app.get_state_history(config))
        
        steps = []
        for snapshot in reversed(history): # Walk forward in time
            # snapshot.values is the BusState
            # snapshot.metadata['source'] often indicates node
            steps.append({
                "state": snapshot.values,
                "next": snapshot.next,
                "metadata": snapshot.metadata
            })
        return {"steps": steps}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear-db")
async def clear_database() -> dict:
    db_path = Path("checkpoints/bus.sqlite")
    if db_path.exists():
        try:
            # Close any connections if possible (though sqlite handles deletions okay usually)
            db_path.unlink()
            return {"status": "success", "message": "Database cleared"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear DB: {e}")
    return {"status": "success", "message": "Database already clean"}


@app.get("/debug/db")
async def debug_db() -> dict:
    import sqlite3
    db_path = Path("checkpoints/bus.sqlite")
    if not db_path.exists():
        return {"error": "Database not found", "tables": {}}
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        
        data = {}
        for table in tables:
            cursor.execute(f"SELECT * FROM {table} LIMIT 100")
            rows = cursor.fetchall()
            fixed_rows = []
            for row in rows:
                d = dict(row)
                # Convert bytes to hex strings for JSON serialization
                for k, v in d.items():
                    if isinstance(v, bytes):
                        d[k] = f"<binary:{v.hex()[:64]}...>" if len(v) > 32 else v.hex()
                fixed_rows.append(d)
            data[table] = fixed_rows
            
        conn.close()
        return {"tables": data}
    except Exception as e:
        return {"error": str(e), "tables": {}}


@app.post("/run")
async def start_run(req: RunRequest) -> dict:
    run_id = str(uuid.uuid4())
    q: asyncio.Queue = asyncio.Queue()
    active_runs[run_id] = q
    loop = asyncio.get_running_loop()

    def _run_pipeline() -> None:
        emit = make_threadsafe_emitter(run_id, q, loop)
        set_emitter(emit)
        try:
            from src.schema import create_initial_state
            initial_state = create_initial_state(req.transcript)
            graph_app = build_graph()
            config = {"configurable": {"thread_id": run_id}}
            
            # Stream the execution to capture intermediate states
            for event in graph_app.stream(initial_state, config=config, stream_mode="values"):
                # Emit full state as a 'state_update' event
                emit("state_update", {"state": event})
            
            # Final state check
            final_snapshot = graph_app.get_state(config)
            final_state = final_snapshot.values
            
            emit("done", {
                "step_count": final_state.get("step", 0),
                "item_count": len(final_state.get("action_items", [])),
            })
        except Exception as exc:
            import traceback
            traceback.print_exc()
            emit("error", {"message": str(exc)})
        finally:
            asyncio.run_coroutine_threadsafe(q.put(None), loop)

    _executor.submit(_run_pipeline)
    return {"run_id": run_id}


@app.get("/stream/{run_id}")
async def stream_events(run_id: str) -> StreamingResponse:
    q = active_runs.get(run_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        try:
            while True:
                item = await asyncio.wait_for(q.get(), timeout=300.0)
                if item is None:
                    break
                yield item
        except asyncio.TimeoutError:
            yield f"event: error\ndata: {json.dumps({'message': 'Pipeline timed out after 5 minutes'})}\n\n"
        finally:
            active_runs.pop(run_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
