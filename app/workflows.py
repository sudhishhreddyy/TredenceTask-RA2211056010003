from typing import Dict

def split_text(state: Dict, tools=None):
    text = state.get("text", "")
    chunk_size = state.get("chunk_size", 100)

    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    return {"chunks": chunks}


def summarize_chunks(state: Dict, tools=None):
    summaries = []

    for c in state.get("chunks", []):
        words = c.split()
        shorter = " ".join(words[:max(1, len(words)//2)])
        summaries.append(shorter)

    return {"summaries": summaries}


def merge_summaries(state: Dict, tools=None):
    merged = " ".join(state.get("summaries", []))
    return {"merged_summary": merged}


def refine_summary(state: Dict, tools=None):
    summary = state.get("merged_summary", "")
    seen = set()
    output = []
    for word in summary.split():
        if word not in seen:
            seen.add(word)
            output.append(word)

    refined = " ".join(output)
    return {"refined_summary": refined}


def measure_length(state: Dict, tools=None):
    summary = state.get("refined_summary", "")
    return {"summary_length": len(summary)}
