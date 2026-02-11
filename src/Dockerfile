# Serve olmOCR via vLLM and a small HTTP API that accepts a PDF and returns OCR markdown.
# Matches vllm_server_task / vllm_server_host from https://github.com/allenai/olmocr/blob/main/olmocr/pipeline.py
FROM alleninstituteforai/olmocr:latest-with-model

# Conversion API (Flask) and entrypoint
RUN pip install --no-cache-dir flask

WORKDIR /app
COPY app.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# vLLM serves on 30024 inside the container; conversion API on PORT (default 8000 for /hc readiness probe)
ENV VLLM_PORT=30024
ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
