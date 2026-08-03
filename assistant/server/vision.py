import logging

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile

from assistant.server.models import VisionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=VisionResponse)
async def analyze_image(image: UploadFile = File(...)) -> VisionResponse:
    raw_bytes = await image.read()
    image_array = np.frombuffer(raw_bytes, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        logger.error("Failed to decode uploaded image.")
        raise HTTPException(status_code=400, detail="Unable to decode image. Upload a valid image file.")

    height, width = frame.shape[:2]
    return VisionResponse(width=width, height=height, message="Image received")
