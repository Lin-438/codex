"""Camera-independent recognition; coordinates refer to the displayed (mirrored) image."""
import math
import numpy as np

LABELS = ['left', 'right', 'open', 'fist', 'idle']


def features(points):
    p = np.asarray(points, dtype=float)
    center = p[[0, 5, 9, 13, 17], :2].mean(axis=0)
    scale = max(np.linalg.norm(p[9] - p[0]), 1e-6)
    relative = (p - p[0]) / scale
    # Distance ratio is rotation tolerant and does not depend on handedness.
    extended = [np.linalg.norm(p[tip] - p[0]) > 1.25 * np.linalg.norm(p[pip] - p[0])
                for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]]
    pose = 'open' if all(extended) else ('fist' if not any(extended) else 'idle')
    return center, relative, pose


def trajectory(samples):
    xy = np.array([s['center'] for s in samples], dtype=float)
    return xy - xy[0]


def dtw(a, b):
    a, b = np.asarray(a), np.asarray(b)
    costs = np.full((len(a)+1, len(b)+1), np.inf)
    costs[0, 0] = 0
    for i in range(1, len(a)+1):
        for j in range(1, len(b)+1):
            costs[i, j] = np.linalg.norm(a[i-1]-b[j-1]) + min(costs[i-1,j], costs[i,j-1], costs[i-1,j-1])
    return float(costs[-1,-1] / max(len(a), len(b)))


def classify(samples, cfg, templates=None):
    if len(samples) < 3:
        return 'idle'
    a = trajectory(samples)
    dx, dy = a[-1]
    distance = np.abs(np.diff(a[:,0])).sum()
    valid = (abs(dx) >= cfg['min_swipe'] and np.ptp(a[:,1]) <= cfg['max_vertical']
             and abs(dx) / max(distance, 1e-6) >= .8)
    if not valid:
        return 'idle'
    if cfg['method'] == 'dtw':
        candidates = [(dtw(a, x['trajectory']), x['label']) for x in (templates or [])]
        if not candidates:
            return 'idle'
        score, label = min(candidates)
        return label if score <= cfg['dtw_threshold'] else 'idle'
    return 'right' if dx > 0 else 'left'


class Controller:
    def __init__(self, cfg, templates=None):
        self.cfg, self.templates = cfg, templates
        self.enabled = False
        self.last_command = -math.inf
        self.reset()

    def reset(self):
        self.pose = None
        self.pose_since = None
        self.anchor = None
        self.still_since = None
        self.armed = False
        self.action = []
        self.last_center = None
        self.last_time = None

    def update(self, t, points):
        c = self.cfg
        if points is None:
            self.reset()  # never finish a gesture after tracking loss
            return None
        if self.last_time is not None and (t <= self.last_time or t-self.last_time > .25):
            self.reset()
        self.last_time = t
        center, relative, pose = features(points)
        sample = {'t': t, 'center': center.tolist(), 'relative': relative.tolist()}
        if pose != self.pose:
            self.pose, self.pose_since = pose, t
        if pose in ('open','fist') and t-self.pose_since >= c['hold_seconds']:
            desired = pose == 'open'
            if self.enabled != desired:
                self.enabled = desired
                self.reset()
                return 'enabled' if desired else 'paused'
        if not self.enabled or pose != 'open' or t-self.last_command < c['cooldown_seconds']:
            self.anchor = None
            self.armed = False
            self.action = []
            self.still_since = None
            return None
        if self.anchor is None:
            self.anchor = sample
            self.still_since = t
        delta = np.linalg.norm(center - np.array(self.anchor['center']))
        if not self.action:
            if not self.armed:
                if delta > c['motion_end']:
                    self.anchor, self.still_since = sample, t
                elif t-self.still_since >= c['stable_seconds']:
                    self.armed = True
            elif delta >= c['motion_start']:
                self.action = [dict(self.anchor, t=t), sample]
                self.still_since = t
        else:
            self.action.append(sample)
            # Ending requires a stable interval, measured against a fixed endpoint.
            if self.last_center is None or np.linalg.norm(center-self.last_center) > c['motion_end']:
                self.last_center = center.copy()
                self.still_since = t
            if t-self.action[0]['t'] > c['max_action_seconds']:
                self.reset()
            elif t-self.still_since >= c['stable_seconds']:
                label = classify(self.action, c, self.templates)
                self.reset()
                if label != 'idle':
                    self.last_command = t
                    return label
        return None
