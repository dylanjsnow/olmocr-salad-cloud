#!/usr/bin/env bash
# Start vLLM in background, wait for ready, then exec the command (main.py or Kelpie).
# main.py calls the vLLM API, so the server must be up before the job runs.
set -e

p="${VLLM_PORT:-30024}"
m="${OLMOCR_MODEL_PATH:-allenai/olmOCR-2-7B-1025-FP8}"
n="${MAX_SERVER_READY_TIMEOUT:-600}"

# OMP_NUM_THREADS=1 avoids thread contention with vLLM's CUDA usage.
export OMP_NUM_THREADS=1

# Start vLLM in background. --served-model-name must be "olmocr" (main.py expects it).
# Tensor/data parallel and max-model-len are configurable via env.
vllm serve "$m" --port "$p" --served-model-name olmocr \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE:-1}" \
  --data-parallel-size "${DATA_PARALLEL_SIZE:-1}" \
  --max-model-len "${MAX_MODEL_LEN:-16384}" \
  ${GPU_MEMORY_UTILIZATION:+--gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"} &
pid=$!

# Forward SIGTERM/SIGINT to vLLM so the container shuts down cleanly.
trap "kill $pid 2>/dev/null; wait $pid 2>/dev/null; exit 0" SIGTERM SIGINT

# Poll /v1/models until vLLM is ready (model load can take 1–2 min).
a=1
while [ "$a" -le "$n" ]; do
  curl -sSf --max-time 10 "http://127.0.0.1:${p}/v1/models" >/dev/null 2>&1 && break
  a=$((a + 1))
  sleep 1
done
[ "$a" -gt "$n" ] && kill $pid 2>/dev/null && exit 1

# Replace this process with the job. CMD (or args after --) become $@.
exec "${@:-python /app/main.py --help}"
