#!/bin/bash
set -euo pipefail

# Run the olmocr container locally
docker run -it --rm \
  -p 8000:8000 \
  -e MODEL_ID="allenai/olmOCR-2-7B-1025-FP8" \
  -e HOST="0.0.0.0" \
  -e PORT="8000" \
  olmocr-local
