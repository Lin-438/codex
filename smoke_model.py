"""Headless real model inference check; requires the official .task file."""
import argparse
import numpy as np
import mediapipe as mp
from gesture.runtime import load_config

parser=argparse.ArgumentParser()
parser.add_argument('--config',default='config.json')
args=parser.parse_args()
cfg=load_config(args.config)
options=mp.tasks.vision.HandLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=cfg['model']),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=1)
with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
    for timestamp in (0,33,66):
        result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
            data=np.zeros((480,640,3),dtype=np.uint8)),timestamp)
        assert not result.hand_landmarks, 'Unexpected hand detected on blank frame'
print('PASS: CPU model initialization and three VIDEO inference calls (blank frames)')
