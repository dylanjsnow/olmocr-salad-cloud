import base64
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "https://romaine-ceviche-3b19vknj8drqwzvi.salad.cloud/v1/chat/completions"
MODEL_ID = "allenai/olmOCR-2-7B-1025-FP8"
MAX_EDGE_PX = 1400
REQUEST_TIMEOUT_SEC = 180
IMAGE_FORMAT = "png"
JPEG_QUALITY = 60


def render_first_page_to_image(pdf_path: Path, output_path: Path) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "/usr/bin/sips",
            "-s",
            "format",
            IMAGE_FORMAT,
            "-s",
            "formatOptions",
            str(JPEG_QUALITY),
            "-Z",
            str(MAX_EDGE_PX),
            str(pdf_path),
            "--out",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def build_payload(image_bytes: bytes, image_format: str = "png") -> bytes:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract the text from this image and return it as "
                            "clean markdown. Preserve headings and lists when obvious. "
                            "Return only the markdown."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_format};base64,{encoded}",
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 4096,
    }
    return json.dumps(payload).encode("utf-8")


def send_request(payload: bytes) -> str:
    api_key = os.environ.get("SALAD_CLOUD_API_KEY")
    if not api_key:
        raise RuntimeError("SALAD_CLOUD_API_KEY is not set in the environment.")
    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Salad-Api-Key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return f"HTTP {exc.code}: {body}"


def main() -> None:
    image_path = Path("data/excerpt_layout.png")
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    image_bytes = image_path.read_bytes()
    # Determine format from file extension
    image_format = image_path.suffix[1:] if image_path.suffix else "png"
    payload = build_payload(image_bytes, image_format)
    response_text = send_request(payload)
    
    # Parse and print just the markdown content
    try:
        response_json = json.loads(response_text)
        if "choices" in response_json and len(response_json["choices"]) > 0:
            content = response_json["choices"][0]["message"]["content"]
            print(content)
        else:
            print(response_text)
    except json.JSONDecodeError:
        print(response_text)


if __name__ == "__main__":
    main()
