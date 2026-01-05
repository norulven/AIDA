"""Webcam integration for Aida."""

from pathlib import Path
import cv2
import numpy as np

from src.core.config import CameraConfig


class Camera:
    """Webcam capture and processing."""

    def __init__(self, config: CameraConfig):
        self.config = config
        self.capture: cv2.VideoCapture | None = None

    def open(self) -> bool:
        """Open the camera."""
        self.capture = cv2.VideoCapture(self.config.device_id)

        if not self.capture.isOpened():
            return False

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        return True

    def close(self) -> None:
        """Close the camera."""
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def is_open(self) -> bool:
        """Check if camera is open."""
        return self.capture is not None and self.capture.isOpened()

    def capture_frame(self) -> np.ndarray | None:
        """Capture a single frame."""
        if not self.is_open():
            if not self.open():
                return None

        ret, frame = self.capture.read()
        if ret:
            return frame
        return None

    def capture_photo(self, output_path: Path | str) -> bool:
        """Capture and save a photo."""
        frame = self.capture_frame()
        if frame is not None:
            cv2.imwrite(str(output_path), frame)
            return True
        return False

    def get_frame_base64(self) -> str | None:
        """Capture frame and return as base64 for LLM vision."""
        import base64

        frame = self.capture_frame()
        if frame is None:
            return None

        _, buffer = cv2.imencode(".jpg", frame)
        return base64.b64encode(buffer).decode("utf-8")

    def list_cameras(self) -> list[int]:
        """List available camera devices."""
        available = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
