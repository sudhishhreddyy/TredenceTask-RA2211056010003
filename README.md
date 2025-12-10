
# Mini Workflow Engine — Summarization Example

A minimal workflow / graph engine implemented in FastAPI.  
This project demonstrates a small, portfolio-ready agent workflow engine with:

- Node-based execution (Python functions as nodes)
- Shared state passed between nodes (persisted)
- Conditional branching & looping
- SQLite persistence for graphs and runs
- Safe expression evaluation using `asteval`
- Structured JSON logging (rotating file)
- WebSocket live log streaming per run (`/ws/{run_id}`)
- Example summarization workflow (split → summarize → merge → refine → measure)

---

## 📁 Repo Layout

```
app/
    main.py
    engine.py
    workflows.py
    tools.py
    database.py
    logger.py
    ws_manager.py
run_examples/
    graph_create.json
    run_payload.json
requirements.txt
README.md
```

---

## 🚀 Quick Setup

### 1. Clone repo + create virtual environment

```bash
git clone https://github.com/<your-username>/summarization-workflow.git
cd summarization-workflow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the server

```bash
uvicorn app.main:app --reload
```

Open browser:  
👉 http://127.0.0.1:8000/docs

---

## 🧩 Create a Sample Graph

```bash
curl -X POST "http://127.0.0.1:8000/graph/create" \
  -H "Content-Type: application/json" \
  -d @run_examples/graph_create.json
```

---

## ▶️ Start a Workflow Run

```bash
curl -X POST "http://127.0.0.1:8000/graph/run" \
  -H "Content-Type: application/json" \
  -d @run_examples/run_payload.json
```

---

## 🔍 Poll Run State

```bash
curl "http://127.0.0.1:8000/graph/state/<run_id>"
```

---

## 📡 Watch Live Logs (WebSocket)

Connect any WS client to:

```
ws://127.0.0.1:8000/ws/<run_id>
```

Logs also appear in:

```
workflow.log
```

---

## �� What the Engine Supports

- Nodes implemented as Python functions (`workflows.py`)
- Shared state as a persisted dictionary
- Conditional expressions evaluated safely with `asteval`
- Looping and branching in workflow graphs
- Background run execution & run state inspection
- Live streaming logs via WebSocket
- SQLite persistence for graphs and workflow runs

---

## 🛠️ What I Would Improve With More Time

- Async / batched DB writes for better throughput  
- Per-user graph isolation + authentication  
- Pydantic request/response models for stricter validation  
- Full test suite + CI pipeline  
- Dockerfile for reproducible deployment  
- A visual UI for creating and monitoring workflow graphs  

---

