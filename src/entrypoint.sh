#!/usr/bin/env bash
# Start vLLM (olmOCR) in the background, wait for ready, then run the conversion API.
# Matches vllm_server_task() / vllm_server_host() from olmocr pipeline.

set -e

VLLM_PORT="${VLLM_PORT:-30024}"
PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
# Model: use repo id so vLLM uses pre-downloaded cache (HF_HOME set in with-model image)
MODEL_PATH="${OLMOCR_MODEL_PATH:-allenai/olmOCR-2-7B-1025-FP8}"

export VLLM_PORT
export PORT
export HOST

# Same defaults as olmocr pipeline (vllm_server_task)
TP="${TENSOR_PARALLEL_SIZE:-1}"
DP="${DATA_PARALLEL_SIZE:-1}"
GPU_UTIL="${GPU_MEMORY_UTILIZATION:-}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"

VLLM_CMD=(
  vllm serve "$MODEL_PATH"
  --port "$VLLM_PORT"
  --disable-log-requests
  --uvicorn-log-level warning
  --served-model-name olmocr
  --tensor-parallel-size "$TP"
  --data-parallel-size "$DP"
  --limit-mm-per-prompt '{"video": 0}'
  --max-model-len "$MAX_MODEL_LEN"
)

if [ -n "$GPU_UTIL" ]; then
  VLLM_CMD+=(--gpu-memory-utilization "$GPU_UTIL")
fi

echo "Starting vLLM on port $VLLM_PORT (model: $MODEL_PATH) ..."
export OMP_NUM_THREADS=1
"${VLLM_CMD[@]}" &
VLLM_PID=$!

cleanup() {
  echo "Shutting down vLLM (PID $VLLM_PID) ..."
  kill "$VLLM_PID" 2>/dev/null || true
  wait "$VLLM_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Wait for vLLM to be ready (same idea as vllm_server_ready in pipeline)
VLLM_URL="http://127.0.0.1:${VLLM_PORT}/v1/models"
MAX_ATTEMPTS="${MAX_SERVER_READY_TIMEOUT:-600}"
attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  if curl -sSf --max-time 10 "$VLLM_URL" >/dev/null 2>&1; then
    echo "vLLM is ready."
    break
  fi
  echo "Waiting for vLLM ... attempt $attempt/$MAX_ATTEMPTS"
  sleep 1
  attempt=$((attempt + 1))
done

if [ "$attempt" -gt "$MAX_ATTEMPTS" ]; then
  echo "vLLM did not become ready in time."
  kill "$VLLM_PID" 2>/dev/null || true
  exit 1
fi

# Run the conversion API (health on /, convert on POST /convert)
echo "Starting conversion API on $HOST:$PORT ..."
exec python /app/convert_server.py
