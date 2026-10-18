import argparse
import json
import sys
import time
import cv2
from gesture.core import Controller
from gesture.runtime import Camera, load_config, send_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--camera',type=int)
    parser.add_argument('--control',action='store_true')
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.camera is not None:
        cfg['camera'] = args.camera
    if args.control and sys.platform != 'win32':
        parser.error('--control requires Windows')
    templates = None
    if cfg['method'] == 'dtw':
        templates = json.load(open(cfg['templates'],encoding='utf-8'))
        if not templates:
            raise ValueError('Empty DTW template set')
    recognizer = Controller(cfg, templates)
    camera = Camera(cfg)
    result, until, previous = 'none',0,time.monotonic()
    try:
        while True:
            now, frame, points = camera.read()
            command = recognizer.update(now,points)
            if command:
                result,until = command,now+1.5
                if args.control and command in ('left','right'):
                    send_key(command)
            fps = 1/max(now-previous,1e-6)
            previous = now
            lines = [f"{'CONTROL' if args.control else 'DEMO'} | {'ENABLED' if recognizer.enabled else 'PAUSED'} | FPS {fps:.1f}",
                     f"Hand: {'tracked' if points else 'missing'} | Result: {result if now < until else 'none'}",
                     'Open palm: enable / fist: pause / Q or Esc: exit']
            for i,line in enumerate(lines):
                cv2.putText(frame,line,(12,28+28*i),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,220,30),2)
            cv2.imshow('Gesture presentation',frame)
            if cv2.waitKey(1)&255 in (27,ord('q')) or cv2.getWindowProperty('Gesture presentation',cv2.WND_PROP_VISIBLE)<1:
                break
    finally:
        camera.close()


if __name__ == '__main__':
    main()
