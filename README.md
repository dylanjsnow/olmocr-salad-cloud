# OLMOCR Salad Cloud

Docker image: vLLM (olmOCR) + HTTP API to convert a PDF to markdown.

## Build and run

```bash
cd src
docker build -t olmocr-salad-cloud .
docker run --gpus all -p 8000:8000 olmocr-salad-cloud
```

## API

- **GET /hc** — Readiness (200 when ready, 503 otherwise). Use path `/hc`, port 8000, timeout 1s.
- **POST /convert** — Body: PDF bytes. Response: markdown (or JSON `{"text":"..."}` with `?format=json`).

```bash
curl -X POST http://localhost:8000/convert -H "Content-Type: application/pdf" --data-binary @your.pdf -o out.md
```

From a worker: `POST` the PDF to `http://<host>:8000/convert`, get markdown in the response body (or `response.json()["text"]`). Optional env: `PORT`, `MAX_CONCURRENT_PAGES`, `GPU_MEMORY_UTILIZATION`.
