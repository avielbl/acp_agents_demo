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
            initial_state = {
                "goal": req.transcript,
                "done": False,
                "mailbox": [],
                "active_role": "planner",
                "step": 0,
                "segments": [],
                "action_items": [],
                "validation_issues": [],
                "retry_count": 0,
            }
            graph_app = build_graph()
            config = {"configurable": {"thread_id": run_id}}
            final_state = graph_app.invoke(initial_state, config=config)
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
