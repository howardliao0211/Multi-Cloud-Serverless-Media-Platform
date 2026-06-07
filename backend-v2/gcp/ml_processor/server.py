import hashlib
import hmac
import json
import os
import urllib.request
from pathlib import Path
import time
import tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

BUILD_VERSION = "video-support-v2-debug"

import cv2
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



def _download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")

    print(f"Downloading model from {urlparse(url).scheme}://{urlparse(url).netloc}/... to {destination}")

    with requests.get(url, stream=True, timeout=(10, 600)) as response:
        response.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    tmp.replace(destination)
    return destination


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_model_path(
    *,
    url_env: str,
    local_env: str,
    default_local_path: str,
    cache_filename: str,
    checksum_env: str | None = None,
) -> str:
    url = os.getenv(url_env)
    local_path = os.getenv(local_env, default_local_path)

    if not url:
        print(f"{url_env} not set; using local model path {local_path}")
        return local_path

    version = os.getenv("GCP_MODEL_VERSION", "default")
    cache_dir = Path(os.getenv("GCP_MODEL_CACHE_DIR", "/tmp/aussie-ecolens-models")) / version
    destination = cache_dir / cache_filename

    if not destination.exists() or destination.stat().st_size == 0:
        _download_file(url, destination)
    else:
        print(f"Using cached model file {destination}")

    if checksum_env:
        expected = os.getenv(checksum_env)
        if expected:
            actual = _sha256_file(destination)
            if actual.lower() != expected.lower():
                destination.unlink(missing_ok=True)
                raise ValueError(
                    f"Checksum mismatch for {destination}: expected {expected}, got {actual}"
                )

    return str(destination)



def _download_model_if_needed(url: str, path: str) -> str:
    """Download a model from a URL into local writable storage if not already present."""
    if not url:
        raise ValueError(f"Missing model URL for {path}")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.stat().st_size > 0:
        print(f"Using cached model: {target} ({target.stat().st_size} bytes)", flush=True)
        return str(target)

    tmp = target.with_suffix(target.suffix + ".tmp")
    print(f"Downloading model to {target}", flush=True)

    with requests.get(url, stream=True, timeout=(10, 600)) as response:
        response.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    tmp.replace(target)
    print(f"Downloaded model: {target} ({target.stat().st_size} bytes)", flush=True)
    return str(target)


def _resolve_model_paths(model_urls: dict | None = None, model_version: str | None = None) -> tuple[str, str]:
    """Resolve classifier/detector model paths from request URLs, env URLs, or baked-in fallback."""
    cache_root = Path(os.environ.get("GCP_MODEL_CACHE_DIR", "/tmp/aussie-ecolens-models"))
    version = model_version or os.environ.get("GCP_MODEL_VERSION", "default")
    cache_dir = cache_root / version

    model_urls = model_urls or {}
    classifier_url = model_urls.get("classifier") or os.environ.get("GCP_CLASSIFIER_MODEL_URL", "")
    detector_url = model_urls.get("detector") or os.environ.get("GCP_DETECTOR_MODEL_URL", "")

    if classifier_url and detector_url:
        classifier_path = _download_model_if_needed(
            classifier_url,
            str(cache_dir / "model.pt"),
        )
        detector_path = _download_model_if_needed(
            detector_url,
            str(cache_dir / "mdv5a.pt"),
        )
        return classifier_path, detector_path

    # Backward-compatible fallback for old baked-model images.
    return "/models/model.pt", "/models/mdv5a.pt"

def get_tagger(model_urls: dict | None = None, model_version: str | None = None) -> ImageTagger:
    global _tagger

    if _tagger is not None:
        return _tagger

    print("Initializing ImageTagger", flush=True)

    classifier_model_path, detector_model_path = _resolve_model_paths(model_urls, model_version)
    print(f"Using classifier model: {classifier_model_path}", flush=True)
    print(f"Using detector model: {detector_model_path}", flush=True)

    for model_path in [Path(classifier_model_path), Path(detector_model_path)]:
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if model_path.stat().st_size < 1024:
            raise ValueError(
                f"Model file looks too small: {model_path} ({model_path.stat().st_size} bytes)"
            )

    _tagger = ImageTagger(
        classifier_model_path=classifier_model_path,
        detector_model_path=detector_model_path,
    )
    print("ImageTagger initialized", flush=True)

    return _tagger


def download_input_to_temp_file(url: str, suffix: str = ".jpg") -> Path:
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    temp_path = Path(path)
    temp_path.write_bytes(response.content)

    if temp_path.stat().st_size == 0:
        raise ValueError("Downloaded input media is empty")

    return temp_path


def real_image_inference(inputs, model_urls: dict | None = None, model_version: str | None = None):
    tagger = get_tagger(model_urls, model_version)

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


def real_video_inference(inputs, model_urls: dict | None = None, model_version: str | None = None):
    tagger = get_tagger(model_urls, model_version)

    all_tags = Counter()
    detections = []

    for item in inputs:
        url = item.get("url")
        if not url:
            raise ValueError("Input item is missing url")

        source = item.get("source", "unknown")
        local_video_path = download_input_to_temp_file(url, suffix=".mp4")

        cap = cv2.VideoCapture(str(local_video_path))
        if not cap.isOpened():
            local_video_path.unlink(missing_ok=True)
            raise ValueError(f"Cannot open video: {local_video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frame_interval = max(int(round(fps)), 1) if fps > 0 else 30

            frame_count = 0
            sampled_count = 0
            max_sampled_frames = int(os.getenv("GCP_VIDEO_MAX_SAMPLED_FRAMES", "12"))

            while sampled_count < max_sampled_frames:
                success, frame = cap.read()
                if not success:
                    break

                if frame_count % frame_interval == 0:
                    timestamp_sec = None
                    if fps > 0:
                        timestamp_sec = round(frame_count / fps, 3)

                    result = tagger.tag_image(frame)
                    item_tags = result.get("tags", {})
                    all_tags.update(item_tags)

                    for detection in result.get("detections", []):
                        detections.append({
                            **detection,
                            "source": source,
                            "timestamp_sec": timestamp_sec,
                        })

                    sampled_count += 1

                frame_count += 1

            if sampled_count == 0:
                raise ValueError("No frames were extracted from video")
        finally:
            cap.release()
            try:
                local_video_path.unlink(missing_ok=True)
            except Exception:
                pass

    return {
        "tags": sorted(all_tags.keys()),
        "tag_counts": dict(all_tags),
        "detections": detections,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/debug-version":
            return json_response(self, 200, {
                "build_version": BUILD_VERSION,
                "video_support": True,
            })

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
            model_urls = payload.get("model_urls") or {}
            model_version = payload.get("model_version") or os.environ.get("GCP_MODEL_VERSION", "default")

            if not request_id:
                return json_response(self, 400, {"error": "Missing request_id"})

            if not media_hash:
                return json_response(self, 400, {"error": "Missing hash"})

            if media_type not in ["image", "video"]:
                return json_response(self, 400, {"error": "media_type must be image or video"})

            if not inputs:
                return json_response(self, 400, {"error": "At least one input is required"})

            if media_type == "image":
                inference_result = real_image_inference(inputs, model_urls, model_version)
            elif media_type == "video":
                inference_result = real_video_inference(inputs, model_urls, model_version)
            else:
                return json_response(self, 400, {"error": "media_type must be image or video"})

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
