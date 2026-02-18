#!/usr/bin/env python3
"""
PDF-to-markdown OCR using OLMOCR + vLLM. Kelpie-compatible.
Uses sync.before paths: --pdf points to local path (e.g. inputs/job123/doc.pdf).
If file doesn't exist (local testing), downloads from S3 using --s3-bucket and --s3-prefix.

Usage: python main.py --pdf <path> [--output <path>] [--s3-bucket BUCKET] [--s3-prefix PREFIX]
"""
import argparse
import os
import sys

import requests
from pypdf import PdfReader

from olmocr.data.renderpdf import render_pdf_to_base64png
from olmocr.prompts import PageResponse, build_no_anchoring_v4_yaml_prompt
from olmocr.train.dataloader import FrontMatterParser

VLLM_PORT = int(os.environ.get("VLLM_PORT", "30024"))
VLLM_BASE = os.environ.get("VLLM_BASE", f"http://127.0.0.1:{VLLM_PORT}")
COMPLETION_URL = f"{VLLM_BASE.rstrip('/')}/v1/chat/completions"
TARGET_LONGEST_IMAGE_DIM = int(os.environ.get("TARGET_LONGEST_IMAGE_DIM", "1288"))
MAX_TOKENS = 8000
MODEL = os.environ.get("OLMOCR_MODEL", "olmocr")
S3_ENDPOINT = os.environ.get(
    "S3_ENDPOINT_URL",
    "https://1f7ddfe3a5c59735ef33c1000f4260a0.r2.cloudflarestorage.com",
)


def download_file(local_path: str, bucket: str, prefix: str) -> str:
    """
    Ensure PDF exists at local_path. If it exists (Kelpie sync already did it), return.
    Else download from S3 bucket/prefix to local_path. Returns local_path.
    """
    if os.path.isfile(local_path) and local_path.lower().endswith(".pdf"):
        return local_path
    try:
        import boto3
        from botocore.config import Config

        config = Config(region_name="auto", signature_version="s3v4")
        client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            config=config,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        client.download_file(Bucket=bucket, Key=prefix, Filename=local_path)
    except Exception as e:
        print(f"error: download failed: {e}", file=sys.stderr)
        sys.exit(1)
    return local_path


def process_page(pdf_path: str, page_num: int) -> str:
    """OCR one PDF page via vLLM, return markdown."""
    image_base64 = render_pdf_to_base64png(
        pdf_path, page_num, target_longest_image_dim=TARGET_LONGEST_IMAGE_DIM
    )
    query = {
        "model": MODEL,
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
    r = requests.post(COMPLETION_URL, json=query, timeout=300)
    r.raise_for_status()
    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        return ""
    parser = FrontMatterParser(front_matter_class=PageResponse)
    front_matter, text = parser._extract_front_matter_and_text(content)
    page_response = parser._parse_front_matter(front_matter, text)
    return page_response.natural_text or ""


def pdf_to_markdown(pdf_path: str) -> str:
    """Convert PDF to markdown (one page at a time)."""
    reader = PdfReader(pdf_path)
    num_pages = len(reader.pages)
    parts = []
    for p in range(1, num_pages + 1):
        parts.append(process_page(pdf_path, p))
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="OLMOCR PDF to markdown")
    ap.add_argument("--pdf", required=True, help="Local path to PDF (sync.before destination)")
    ap.add_argument("--output", "-o", help="Write markdown to file (for Kelpie sync.after)")
    ap.add_argument("--s3-bucket", help="S3/R2 bucket for download when file missing (local test)")
    ap.add_argument("--s3-prefix", help="S3/R2 object key for download when file missing (local test)")
    args = ap.parse_args()

    pdf_path = args.pdf
    if not os.path.isfile(pdf_path):
        if args.s3_bucket and args.s3_prefix:
            pdf_path = download_file(pdf_path, args.s3_bucket, args.s3_prefix)
        else:
            print(f"error: file not found: {pdf_path} (set --s3-bucket and --s3-prefix for download)", file=sys.stderr)
            sys.exit(1)

    markdown = pdf_to_markdown(pdf_path)
    print(markdown)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(markdown)


if __name__ == "__main__":
    main()
