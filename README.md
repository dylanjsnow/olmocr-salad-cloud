# OLMOCR Salad Cloud

PDF-to-markdown OCR worker using OLMOCR + vLLM. Kelpie-ready for coordinating GPU containers to convert documents, with S3-compatible storage (e.g. Cloudflare R2) for sync.

## Requirements

- **GPU** (for vLLM)
- **Docker** with `--gpus all`
- **R2 credentials** in `src/.env` (see `src/.env.template`)

## Quick test (local GPU)

From the project root:

```bash
docker build -t olmocr-kelpie:latest -f src/Dockerfile-local src/ && docker run --rm --gpus all --env-file src/.env -v "$(pwd)/data:/data" olmocr-kelpie:latest python /app/main.py --pdf /data/berkshire-hathaway-202310-k.pdf --s3-bucket epstein-documents --s3-prefix "data/berkshire-hathaway-202310-k.pdf" -o /data/output.md
```

Downloads `data/berkshire-hathaway-202310-k.pdf` from the `epstein-documents` R2 bucket, runs OCR, and writes markdown to `data/output.md`.

To upload the result to R2 instead of writing locally:

```bash
S3_OUTPUT="data/output/berkshire-hathaway-202310-k.md" ./run_test.sh
```

Or with the one-liner, use `--s3-output` instead of `-o`:

```bash
docker build -t olmocr-kelpie:latest -f src/Dockerfile-local src/
docker run --rm --gpus all --env-file src/.env -v "$(pwd)/data:/data" olmocr-kelpie:latest python /app/main.py --pdf /data/berkshire-hathaway-202310-k.pdf --s3-bucket epstein-documents --s3-prefix "data/berkshire-hathaway-202310-k.pdf" --s3-output "data/output/berkshire-hathaway-202310-k.md"
```

## Usage

`main.py` is a CLI for PDF → markdown:

```bash
# With Kelpie sync (file already at local path)
python main.py --pdf /path/to/doc.pdf --output /path/to/output.md

# Local test: download from S3/R2 when file doesn't exist
python main.py --pdf /data/doc.pdf --s3-bucket epstein-documents --s3-prefix "berkshire-hathaway-202310-k.pdf" -o /data/output.md

# Upload result to S3/R2 instead of local file
python main.py --pdf /data/doc.pdf --s3-bucket epstein-documents --s3-prefix "data/doc.pdf" --s3-output "data/output/doc.md"
```

## Kelpie job shape

When using the [Kelpie API](https://github.com/SaladTechnologies/kelpie-api), submit jobs with `sync.before` for the PDF and `sync.after` for the markdown:

```json
{
  "command": "python",
  "arguments": ["/app/main.py", "--pdf", "/data/inputs/doc.pdf", "-o", "/data/outputs/markdown.md"],
  "environment": {},
  "sync": {
    "before": [{
      "bucket": "epstein-documents",
      "prefix": "path/to/doc.pdf",
      "local_path": "/data/inputs/doc.pdf",
      "direction": "download"
    }],
    "after": [{
      "bucket": "epstein-documents",
      "prefix": "outputs/markdown.md",
      "local_path": "/data/outputs/markdown.md",
      "direction": "upload"
    }]
  },
  "container_group_id": "<your-container-group-uuid>"
}
```

Container: vLLM starts via entrypoint; Kelpie runs `main.py` per job. Add the Kelpie binary and set `CMD ["/kelpie"]` when deploying.

## Environment configuration

Copy `src/.env.template` to `src/.env` and configure:

| Variable | Used by | Purpose |
|----------|---------|---------|
| `AWS_ACCESS_KEY_ID` | main.py | R2/S3-compatible storage access |
| `AWS_SECRET_ACCESS_KEY` | main.py | R2/S3-compatible storage secret |
| `S3_ENDPOINT_URL` | main.py | R2 endpoint |
| `VLLM_PORT`, `OLMOCR_MODEL_PATH`, etc. | Dockerfile entrypoint, main.py | vLLM server and OLMOCR settings |

When deploying with Kelpie, the Kelpie binary will require `KELPIE_API_URL` and `SALAD_PROJECT`; add those to your deployment environment.
