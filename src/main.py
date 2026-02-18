#!/usr/bin/env python3
"""
PDF-to-markdown OCR using OLMOCR pipeline + vLLM. Kelpie-compatible.
Uses sync.before paths: --pdf points to local path (e.g. inputs/job123/doc.pdf).
If file doesn't exist (local testing), downloads from S3 using --s3-bucket and --s3-prefix.

Delegates to olmocr.pipeline for PDF processing (no manual base64/image handling).

Usage: python main.py --pdf <path> [--output <path>] [--s3-bucket BUCKET] [--s3-prefix PREFIX]
"""
import argparse
import os
import subprocess
import sys
import tempfile

S3_ENDPOINT = os.environ.get(
    "S3_ENDPOINT_URL",
    "https://1f7ddfe3a5c59735ef33c1000f4260a0.r2.cloudflarestorage.com",
)
VLLM_PORT = os.environ.get("VLLM_PORT", "30024")
VLLM_SERVER = os.environ.get("VLLM_BASE", f"http://127.0.0.1:{VLLM_PORT}/v1")


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


def _markdown_output_path(workspace: str, source_file: str) -> str:
    """Compute markdown path matching olmocr.pipeline get_markdown_path for local files."""
    relative = source_file.lstrip("/")
    parts = [p for p in relative.split("/") if p and p != ".."]
    relative = "/".join(parts)
    md_filename = os.path.splitext(os.path.basename(relative))[0] + ".md"
    dir_path = os.path.dirname(relative)
    markdown_dir = os.path.join(workspace, "markdown", dir_path) if dir_path else os.path.join(workspace, "markdown")
    return os.path.join(markdown_dir, md_filename)


def main():
    ap = argparse.ArgumentParser(description="OLMOCR PDF to markdown")
    ap.add_argument("--pdf", required=True, help="Local path to PDF (sync.before destination)")
    ap.add_argument("--output", "-o", help="Write markdown to file (for Kelpie sync.after)")
    ap.add_argument("--s3-bucket", help="S3/R2 bucket for download when file missing (local test)")
    ap.add_argument("--s3-prefix", help="S3/R2 object key for download when file missing (local test)")
    args = ap.parse_args()

    pdf_path = os.path.abspath(args.pdf)
    if not os.path.isfile(pdf_path):
        if args.s3_bucket and args.s3_prefix:
            pdf_path = download_file(pdf_path, args.s3_bucket, args.s3_prefix)
        else:
            print(f"error: file not found: {args.pdf} (set --s3-bucket and --s3-prefix for download)", file=sys.stderr)
            sys.exit(1)

    with tempfile.TemporaryDirectory() as workspace:
        cmd = [
            sys.executable, "-m", "olmocr.pipeline", workspace,
            "--server", VLLM_SERVER.rstrip("/"),
            "--model", os.environ.get("OLMOCR_MODEL", "olmocr"),
            "--markdown",
            "--pdfs", pdf_path,
        ]
        subprocess.run(cmd, check=True)

        md_path = _markdown_output_path(workspace, pdf_path)
        if not os.path.isfile(md_path):
            print(f"error: pipeline did not produce {md_path}", file=sys.stderr)
            sys.exit(1)

        with open(md_path) as f:
            markdown = f.read()

    print(markdown)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(markdown)


if __name__ == "__main__":
    main()
