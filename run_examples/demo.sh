#!/usr/bin/env bash
set -e
echo "Creating graph..."
curl -s -X POST "http://127.0.0.1:8000/graph/create" -H "Content-Type: application/json" -d @run_examples/graph_create.json | jq
echo
echo "Start a run (replace graph_id in run_payload.json or edit script)..."
curl -s -X POST "http://127.0.0.1:8000/graph/run" -H "Content-Type: application/json" -d @run_examples/run_payload.json | jq
