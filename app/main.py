from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import uuid

from .engine import GRAPHS, RUNS, register_node, run_graph
from .workflows import split_text, summarize_chunks, merge_summaries, refine_summary, measure_length
from .database import save_graph, load_all_graphs
from fastapi import WebSocket, WebSocketDisconnect
from .logger import workflow_logger
from .ws_manager import WS_CONNECTIONS


app = FastAPI(title="Summarization Workflow Engine")
# Dictionary: run_id -> list of active websocket connections


register_node("split", split_text)
register_node("summarize", summarize_chunks)
register_node("merge", merge_summaries)
register_node("refine", refine_summary)
register_node("measure", measure_length)

@app.on_event("startup")
def load_graphs_on_startup():
    """
    Load graphs persisted in the DB into the engine's in-memory GRAPHS dict.
    This runs once when FastAPI/uvicorn starts.
    """
    try:
        persisted = load_all_graphs()
        if not persisted:
            workflow_logger.info({"event": "startup", "message": "No persisted graphs found"})
            print("Loaded 0 persisted graphs")
            return

        # Populate in-memory graphs
        GRAPHS.update(persisted)
        count = len(persisted)
        workflow_logger.info({"event": "startup", "message": f"Loaded {count} graphs from DB"})
        print(f"Loaded {count} graphs from DB into memory")
    except Exception as e:
        workflow_logger.error({"event": "startup_error", "error": str(e)})
        print(f"[startup] error loading graphs: {e}")


class GraphCreate(BaseModel):
    name: str
    nodes: Dict[str, Any]
    edges: Dict[str, Any]
    entry: str

class RunCreate(BaseModel):
    graph_id: str
    initial_state: Dict[str, Any]

@app.post("/graph/create")
def create_graph(g: GraphCreate):
    graph_id = str(uuid.uuid4())
    graph_data = {"name": g.name, "nodes": g.nodes, "edges": g.edges, "entry": g.entry}

    # Save in memory
    GRAPHS[graph_id] = graph_data

    # Save to SQLite DB
    save_graph(graph_id, graph_data)

    return {"graph_id": graph_id}


@app.post("/graph/run")
def run_graph_endpoint(payload: RunCreate, background_tasks: BackgroundTasks):
    if payload.graph_id not in GRAPHS:
        raise HTTPException(status_code=404, detail="Graph not found")
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_graph, payload.graph_id, payload.initial_state, run_id)
    return {"run_id": run_id}

@app.get("/graph/state/{run_id}")
def get_state(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await websocket.accept()

    # Register this websocket for the given run_id
    WS_CONNECTIONS.setdefault(run_id, []).append(websocket)

    try:
        while True:
            # Keep the connection alive by waiting for any message
            await websocket.receive_text()
    except WebSocketDisconnect:
        # On disconnect remove websocket
        WS_CONNECTIONS[run_id].remove(websocket)

