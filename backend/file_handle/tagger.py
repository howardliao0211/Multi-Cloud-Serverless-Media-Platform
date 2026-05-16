import base64
import tempfile
from collections import Counter
from typing import Any

import cv2
import numpy as np
import torch
from pathlib import Path
from torchvision import transforms

from megadetector.detection import run_detector_batch


class ImageTagger:
    """
    Combined MegaDetector + image classifier pipeline.

    Pipeline:
        input image
        -> MegaDetector detects animal targets
        -> crop each detected target
        -> classifier predicts species/class for each crop
        -> return tags + bounding boxes
    """

    def __init__(
        self,
        classifier_model_path: str = "./model.pt",
        detector_model_path: str = "./mdv5a.pt",
        classifier_conf_thres: float = 0.5,
        detector_conf_thres: float = 0.2,
    ) -> None:

        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        print("Using device:", self.device)

        self.detector_model_path = detector_model_path
        self.detector_conf_thres = detector_conf_thres
        self.classifier_conf_thres = classifier_conf_thres

        self.classes = [
            "Alectura_lathami", "Antechinus_agilis", "Bos_taurus",
            "Burhinus_grallarius", "Canis_familiaris",
            "Chalcophaps_longirostris", "Colluricincla_harmonica",
            "Corcorax_melanorhamphos", "Dacelo_novaeguineae",
            "Dama_dama", "Eopsaltria_australis", "Felis_catus",
            "Geopelia_humeralis", "Gymnorhina_tibicen", "Homo_sapiens",
            "Isoodon_macrourus", "Lepus_europaeus", "Macropus_giganteus",
            "Menura_novaehollandiae", "Mus_musculus",
            "Oryctolagus_cuniculus", "Perameles_nasuta", "Pitta_versicolor",
            "Rattus", "Rattus_fuscipes", "Rattus_rattus",
            "Strepera_graculina", "Sus_scrofa", "Tachyglossus_aculeatus",
            "Thylogale_stigmatica", "Trichosurus_caninus",
            "Trichosurus_cunninghami", "Trichosurus_vulpecula",
            "Varanus_varius", "Vombatus_ursinus", "Vulpes_vulpes",
            "Wallabia_bicolor", "Canis_dingo", "Capra_hircus",
            "Casuarius_casuarius", "Heteromyias_cinereifrons",
            "Hypsiprymnodon_moschatus", "Megapodius_reinwardt",
            "Notamacropus_rufogriseus", "Orthonyx_spaldingii",
            "Uromys_caudimaculatus"
        ]

        self.classifier_model = torch.load(
            classifier_model_path,
            map_location=self.device,
            weights_only=False,
        )

        self.classifier_model.eval()
        self.classifier_model.to(self.device)

        self.transform = transforms.Compose([
            transforms.Resize((480, 480)),
            transforms.ToTensor(),
        ])

    def tag_image(self, image) -> dict[str, Any]:
        """
        Main function.

        Accepts:
            - file path: str
            - file path: Path
            - base64 image: str
            - OpenCV image array: np.ndarray

        Returns:
            {
                "tags": {"Macropus_giganteus": 2, ...},
                "detections": [
                    {
                        "bbox": [...],
                        "bbox_pixels": [...],
                        "detector_category": "1",
                        "detector_confidence": 0.91,
                        "classifier_tags": {"Macropus_giganteus": 1}
                    }
                ]
            }
        """
        image_array = self._load_image(image)

        # If image is an existing file path, run MegaDetector directly on file.
        # This avoids writing a temporary image file.
        if isinstance(image, Path):
            detections = self._run_detector_from_file(str(image), image_array)
        else:
            detections = self._run_detector_from_array(image_array)

        all_tags = Counter()
        detection_results = []

        for det in detections:
            crop = det["crop"]

            classifier_tags = self._classify_crop(crop)
            all_tags.update(classifier_tags)

            detection_results.append({
                "bbox": det["bbox"],
                "bbox_pixels": det["bbox_pixels"],
                "detector_category": det["category"],
                "detector_confidence": det["confidence"],
                "classifier_tags": dict(classifier_tags),
            })

        return {
            "tags": dict(all_tags),
            "detections": detection_results,
        }

    def _run_detector_from_file(
        self,
        image_path: str,
        image_array: np.ndarray,
    ) -> list[dict[str, Any]]:
        """
        Run MegaDetector directly on an existing image file.
        """
        results = run_detector_batch.load_and_run_detector_batch(
            image_file_names=[image_path],
            model_file=self.detector_model_path,
            quiet=True,
            verbose_output=False,
        )

        return self._parse_detector_results(results, image_array)

    def _run_detector_from_array(
        self,
        image_array: np.ndarray,
    ) -> list[dict[str, Any]]:
        """
        MegaDetector expects file paths, so ndarray/base64 input still needs
        a temporary file.

        Important:
            On Windows, NamedTemporaryFile can cause permission issues because
            the file remains open while cv2.imwrite tries to write to it.

            Therefore, this uses mkstemp, closes the file descriptor first,
            writes the image, runs the detector, then manually deletes the file.
        """
        tmp_path = None

        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            # Close the file descriptor so OpenCV can write to it on Windows.
            import os
            os.close(fd)

            success = cv2.imwrite(tmp_path, image_array)

            if not success:
                raise ValueError(
                    f"Failed to write temporary image for detector: {tmp_path}")

            results = run_detector_batch.load_and_run_detector_batch(
                image_file_names=[tmp_path],
                model_file=self.detector_model_path,
                quiet=True,
                verbose_output=False
            )

            return self._parse_detector_results(results, image_array)

        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _parse_detector_results(
        self,
        detector_results: dict[str, Any],
        image_array: np.ndarray,
    ) -> list[dict[str, Any]]:
        image_result = detector_results[0]
        raw_detections = image_result.get("detections", [])

        detections = []

        for det in raw_detections:
            confidence = float(det["conf"])
            category = str(det["category"])

            if confidence < self.detector_conf_thres:
                continue

            # MegaDetector categories:
            # "1" = animal
            # "2" = person
            # "3" = vehicle
            #
            # Since this classifier predicts animal/species classes,
            # we keep only animal detections.
            if category != "1":
                continue

            bbox = det["bbox"]
            crop, bbox_pixels = self._crop_bbox(image_array, bbox)

            if crop is None or crop.size == 0:
                continue

            detections.append({
                "crop": crop,
                "bbox": bbox,
                "bbox_pixels": bbox_pixels,
                "category": category,
                "confidence": confidence,
            })

        return detections

    @torch.no_grad()
    def _classify_crop(self, crop: np.ndarray) -> Counter[str]:
        if crop is None or crop.size == 0:
            return Counter()

        # OpenCV crop is BGR; convert to RGB.
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

        # Your working sample uses PIL.Image.open(...).convert("RGB"),
        # so we should convert the NumPy crop to a PIL image too.
        from PIL import Image
        img_pil = Image.fromarray(crop_rgb).convert("RGB")

        img = self.transform(img_pil)      # -> C,H,W
        img = img.unsqueeze(0)             # -> B,C,H,W

        # Important: your working sample does this.
        # The fine-tuned model expects channel-last input: B,H,W,C.
        img = img.permute(0, 2, 3, 1)      # -> B,H,W,C

        img = img.to(self.device)

        logits = self.classifier_model(img)
        probs = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()

        order = np.argsort(probs)[::-1]

        tags = []

        for idx in order:
            label = self.classes[idx]
            confidence = probs[idx]

            if confidence < self.classifier_conf_thres:
                break

            tags.append(label)

        return Counter(tags)

    def _crop_bbox(
        self,
        image: np.ndarray,
        bbox: list[float],
    ) -> tuple[np.ndarray | None, list[int]]:
        """
        MegaDetector bbox format:
            [x_min, y_min, width, height]

        Values are normalized between 0 and 1.
        """
        h, w = image.shape[:2]

        x, y, box_w, box_h = bbox

        x1 = int(x * w)
        y1 = int(y * h)
        x2 = int((x + box_w) * w)
        y2 = int((y + box_h) * h)

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None, [x1, y1, x2, y2]

        crop = image[y1:y2, x1:x2]

        return crop, [x1, y1, x2, y2]

    def _load_image(self, image) -> np.ndarray:
        """
        Load image from:
            - existing file path: str or Path
            - base64 string
            - OpenCV ndarray
        """
        if isinstance(image, Path):
            image_array = cv2.imread(str(image))

        elif isinstance(image, str):
            img_bytes = base64.b64decode(image)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            image_array = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        elif isinstance(image, np.ndarray):
            image_array = image

        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        if image_array is None:
            raise ValueError("Failed to load image")

        return image_array


if __name__ == "__main__":

    def encode(image: Path) -> str:
        image_array = cv2.imread(str(image))
        _, buffer = cv2.imencode(".jpg", image_array)
        return base64.b64encode(buffer).decode("utf-8")

    tagger = ImageTagger(
        classifier_model_path="./model.pt",
        detector_model_path="./mdv5a.pt",
        classifier_conf_thres=0.5,
        detector_conf_thres=0.2,
    )

    image_path = Path("./elephants.jpg")
    result = tagger.tag_image(image_path)

    print(result["tags"])
    print(result["detections"])

    image_base64 = encode(image_path)
    result = tagger.tag_image(image_base64)
    print(result["tags"])
    print(result["detections"])
