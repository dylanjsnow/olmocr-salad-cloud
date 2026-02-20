#!/usr/bin/env bash
# Build and run OLMOCR on a PDF. Requires GPU. S3/R2 credentials in src/.env only when downloading from epstein-documents.
# Usage:
#   ./run_test.sh                         # use data/sample.pdf or fetch a public sample
#   PDF_PREFIX="myfile.pdf" ./run_test.sh # use data/myfile.pdf or download from S3
set -e
cd "$(dirname "$0")"

PDF_PREFIX="${PDF_PREFIX:-data/berkshire-hathaway-202310-k.pdf}"
PDF_BASENAME="$(basename "$PDF_PREFIX")"
LOCAL_PDF="data/${PDF_BASENAME}"
SAMPLE_URL="https://freetestdata.com/wp-content/uploads/2021/09/Free_Test_Data_100KB_PDF.pdf"

echo "Building image (Dockerfile-local)..."
docker build -t olmocr-kelpie:latest -f src/Dockerfile-local src/

S3_ARGS=()
if [[ -f "$LOCAL_PDF" ]]; then
  echo "Running OCR on PDF (local: $LOCAL_PDF)..."
elif [[ "$PDF_PREFIX" == "sample.pdf" ]] || [[ "$PDF_PREFIX" == "sample" ]]; then
  echo "Fetching sample PDF to data/sample.pdf..."
  mkdir -p data
  curl -sSL -o "$LOCAL_PDF" "$SAMPLE_URL"
  echo "Running OCR on PDF (sample)..."
else
  echo "Running OCR on PDF (download from epstein-documents/${PDF_PREFIX})..."
  S3_ARGS=(--s3-bucket epstein-documents --s3-prefix "$PDF_PREFIX")
fi

docker run --rm --gpus all \
  --env-file src/.env \
  -v "$(pwd)/data:/data" \
  olmocr-kelpie:latest \
  python /app/main.py --pdf "/data/${PDF_BASENAME}" "${S3_ARGS[@]}" -o /data/output.md
