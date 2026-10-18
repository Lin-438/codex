import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import time
import cv2
from gesture.core import Controller, features
from gesture.runtime import Camera, load_config, send_key


def draw_motion_guide(frame, recognizer, points):
    if points is None:
        return
    center, _, _ = features(points)
    height, width = frame.shape[:2]
    current = (round(center[0]*width), round(center[1]*height))
    cv2.circle(frame, current, 8, (255,255,255), 2)
    cv2.putText(frame, 'PALM', (current[0]+10, current[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
    start = (recognizer.action[0] if recognizer.action else
             recognizer.anchor if recognizer.armed else None)
    if start is None:
        return
    x, y = start['center']
    origin = (round(x*width), round(y*height))
    cv2.circle(frame, origin, 4, (255,180,0), 2)
    cv2.line(frame, origin, current, (255,180,0), 2)
    for label, direction in [('L',-1), ('R',1)]:
        target_x = round((x+direction*recognizer.cfg['min_swipe'])*width)
        cv2.line(frame, (target_x,origin[1]-18), (target_x,origin[1]+18),
                 (255,180,0), 2)
        cv2.putText(frame, label, (target_x-5,origin[1]-22),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, (255,180,0), 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--camera',type=int)
    parser.add_argument('--backend',choices=['auto','dshow','msmf'],
                        help='Windows camera backend; dshow often exposes manual exposure')
    parser.add_argument('--exposure',type=float,
                        help='Manual camera exposure, e.g. -7 with DirectShow; device dependent')
    parser.add_argument('--gain',type=float,
                        help='Camera sensor gain; range and support depend on the driver')
    parser.add_argument('--gamma',type=float,
                        help='Software brightening before detection; below 1 is brighter')
    parser.add_argument('--width',type=int,help='Requested capture width')
    parser.add_argument('--height',type=int,help='Requested capture height')
    parser.add_argument('--inference-width',type=int,
                        help='Resize frames for hand detection; 320 can improve CPU speed')
    parser.add_argument('--control',action='store_true')
    parser.add_argument('--trace', metavar='PATH',
                        help='Record keypoints and decisions as JSONL; no images; refuses overwrite')
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.camera is not None:
        cfg['camera'] = args.camera
    if args.backend is not None:
        cfg['camera_backend'] = args.backend
    if args.exposure is not None:
        cfg['camera_exposure'] = args.exposure
    if args.gain is not None:
        cfg['camera_gain'] = args.gain
    if args.gamma is not None:
        cfg['image_gamma'] = args.gamma
    for name in ('width','height','inference_width'):
        value = getattr(args,name)
        if value is not None:
            cfg[name] = value
    if args.control and sys.platform != 'win32':
        parser.error('--control requires Windows')
    templates = None
    if cfg['method'] == 'dtw':
        templates = json.load(open(cfg['templates'],encoding='utf-8'))
        if not templates:
            raise ValueError('Empty DTW template set')
    recognizer = Controller(cfg, templates)
    with ExitStack() as resources:
        trace = None
        if args.trace:
            path = Path(args.trace)
            path.parent.mkdir(parents=True, exist_ok=True)
            trace = resources.enter_context(path.open('x', encoding='utf-8'))
            trace.write(json.dumps({'type':'meta', 'schema':1, 'config':cfg,
                                   'mode':'control' if args.control else 'demo'},
                                  allow_nan=False) + '\n')
            trace.flush()
            print(f'Recording keypoints and decisions to {path}; Q finishes recording', flush=True)
        camera = Camera(cfg)
        resources.callback(camera.close)
        result, previous = 'none',time.monotonic()
        trace_start = None
        while True:
            now, frame, points = camera.read()
            previous_attempt_at = recognizer.last_attempt_at
            command = recognizer.update(now,points)
            new_attempt = (recognizer.last_attempt
                           if recognizer.last_attempt_at != previous_attempt_at else None)
            if new_attempt is not None:
                print(f'Motion: {new_attempt}', flush=True)
            if command:
                result = command
                print(f'Gesture: {command}', flush=True)
            fps = 1/max(now-previous,1e-6)
            previous = now
            phase = ('PAUSED' if not recognizer.enabled else
                     'COOLDOWN' if now-recognizer.last_command < cfg['cooldown_seconds'] else
                     'MOVING' if recognizer.action else
                     'READY' if recognizer.armed else 'HOLD STILL')
            if trace is not None:
                if trace_start is None:
                    trace_start = now
                trace.write(json.dumps({'type':'frame', 't':now-trace_start,
                                        'points':points, 'event':command,
                                        'phase':phase, 'attempt':new_attempt},
                                       allow_nan=False) + '\n')
                trace.flush()
            if args.control and command in ('left','right'):
                send_key(command)
                print(f'Key: {command} accepted by Windows', flush=True)
            draw_motion_guide(frame, recognizer, points)
            if recognizer.action:
                dx = (recognizer.action[-1]['center'][0]
                      - recognizer.action[0]['center'][0])
                attempt = f'Motion dx={dx:+.2f} / {cfg["min_swipe"]:.2f}'
            elif recognizer.last_attempt is not None:
                attempt = f'Last motion: {recognizer.last_attempt}'
            else:
                attempt = 'Last motion: none'
            lines = [f"{'CONTROL' if args.control else 'DEMO'} | {'ENABLED' if recognizer.enabled else 'PAUSED'} | FPS {fps:.1f}",
                     f"Capture {camera.capture_ms:.0f} ms | Detect {camera.infer_ms:.0f} ms",
                     f"Hand: {'tracked' if points else 'missing'} | Pose: {recognizer.pose or 'none'} | {phase}",
                     f'Last event: {result}', attempt,
                     'Open palm: enable / fist: pause / Q or Esc: exit']
            for i,line in enumerate(lines):
                cv2.putText(frame,line,(12,28+28*i),cv2.FONT_HERSHEY_SIMPLEX,
                            .52 if i == 4 else .6,(255,220,30),2)
            cv2.imshow('Gesture presentation',frame)
            if cv2.waitKey(1)&255 in (27,ord('q')) or cv2.getWindowProperty('Gesture presentation',cv2.WND_PROP_VISIBLE)<1:
                break


if __name__ == '__main__':
    main()
