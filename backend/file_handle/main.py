from schema import ImageRequest, ImageResponse
import cv2
import base64
import numpy as np

def decode(image_base64: str) -> np.ndarray:
    img_bytes = base64.b64decode(image_base64)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

def create_image_response(image: ImageRequest) -> ImageResponse:
    decoded = decode(image.image)
    
