# Serve olmOCR via vLLM and a small HTTP API that accepts a PDF and returns OCR markdown.
# Matches vllm_server_task / vllm_server_host from https://github.com/allenai/olmocr/blob/main/olmocr/pipeline.py
FROM alleninstituteforai/olmocr:latest-with-model

# Conversion API (Flask) and entrypoint
RUN pip install --no-cache-dir flask

WORKDIR /app
COPY convert_server.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# vLLM serves on 30024 inside the container; conversion API on PORT (default 8080)
ENV VLLM_PORT=30024
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
