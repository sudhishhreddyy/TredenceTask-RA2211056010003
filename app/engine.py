import uuid
import asyncio
from typing import Dict, Any, Callable, Optional
from asteval import Interpreter
from .database import save_graph, save_run
from .logger import workflow_logger
from .ws_manager import WS_CONNECTIONS
import json

# -------------------------
# Broadcast helper
# -------------------------
async def broadcast_event(run_id: str, event: dict):
    """Send event to all live websocket clients of this run."""
    connections = WS_CONNECTIONS.get(run_id, [])
    dead = []

    for ws in list(connections):
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            # Mark closed connections for removal
            dead.append(ws)

    # Remove bad connections
    for ws in dead:
        if ws in connections:
            connections.remove(ws)

# In-memory stores
GRAPHS: Dict[str, Dict] = {}
RUNS: Dict[str, Dict] = {}

# Registries
NODE_REGISTRY: Dict[str, Callable] = {}
TOOL_REGISTRY: Dict[str, Callable] = {}

def register_node(name: str, fn: Callable):
    NODE_REGISTRY[name] = fn

def register_tool(name: str, fn: Callable):
    TOOL_REGISTRY[name] = fn

async def _maybe_await(v):
    if asyncio.iscoroutine(v):
        return await v
    return v

# Safe evaluator
_ASTEVAL = Interpreter(minimal=True)

def _eval_condition(expr: str, state: Dict[str, Any]) -> bool:
    """
    Safely evaluate condition expressions like:
        state.get('summary_length', 0) < state.get('limit', 100)
    """
    try:
        _ASTEVAL.symtable["state"] = state
        _ASTEVAL.symtable["tools"] = TOOL_REGISTRY

        result = _ASTEVAL(expr)

        # Clean up symbol table after evaluation
        _ASTEVAL.symtable.pop("state", None)
        _ASTEVAL.symtable.pop("tools", None)

        return bool(result)
    except Exception:
        _ASTEVAL.symtable.pop("state", None)
        _ASTEVAL.symtable.pop("tools", None)
        return False

async def run_graph(graph_id: str, initial_state: Dict[str, Any], run_id: Optional[str] = None):
    if graph_id not in GRAPHS:
        raise KeyError("Graph not found")

    run_id = run_id or str(uuid.uuid4())
    graph = GRAPHS[graph_id]
    state = dict(initial_state)

    # initialize run in memory
    RUNS[run_id] = {"state": state, "log": [], "status": "running", "current": graph["entry"]}

    # log run started
    workflow_logger.info({
        "event": "run_started",
        "run_id": run_id,
        "graph_id": graph_id,
        "initial_state": state
    })

    # broadcast run started (safe)
    try:
        await broadcast_event(run_id, {
            "event": "run_started",
            "run_id": run_id,
            "graph_id": graph_id,
            "initial_state": state
        })
    except Exception:
        workflow_logger.error({"event": "broadcast_failed", "stage": "run_started", "run_id": run_id})

    # persist initial run record to DB
    try:
        save_run(run_id, graph_id, state, RUNS[run_id]["status"], RUNS[run_id]["log"])
    except Exception:
        # non-fatal: continue even if DB save fails
        workflow_logger.error({
            "event": "db_save_failed",
            "run_id": run_id,
            "stage": "init_save"
        })

    current = graph["entry"]
    steps = 0

    while current is not None and steps < 500:
        steps += 1

        RUNS[run_id]["current"] = current
        RUNS[run_id]["log"].append({"step": steps, "node": current, "event": "start"})

        # log node start
        workflow_logger.info({
            "event": "node_start",
            "run_id": run_id,
            "node": current,
            "step": steps,
            "state_snapshot": state.copy()
        })

        # broadcast node start
        try:
            await broadcast_event(run_id, {
                "event": "node_start",
                "run_id": run_id,
                "node": current,
                "step": steps,
                "state": state.copy()
            })
        except Exception:
            workflow_logger.error({"event": "broadcast_failed", "stage": "node_start", "run_id": run_id, "node": current})

        # persist after start event
        try:
            save_run(run_id, graph_id, state, RUNS[run_id]["status"], RUNS[run_id]["log"])
        except Exception:
            workflow_logger.error({
                "event": "db_save_failed",
                "run_id": run_id,
                "stage": "after_start",
                "node": current
            })

        # Execute node
        fn = NODE_REGISTRY.get(current)
        if fn is None:
            RUNS[run_id]["log"].append({"step": steps, "node": current, "event": "missing_node"})
            # log missing node
            workflow_logger.error({
                "event": "missing_node",
                "run_id": run_id,
                "node": current,
                "step": steps,
                "message": "Node not registered"
            })

            # broadcast missing node
            try:
                await broadcast_event(run_id, {
                    "event": "missing_node",
                    "run_id": run_id,
                    "node": current,
                    "step": steps,
                    "message": "Node not registered"
                })
            except Exception:
                workflow_logger.error({"event": "broadcast_failed", "stage": "missing_node", "run_id": run_id, "node": current})

            # persist missing_node event
            try:
                save_run(run_id, graph_id, state, RUNS[run_id]["status"], RUNS[run_id]["log"])
            except Exception:
                workflow_logger.error({
                    "event": "db_save_failed",
                    "run_id": run_id,
                    "stage": "missing_node"
                })
            break

        try:
            result = fn(state, tools=TOOL_REGISTRY)
            result = await _maybe_await(result)
            if isinstance(result, dict):
                state.update(result)
        except Exception as e:
            # Log node execution error and persist
            workflow_logger.exception({
                "event": "node_exception",
                "run_id": run_id,
                "node": current,
                "step": steps,
                "error": str(e)
            })
            RUNS[run_id]["log"].append({"step": steps, "node": current, "event": "error", "error": str(e)})

            # broadcast exception
            try:
                await broadcast_event(run_id, {
                    "event": "node_exception",
                    "run_id": run_id,
                    "node": current,
                    "step": steps,
                    "error": str(e)
                })
            except Exception:
                workflow_logger.error({"event": "broadcast_failed", "stage": "node_exception", "run_id": run_id})

            try:
                save_run(run_id, graph_id, state, RUNS[run_id]["status"], RUNS[run_id]["log"])
            except Exception:
                workflow_logger.error({
                    "event": "db_save_failed",
                    "run_id": run_id,
                    "stage": "on_exception"
                })
            break

        RUNS[run_id]["log"].append({"step": steps, "node": current, "event": "end", "state": dict(state)})

        # log node end
        workflow_logger.info({
            "event": "node_end",
            "run_id": run_id,
            "node": current,
            "step": steps,
            "updated_state": state.copy()
        })

        # broadcast node end
        try:
            await broadcast_event(run_id, {
                "event": "node_end",
                "run_id": run_id,
                "node": current,
                "step": steps,
                "state": state.copy()
            })
        except Exception:
            workflow_logger.error({"event": "broadcast_failed", "stage": "node_end", "run_id": run_id, "node": current})

        # persist after end event
        try:
            save_run(run_id, graph_id, state, RUNS[run_id]["status"], RUNS[run_id]["log"])
        except Exception:
            workflow_logger.error({
                "event": "db_save_failed",
                "run_id": run_id,
                "stage": "after_end",
                "node": current
            })

        # Find next node
        edge = graph.get("edges", {}).get(current)
        if edge is None:
            current = None
            break

        # Simple next step
        if isinstance(edge, str):
            current = edge
            continue

        # Conditional branching
        if isinstance(edge, dict):
            cond = edge.get("condition")
            if cond is None:
                current = None
                break
            if _eval_condition(cond, state):
                current = edge.get("true")
            else:
                current = edge.get("false")
            continue

        # Default stop
        current = None

    # mark finished and persist final state
    RUNS[run_id]["status"] = "finished"

    # log run finished
    workflow_logger.info({
        "event": "run_finished",
        "run_id": run_id,
        "graph_id": graph_id,
        "final_state": state,
        "steps": steps
    })

    # broadcast run finished
    try:
        await broadcast_event(run_id, {
            "event": "run_finished",
            "run_id": run_id,
            "final_state": state
        })
    except Exception:
        workflow_logger.error({"event": "broadcast_failed", "stage": "run_finished", "run_id": run_id})

    try:
        save_run(run_id, graph_id, state, RUNS[run_id]["status"], RUNS[run_id]["log"])
    except Exception:
        workflow_logger.error({
            "event": "db_save_failed",
            "run_id": run_id,
            "stage": "final_save"
        })

    return run_id
