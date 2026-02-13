# OLMOCR Salad Cloud

Docker image: vLLM (olmOCR) + HTTP API to convert a PDF to markdown.

## Setup

Copy the .env.template into a local .env and add your Salad Cloud API details and any missing values from the .env file.

```bash
cd src/
cp .env.template .env
```

You will need to retrieve the following details from your SaladCloud and GitHub accounts:

1. SaladCloud API Key: [https://portal.salad.com/api-key](https://portal.salad.com/api-key)
2. SaladCloud Organization name: [https://portal.salad.com/organizations](https://portal.salad.com/organizations)
3. SaladCloud Project name (from dropdown on lefthand side): [https://portal.salad.com/organizations/old-stock-consulting/projects/default/containers](https://portal.salad.com/organizations/old-stock-consulting/projects/default/containers)
4. GitHub username (top right icon when logged in): [https://github.com/](https://github.com/)
5. GitHub package access token (create new classic token, write:packages and read:packages access enabled at minimum): [https://github.com/settings/tokens/new](https://github.com/settings/tokens/new)

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

8. **List container group instances** — Check how many instances are deployed and their status ([List Container Group Instances API](https://docs.salad.com/reference/saladcloud-api/container-groups/list-container-group-instances)). Replace `mandelbrot-worker` with your container group name from step 6:

```bash
source src/.env && curl -sS -X GET "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/containers/mandelbrot-worker/instances" -H "Salad-Api-Key: $SALAD_API_KEY" | jq .
```

9. **Create a Job and add it to the Job Queue** — Submit a job for the queue worker to process ([Create Job API](https://docs.salad.com/reference/saladcloud-api/queues/create-job)). The `input` field may be any valid JSON; adjust it to match your worker's expected payload:

```bash
source src/.env && curl -sS -X POST "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/queues/${SALAD_QUEUE_NAME}/jobs" -H "Salad-Api-Key: $SALAD_API_KEY" -H "Content-Type: application/json" -d '{"input":{"example":true}}' | jq .
```

10. **List all jobs in the queue** — View jobs and their status ([List Jobs API](https://docs.salad.com/reference/saladcloud-api/queues/list-jobs)). To fetch a single job by ID, use the [Get Job API](https://docs.salad.com/reference/saladcloud-api/queues/get-job):

```bash
source src/.env && curl -sS -X GET "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION_NAME}/projects/${SALAD_PROJECT_NAME}/queues/${SALAD_QUEUE_NAME}/jobs" -H "Salad-Api-Key: $SALAD_API_KEY" | jq .
```

11. **Get the result of the Job being processed by the queue**:


