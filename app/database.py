import sqlite3
import json
import pathlib

DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "workflow.db"

def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Table for storing graph definitions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS graphs (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)

    # Table for storing workflow runs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            graph_id TEXT NOT NULL,
            state TEXT NOT NULL,
            status TEXT NOT NULL,
            log TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

# initialize on import
init_db()

def save_graph(graph_id: str, graph: dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO graphs (id, data) VALUES (?, ?)",
        (graph_id, json.dumps(graph)),
    )
    conn.commit()
    conn.close()

def load_graph(graph_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT data FROM graphs WHERE id = ?", (graph_id,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def save_run(run_id: str, graph_id: str, state: dict, status: str, log: list):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO runs (id, graph_id, state, status, log) VALUES (?, ?, ?, ?, ?)",
        (run_id, graph_id, json.dumps(state), status, json.dumps(log)),
    )
    conn.commit()
    conn.close()

def load_run(run_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT graph_id, state, status, log FROM runs WHERE id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "graph_id": row[0],
        "state": json.loads(row[1]),
        "status": row[2],
        "log": json.loads(row[3])
    }

def load_all_graphs():
    """
    Load every graph from the graphs table and return dict(graph_id -> graph_dict).
    Returns an empty dict on benign failures.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, data FROM graphs")
        rows = cur.fetchall()
        conn.close()
        return {row[0]: json.loads(row[1]) for row in rows}
    except Exception as e:
        # Print to console + return empty dict so startup doesn't fail.
        print(f"[database.load_all_graphs] failed: {e}")
        return {}
