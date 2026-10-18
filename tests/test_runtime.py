import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from gesture.runtime import Camera, make_gamma_lut


class RuntimeTests(unittest.TestCase):
    def test_inference_uses_smaller_frame_without_changing_preview(self):
        class Capture:
            def read(self):
                return True, np.full((480, 640, 3), 128, dtype=np.uint8)

        class Detector:
            def detect_for_video(self, image, timestamp):
                self.shape = image.numpy_view().shape
                self.pixel = int(image.numpy_view()[0, 0, 0])
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
        camera.gamma_lut = make_gamma_lut(.7)
        with patch('gesture.runtime.mp.Image', Image):
            now, frame, points = camera.read()
        self.assertEqual(camera.detector.shape, (240, 320, 3))
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertGreater(int(frame[0, 0, 0]), 128)
        self.assertEqual(camera.detector.pixel, int(frame[0, 0, 0]))
        self.assertIsNone(points)
        self.assertGreaterEqual(camera.timestamp, 0)
        self.assertGreaterEqual(camera.capture_ms, 0)
        self.assertGreaterEqual(camera.infer_ms, 0)

    def test_gamma_brightens_midtones_without_clipping_endpoints(self):
        lut = make_gamma_lut(.7)
        self.assertEqual(lut.shape, (256,))
        self.assertEqual(int(lut[0]), 0)
        self.assertGreater(int(lut[128]), 128)
        self.assertEqual(int(lut[255]), 255)
        with self.assertRaises(ValueError):
            make_gamma_lut(0)
