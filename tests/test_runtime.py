import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from gesture.runtime import Camera


class RuntimeTests(unittest.TestCase):
    def test_inference_uses_smaller_frame_without_changing_preview(self):
        class Capture:
            def read(self):
                return True, np.zeros((480, 640, 3), dtype=np.uint8)

        class Detector:
            def detect_for_video(self, image, timestamp):
                self.shape = image.numpy_view().shape
                self.timestamp = timestamp
                return SimpleNamespace(hand_landmarks=[])

        class Image:
            def __init__(self, image_format, data):
                self.data = data

            def numpy_view(self):
                return self.data

        camera = Camera.__new__(Camera)
        camera.cap = Capture()
        camera.detector = Detector()
        camera.cfg = {'mirror': True, 'inference_width': 320}
        camera.timestamp = -1
        with patch('gesture.runtime.mp.Image', Image):
            now, frame, points = camera.read()
        self.assertEqual(camera.detector.shape, (240, 320, 3))
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertIsNone(points)
        self.assertGreaterEqual(camera.timestamp, 0)
        self.assertGreaterEqual(camera.capture_ms, 0)
        self.assertGreaterEqual(camera.infer_ms, 0)
