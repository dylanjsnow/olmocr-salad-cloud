# Serve olmOCR via vLLM and a small HTTP API that accepts a PDF and returns OCR markdown.
# Matches vllm_server_task / vllm_server_host from https://github.com/allenai/olmocr/blob/main/olmocr/pipeline.py
FROM alleninstituteforai/olmocr:latest-with-model

# Conversion API (Flask), dotenv, and entrypoint
RUN pip install --no-cache-dir flask python-dotenv

WORKDIR /app
COPY app.py entrypoint.sh .env.template /app/
RUN chmod +x /app/entrypoint.sh && cp /app/.env.template /app/.env

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
