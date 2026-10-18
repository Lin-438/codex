import json
import time
from pathlib import Path
import cv2
import mediapipe as mp

EDGES = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(17,18),(18,19),(19,20),(0,17)]


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    for key in ['hold_seconds','stable_seconds','cooldown_seconds','min_swipe','max_vertical','motion_start','motion_end','max_action_seconds','dtw_threshold']:
        if cfg[key] <= 0:
            raise ValueError(f'{key} must be positive')
    if cfg['method'] not in ('rule','dtw'):
        raise ValueError('method must be rule or dtw')
    return cfg


class Camera:
    def __init__(self, cfg):
        if not Path(cfg['model']).is_file():
            raise FileNotFoundError('Model missing. Run: python tools.py download-model')
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=cfg['model']),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=1,
            min_hand_detection_confidence=cfg['min_detection_confidence'],
            min_tracking_confidence=cfg['min_tracking_confidence'])
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.cap = cv2.VideoCapture(cfg['camera'])
        self.cfg = cfg
        self.timestamp = -1
        if not self.cap.isOpened():
            self.close()
            raise RuntimeError('Cannot open camera; check camera number and permissions')

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError('Camera frame read failed')
        if self.cfg['mirror']:
            frame = cv2.flip(frame, 1)
        now = time.monotonic()
        self.timestamp = max(self.timestamp+1, int(now*1000))
        result = self.detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), self.timestamp)
        points = None
        if result.hand_landmarks:
            points = [[p.x,p.y,p.z] for p in result.hand_landmarks[0]]
            h,w = frame.shape[:2]
            xy = [(int(p[0]*w),int(p[1]*h)) for p in points]
            for a,b in EDGES:
                cv2.line(frame,xy[a],xy[b],(80,220,80),2)
            for p in xy:
                cv2.circle(frame,p,3,(0,180,255),-1)
        return now,frame,points

    def close(self):
        self.cap.release()
        self.detector.close()
        cv2.destroyAllWindows()


def send_key(command):
    # Windows SendInput does not activate or focus any window.
    import sys
    import ctypes
    from ctypes import wintypes
    if sys.platform != 'win32':
        raise RuntimeError('Actual presentation control is supported on Windows only')
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk',wintypes.WORD),('wScan',wintypes.WORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ctypes.c_size_t)]
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx',wintypes.LONG),('dy',wintypes.LONG),('mouseData',wintypes.DWORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ctypes.c_size_t)]
    class PAYLOAD(ctypes.Union):
        _fields_ = [('ki',KEYBDINPUT),('mi',MOUSEINPUT)]
    class INPUT(ctypes.Structure):
        _anonymous_ = ('u',)
        _fields_ = [('type',wintypes.DWORD),('u',PAYLOAD)]
    vk = {'left':0x25,'right':0x27}[command]
    events = (INPUT*2)()
    for i, flags in enumerate([0,2]):
        events[i].type = 1
        events[i].ki = KEYBDINPUT(vk,0,flags,0,0)
    fn = ctypes.windll.user32.SendInput
    fn.argtypes = [wintypes.UINT,ctypes.POINTER(INPUT),ctypes.c_int]
    fn.restype = wintypes.UINT
    if fn(2,events,ctypes.sizeof(INPUT)) != 2:
        raise RuntimeError('SendInput failed; check foreground application privilege level')
