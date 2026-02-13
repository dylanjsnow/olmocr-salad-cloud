# OLMOCR Salad Cloud

Docker image: vLLM (olmOCR) + HTTP API to convert a PDF to markdown.

## Setup

Copy the .env.template into a local .env and add your Salad Cloud API details and any missing values from the .env file.

```bash
cd src/
cp .env.template .env
```

## Build and run

```bash
cd src
cp .env.template .env # Modify this to add any missing values
docker build -t olmocr-salad-cloud .
docker run --gpus all -p 8000:8000 olmocr-salad-cloud
```

## API

- **GET /health** — General health (JSON). Returns 503 until vLLM is ready.
- **GET /startup** — Salad startup probe. Fails repeatedly → container restarted.
- **GET /live** — Salad liveness probe. Fails repeatedly → container restarted.
- **GET /hc** — Salad readiness probe. Fails → traffic stopped; container keeps running.
- **POST /convert** — Body: PDF bytes. Response: markdown (or JSON `{"text":"..."}` with `?format=json`).

Probe config (HTTP/1.X, port 8000, timeout 1s): startup `/startup` initial_delay 60s; liveness `/live` period 10s; readiness `/hc` period 10s.

```bash
curl -X POST http://localhost:8000/convert -H "Content-Type: application/pdf" --data-binary @your.pdf -o out.md
```

From a worker: `POST` the PDF to `http://<host>:8000/convert`, get markdown in the response body (or `response.json()["text"]`).

**Config:** Copy `src/.env.template` to `src/.env` and set your values.

## SaladCloud configuration

1. **Create a SaladCloud Job Queue** — Set `SALAD_API_KEY`, `SALAD_ORGANIZATION_NAME`, `SALAD_PROJECT_NAME`, `SALAD_QUEUE_NAME` in `src/.env`, then:

```bash
source src/.env && curl -sS -X POST "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/queues" -H "Salad-Api-Key: $SALAD_API_KEY" -H "Content-Type: application/json" -d "{\"name\":\"$SALAD_QUEUE_NAME\",\"display_name\":\"$SALAD_QUEUE_NAME\"}"
```

2. **Confirm the SaladCloud Job Queue exists**:

```bash
source src/.env && curl -sS -X GET "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/queues/${SALAD_QUEUE_NAME}" -H "Salad-Api-Key: $SALAD_API_KEY" -H "Content-Type: application/json" | jq .
```

3. **Create a SaladCloud Job Queue Worker container**:

```bash
cd base
docker image build -t mandelbrot:latest .
```

4. **Make the Job Queue worker container publicly available (can use either Github Container Registry, or Docker Container Registry)**:

```bash
docker login ghcr.io
docker tag mandelbrot:latest ghcr.io/dylanjsnow/mandelbrot:latest
docker push ghcr.io/dylanjsnow/mandelbrot:latest
```

5. **Check the container works and is publicly accessible**:

```bash
docker pull ghcr.io/dylanjsnow/mandelbrot:latest
```

6. **Create a SaladCloud Container Group using this container**:

```bash
source src/.env
curl -sS -X POST \
  "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/containers" \
  -H "Salad-Api-Key: $SALAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq --arg q "$SALAD_QUEUE_NAME" '.queue_connection.queue_name = $q' config/container-group-mandelbrot.json)"
```

7. **List container groups** — Confirm the container group was created and check its status ([List Container Groups API](https://docs.salad.com/reference/saladcloud-api/container-groups/list-container-groups)):

```bash
source src/.env && curl -sS -X GET "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/containers" -H "Salad-Api-Key: $SALAD_API_KEY" | jq .
```

