import cv2


class WebcamClient:
    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self.capture = None

    def open(self) -> None:
        self.capture = cv2.VideoCapture(self.camera_index)
        if not self.capture.isOpened():
            raise RuntimeError("Unable to open webcam.")

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        cv2.destroyAllWindows()

    def get_frame(self) -> bytes:
        if self.capture is None:
            raise RuntimeError("Webcam is not initialized.")

        success, frame = self.capture.read()
        if not success or frame is None:
            raise RuntimeError("Failed to capture webcam frame.")

        success, encoded = cv2.imencode('.jpg', frame)
        if not success:
            raise RuntimeError("Failed to encode webcam frame.")

        return encoded.tobytes()
