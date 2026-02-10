# OLMOCR Salad Cloud distributed inference

Docker image that runs **vLLM** (olmOCR model) and an HTTP API to **convert a PDF to markdown**. The container can be invoked by a job-queue worker that sends a PDF and receives OCR text.

## Container behavior (from `vllm_server_task` / `vllm_server_host`)

- **vLLM** is started with the same options as [olmocr pipeline](https://github.com/allenai/olmocr/blob/main/olmocr/pipeline.py): `vllm serve <model> --port 30024 --served-model-name olmocr` (plus tensor/data parallel and memory options).
- After vLLM is ready, a small **conversion API** listens on `PORT` (default **8080**):
  - **GET /** or **GET /health** — healthcheck (returns 503 until vLLM is ready).
  - **POST /convert** — body: raw PDF bytes or `multipart/form-data` with `file`; response: markdown text or `{"text": "..."}` if `Accept: application/json` or `?format=json`.

## Build and run

```bash
cd src
docker build -t olmocr-salad-cloud .
docker run --gpus all -p 8080:8080 olmocr-salad-cloud
```

Then:

- Health: `curl http://localhost:8080/`
- Convert: `curl -X POST http://localhost:8080/convert -H "Content-Type: application/pdf" --data-binary @your.pdf -o out.md`

## Worker example

A worker that polls a job queue, downloads the PDF, calls the container, and uploads the result can call the inference server like this:

```python
# Get job and download PDF bytes, then:
response = requests.post(
    f"http://{CONTAINER_HOST}:8080/convert",
    data=pdf_bytes,
    headers={"Content-Type": "application/pdf"},
    timeout=600,
)
response.raise_for_status()
markdown = response.text  # or response.json()["text"] for JSON
# Upload markdown and return job result
```

See `src/worker_example.py` for a full loop (health + optional TEST_PDF_PATH for a single file).

## Env (container)

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_PORT` | 30024 | Port vLLM listens on (internal) |
| `PORT` | 8080 | Conversion API port (expose this) |
| `HOST` | 0.0.0.0 | Bind address for conversion API |
| `MAX_SERVER_READY_TIMEOUT` | 600 | Seconds to wait for vLLM before failing |
| `TARGET_LONGEST_IMAGE_DIM` | 1288 | Longest image dimension for PDF rendering |
| `MAX_CONCURRENT_PAGES` | 64 | Pages sent to vLLM in parallel (raise to use GPU/KV cache more) |
| `GPU_MEMORY_UTILIZATION` | (vLLM default) | vLLM GPU memory fraction (e.g. 0.95 for more KV cache) |
| `MAX_MODEL_LEN` | 16384 | vLLM max model length |

## Original pipeline usage (batch, no API)

```bash
docker run --gpus all -v ./data:/workspace alleninstituteforai/olmocr:latest-with-model \
  -c "python -m olmocr.pipeline /workspace/output --markdown --pdfs /workspace/holybiblecontain03thom.pdf"
```

Resultant markdown is under *data/output/markdown/workspace*.



