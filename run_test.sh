#!/usr/bin/env bash
# Build and run OLMOCR on a PDF. Requires GPU and R2 credentials in src/.env.
# Usage: PDF_PREFIX="1-23-2026 402f_Notice.pdf" ./run_test.sh
set -e
cd "$(dirname "$0")"

PDF_PREFIX="${PDF_PREFIX:-1-23-2026 402f_Notice.pdf}"
echo "Building image (Dockerfile-local)..."
docker build -t olmocr-kelpie:latest -f src/Dockerfile-local src/

echo "Running OCR on PDF (download from epstein-documents/${PDF_PREFIX})..."
docker run --rm --gpus all \
  --env-file src/.env \
  -v "$(pwd)/data:/data" \
  olmocr-kelpie:latest \
  python /app/main.py --pdf "/data/$(basename "$PDF_PREFIX")" --s3-bucket epstein-documents --s3-prefix "$PDF_PREFIX" -o /data/output.md
