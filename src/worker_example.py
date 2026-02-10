"""
Example worker: poll a job queue, download PDF input, call the inference container
(POST /convert), then upload the markdown result.

Configure via env: HOST, PORT (inference API), and your queue/storage credentials.
"""
import os
import time

import requests

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = os.environ.get("PORT", "8080")
BASE_URL = f"http://{HOST}:{PORT}"

# Optional: wait for the inference server before starting
WAIT_FOR_SERVER = int(os.environ.get("WAIT_FOR_SERVER", "1"))
INITIAL_SLEEP = int(os.environ.get("INITIAL_SLEEP", "2"))


def main():
    if WAIT_FOR_SERVER and INITIAL_SLEEP:
        time.sleep(INITIAL_SLEEP)

    while True:
        print(80 * "*")
        print("Get a job and download its input")

        # 1) Retrieve a job from your queue (e.g. AWS SQS) and get PDF URL or bytes
        # job = get_job_from_queue()
        # pdf_path_or_url = job["input_ref"]
        # pdf_bytes = download_from_storage(pdf_path_or_url)

        # For local testing: use a local PDF path and read bytes
        pdf_path = os.environ.get("TEST_PDF_PATH")
        if pdf_path and os.path.isfile(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        else:
            # No real job: just hit health and loop
            print("No TEST_PDF_PATH set; calling health only.")
            try:
                r = requests.get(f"{BASE_URL}/", timeout=10)
                print("Health response:", r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
            except Exception as e:
                print("Health check failed:", e)
            time.sleep(5)
            continue

        # 2) Call the inference server: POST /convert with the PDF
        print("Calling inference server:", BASE_URL)
        try:
            r = requests.post(
                f"{BASE_URL}/convert",
                data=pdf_bytes,
                headers={"Content-Type": "application/pdf"},
                timeout=600,
            )
            r.raise_for_status()
            markdown = r.text
            if r.headers.get("Content-Type", "").startswith("application/json"):
                import json
                markdown = r.json().get("text", "")
            print("Got markdown length:", len(markdown))
        except requests.RequestException as e:
            print("Inference failed:", e)
            # Return failure to queue
            time.sleep(5)
            continue

        # 3) Upload the job output to cloud storage
        # output_ref = upload_to_storage(markdown, job["output_key"])
        # 4) Return the job result to the queue (success/failure)
        # return_job_result(job["id"], success=True, output_ref=output_ref)
        print("Upload job output and return its result (stub)")

        # If you were processing one test file, exit
        if pdf_path:
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
