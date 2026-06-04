import hashlib
import hmac
import json
import os
import time
import tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests
from shared.model import ImageTagger


PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
HMAC_SECRET = os.getenv("INTERNAL_HMAC_SECRET", "")
MAX_TIME_SKEW_SECONDS = int(os.getenv("MAX_TIME_SKEW_SECONDS", "300"))

LOCAL_CLASSIFIER_MODEL_PATH = Path(os.getenv("LOCAL_CLASSIFIER_MODEL_PATH", "/models/model.pt"))
LOCAL_DETECTOR_MODEL_PATH = Path(os.getenv("LOCAL_DETECTOR_MODEL_PATH", "/models/mdv5a.pt"))

_tagger = None


def json_response(handler, status_code, payload):
    body = json.dumps(payload).encode("utf-8")

    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def verify_hmac(body, timestamp, signature):
    if not HMAC_SECRET:
        raise ValueError("INTERNAL_HMAC_SECRET is not configured")

    if not timestamp or not signature:
        raise PermissionError("Missing HMAC headers")

    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise PermissionError("Invalid timestamp") from exc

    now = int(time.time())

    if abs(now - request_time) > MAX_TIME_SKEW_SECONDS:
        raise PermissionError("Expired request timestamp")

    message = timestamp.encode("utf-8") + b"." + body

    expected = hmac.new(
        HMAC_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise PermissionError("Invalid HMAC signature")


def get_tagger() -> ImageTagger:
    global _tagger

    if _tagger is not None:
        return _tagger

    for model_path in [LOCAL_CLASSIFIER_MODEL_PATH, LOCAL_DETECTOR_MODEL_PATH]:
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if model_path.stat().st_size < 1024:
            raise ValueError(f"Model file looks too small: {model_path} ({model_path.stat().st_size} bytes)")

    print("Initializing ImageTagger")
    _tagger = ImageTagger(
        classifier_model_path=LOCAL_CLASSIFIER_MODEL_PATH,
        detector_model_path=LOCAL_DETECTOR_MODEL_PATH,
    )
    print("ImageTagger initialized")

    return _tagger


def download_input_to_temp_file(url: str) -> Path:
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)

    temp_path = Path(path)
    temp_path.write_bytes(response.content)

    if temp_path.stat().st_size == 0:
        raise ValueError("Downloaded input image is empty")

    return temp_path


def real_image_inference(inputs):
    tagger = get_tagger()

    all_tags = Counter()
    detections = []

    for item in inputs:
        url = item.get("url")
        if not url:
            raise ValueError("Input item is missing url")

        source = item.get("source", "unknown")
        timestamp_sec = item.get("timestamp_sec")

        local_image_path = download_input_to_temp_file(url)

        try:
            result = tagger.tag_image(local_image_path)
        finally:
            try:
                local_image_path.unlink(missing_ok=True)
            except Exception:
                pass

        item_tags = result.get("tags", {})
        all_tags.update(item_tags)

        for detection in result.get("detections", []):
            detections.append({
                **detection,
                "source": source,
                "timestamp_sec": timestamp_sec,
            })

    return {
        "tags": sorted(all_tags.keys()),
        "tag_counts": dict(all_tags),
        "detections": detections,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path in ["/", "/health"]:
            return json_response(self, 200, {
                "service": "aussie-ecolens-ml-processor",
                "environment": ENVIRONMENT,
                "status": "healthy",
                "model_name": "gcp_image_tagger",
                "model_version": "mdv5a-plus-classifier",
            })

        return json_response(self, 404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path != "/process-media":
            return json_response(self, 404, {"error": "Not found"})

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)

            verify_hmac(
                body=body,
                timestamp=self.headers.get("X-Timestamp", ""),
                signature=self.headers.get("X-Signature", ""),
            )

            payload = json.loads(body.decode("utf-8"))

            request_id = payload.get("request_id")
            media_hash = payload.get("hash")
            media_type = payload.get("media_type")
            inputs = payload.get("inputs", [])

            if not request_id:
                return json_response(self, 400, {"error": "Missing request_id"})

            if not media_hash:
                return json_response(self, 400, {"error": "Missing hash"})

            if media_type not in ["image", "video"]:
                return json_response(self, 400, {"error": "media_type must be image or video"})

            if not inputs:
                return json_response(self, 400, {"error": "At least one input is required"})

            if media_type != "image":
                return json_response(self, 400, {"error": "GCP image processor currently supports image only"})

            inference_result = real_image_inference(inputs)

            return json_response(self, 200, {
                "request_id": request_id,
                "hash": media_hash,
                "status": "success",
                "tags": inference_result["tags"],
                "tag_counts": inference_result["tag_counts"],
                "detections": inference_result["detections"],
                "model_name": "gcp_image_tagger",
                "model_version": "mdv5a-plus-classifier",
            })

        except PermissionError as exc:
            return json_response(self, 401, {"error": str(exc)})

        except Exception as exc:
            print(f"Error processing request: {exc}")
            return json_response(self, 500, {"error": str(exc)})

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))


if __name__ == "__main__":
    # Start the HTTP server immediately so Cloud Run can pass its startup probe.
    # The model is lazy-loaded on the first /process-media request via get_tagger().
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Starting ML processor on port {PORT}")
    server.serve_forever()
