# OLMOCR Salad Cloud distributed inference

## Usage

curl https://romaine-ceviche-3b19vknj8drqwzvi.salad.cloud/v1/chat/completions \
  -X POST \
  -H 'Content-Type: application/json' \
  -H 'Salad-Api-Key: ' \
  -d '{"model": "allenai/olmOCR-2-7B-1025-FP8","messages": [{"role": "system","content": "You are a helpful assistant."},{"role": "user","content": "What is deep learning?"}]}'# olmocr-salad-cloud
