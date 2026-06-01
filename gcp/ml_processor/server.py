import hashlib
import hmac
import json
import os
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import requests


PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
HMAC_SECRET = os.getenv("INTERNAL_HMAC_SECRET", "")
MAX_TIME_SKEW_SECONDS = int(os.getenv("MAX_TIME_SKEW_SECONDS", "300"))


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


def placeholder_inference(inputs):
    detections = []

    for item in inputs:
        url = item.get("url")
        if not url:
            raise ValueError("Input item is missing url")

        # Verifies the temporary S3 presigned URL works.
        # We do not store the media bytes.
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        detections.append({
            "label": "placeholder_species",
            "confidence": 0.99,
            "source": item.get("source", "unknown"),
            "timestamp_sec": item.get("timestamp_sec"),
            "bbox": None,
        })

    counts = Counter(detection["label"] for detection in detections)

    return {
        "tags": sorted(counts.keys()),
        "tag_counts": dict(counts),
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

            inference_result = placeholder_inference(inputs)

            return json_response(self, 200, {
                "request_id": request_id,
                "hash": media_hash,
                "status": "success",
                "tags": inference_result["tags"],
                "tag_counts": inference_result["tag_counts"],
                "detections": inference_result["detections"],
                "model_name": "placeholder",
                "model_version": "dev",
            })

        except PermissionError as exc:
            return json_response(self, 401, {"error": str(exc)})

        except Exception as exc:
            return json_response(self, 500, {"error": str(exc)})

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Starting ML processor on port {PORT}")
    server.serve_forever()
