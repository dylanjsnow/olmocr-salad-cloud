#!/usr/bin/env bash
# Start vLLM (olmOCR), wait for ready, then run the conversion API.

set -e

# Load defaults from .env (set -a exports vars when sourced)
[ -f /app/.env ] && set -a && source /app/.env && set +a

echo "Starting vLLM on port $VLLM_PORT (model: ${OLMOCR_MODEL_PATH:-allenai/olmOCR-2-7B-1025-FP8}) ..."
export OMP_NUM_THREADS=1

VLLM_CMD=(
  vllm serve "${OLMOCR_MODEL_PATH:-allenai/olmOCR-2-7B-1025-FP8}"
  --port "$VLLM_PORT"
  --disable-log-requests
  --uvicorn-log-level warning
  --served-model-name olmocr
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE:-1}"
  --data-parallel-size "${DATA_PARALLEL_SIZE:-1}"
  --limit-mm-per-prompt '{"video": 0}'
  --max-model-len "${MAX_MODEL_LEN:-16384}"
)
[[ -n "${GPU_MEMORY_UTILIZATION:-}" ]] && VLLM_CMD+=(--gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}")

"${VLLM_CMD[@]}" &
VLLM_PID=$!

cleanup() {
  echo "Shutting down vLLM (PID $VLLM_PID) ..."
  kill "$VLLM_PID" 2>/dev/null || true
  wait "$VLLM_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Wait for vLLM to be ready
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

echo "Starting conversion API on $HOST:$PORT ..."
exec python /app/app.py
