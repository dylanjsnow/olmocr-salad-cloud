"""
HTTP server that accepts a PDF upload and returns OCR markdown using the local vLLM (olmOCR).
Designed to be run inside the same container as vLLM, after vLLM is ready.
"""
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from pypdf import PdfReader

# Olmocr imports (must be available in the container)
from olmocr.data.renderpdf import render_pdf_to_base64png
from olmocr.prompts import PageResponse, build_no_anchoring_v4_yaml_prompt
from olmocr.train.dataloader import FrontMatterParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# vLLM server URL (same host, port used by vllm_server_task in pipeline)
VLLM_PORT = int(os.environ.get("VLLM_PORT", "30024"))
VLLM_BASE = os.environ.get("VLLM_BASE", f"http://127.0.0.1:{VLLM_PORT}")
COMPLETION_URL = f"{VLLM_BASE.rstrip('/')}/v1/chat/completions"
TARGET_LONGEST_IMAGE_DIM = int(os.environ.get("TARGET_LONGEST_IMAGE_DIM", "1288"))
MAX_TOKENS = 8000
MODEL_NAME = os.environ.get("OLMOCR_MODEL_NAME", "olmocr")
# Process this many pages concurrently so vLLM can batch and use the GPU (KV cache).
# Pipeline uses hundreds of concurrent requests; 32–64 keeps one PDF conversion busy.
MAX_CONCURRENT_PAGES = int(os.environ.get("MAX_CONCURRENT_PAGES", "64"))


def build_page_query(local_pdf_path: str, page: int) -> dict:
    """Build the chat completion payload for one page (matches pipeline.build_page_query)."""
    image_base64 = render_pdf_to_base64png(
        local_pdf_path, page, target_longest_image_dim=TARGET_LONGEST_IMAGE_DIM
    )
    return {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_no_anchoring_v4_yaml_prompt()},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                ],
            }
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
    }


def process_page(local_pdf_path: str, page_num: int) -> str | None:
    """Call vLLM for one page and return natural_text, or None on failure."""
    query = build_page_query(local_pdf_path, page_num)
    try:
        r = requests.post(COMPLETION_URL, json=query, timeout=120)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("vLLM request failed for page %s: %s", page_num, e)
        return None

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        return None

    parser = FrontMatterParser(front_matter_class=PageResponse)
    front_matter, text = parser._extract_front_matter_and_text(content)
    page_response = parser._parse_front_matter(front_matter, text)
    return page_response.natural_text if page_response.natural_text else ""


def pdf_to_markdown(pdf_path: str) -> str:
    """Convert a PDF file to a single markdown string (concatenated page texts)."""
    reader = PdfReader(pdf_path)
    num_pages = len(reader.pages)
    workers = min(MAX_CONCURRENT_PAGES, num_pages)
    # Results by 1-based page number so we can join in order
    results = [None] * (num_pages + 1)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_page, pdf_path, p): p for p in range(1, num_pages + 1)}
        for fut in as_completed(futures):
            page_num = futures[fut]
            try:
                results[page_num] = fut.result() or ""
            except Exception as e:
                logger.warning("Page %s failed: %s", page_num, e)
                results[page_num] = ""

    parts = [results[p] or "" for p in range(1, num_pages + 1)]
    return "\n\n".join(parts)


def create_app():
    """Create Flask app for health + convert endpoints."""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        from flask import Flask, request
        jsonify = lambda x, **kw: (x, kw.get("status", 200))

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max PDF

    def _vllm_ready(timeout: float = 5) -> bool:
        """Return True if vLLM is ready to serve."""
        try:
            r = requests.get(f"{VLLM_BASE.rstrip('/')}/v1/models", timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    @app.route("/", methods=["GET"])
    @app.route("/health", methods=["GET"])
    def health():
        """Healthcheck for queue worker and load balancers."""
        ok = _vllm_ready(timeout=5)
        return jsonify({"status": "ok" if ok else "vllm_unavailable", "vllm_ready": ok}), 200 if ok else 503

    @app.route("/hc", methods=["GET"])
    def readiness():
        """
        Readiness probe for Job Queue Service (e.g. Salad).
        Returns 200 when vLLM is ready to receive jobs, 503 otherwise.
        Use a 1s timeout so the probe completes within typical timeout limits.
        """
        ok = _vllm_ready(timeout=1)
        if ok:
            return "", 200
        return "", 503

    @app.route("/convert", methods=["POST"])
    def convert():
        """
        Accept a PDF file (multipart/form-data 'file' or raw body) and return OCR markdown.
        Response: plain text markdown or JSON { "text": "...", "error": "..." }.
        """
        fd = None
        try:
            if request.content_type and "multipart/form-data" in request.content_type and "file" in request.files:
                f = request.files["file"]
                if not f.filename or not f.filename.lower().endswith(".pdf"):
                    return jsonify({"error": "Missing or non-PDF file"}), 400
                fd = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                f.save(fd.name)
                fd.close()
                fd = fd.name
            elif request.data:
                fd = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                fd.write(request.data)
                fd.close()
                fd = fd.name
            else:
                return jsonify({"error": "No PDF data (use multipart 'file' or raw body)"}), 400

            markdown = pdf_to_markdown(fd)
            if request.accept_mimetypes.best in ("application/json",) or request.args.get("format") == "json":
                return jsonify({"text": markdown})
            return markdown, 200, {"Content-Type": "text/markdown; charset=utf-8"}
        except Exception as e:
            logger.exception("Convert failed: %s", e)
            return jsonify({"error": str(e)}), 500
        finally:
            if fd and os.path.exists(fd):
                try:
                    os.unlink(fd)
                except OSError:
                    pass

    return app


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    app = create_app()
    app.run(host=host, port=port, threaded=True)
