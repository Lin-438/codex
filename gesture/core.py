"""Camera-independent recognition; coordinates refer to the displayed (mirrored) image."""
import math
import numpy as np

LABELS = ['left', 'right', 'open', 'fist', 'idle']
MIN_STRAIGHTNESS = .8


def features(points):
    p = np.asarray(points, dtype=float)
    center = p[[0, 5, 9, 13, 17], :2].mean(axis=0)
    scale = max(np.linalg.norm(p[9] - p[0]), 1e-6)
    relative = (p - p[0]) / scale
    # Distance ratio is rotation tolerant and does not depend on handedness.
    extended = [np.linalg.norm(p[tip] - p[0]) > 1.25 * np.linalg.norm(p[pip] - p[0])
                for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]]
    # A briefly curled or occluded finger should not cancel an otherwise open hand.
    count = sum(extended)
    pose = 'open' if count >= 3 else ('fist' if count == 0 else 'idle')
    return center, relative, pose


def trajectory(samples):
    xy = np.array([s['center'] for s in samples], dtype=float)
    return xy - xy[0]


def motion_metrics(samples):
    a = trajectory(samples)
    dx = float(a[-1, 0])
    vertical = float(np.ptp(a[:, 1]))
    horizontal_path = float(np.abs(np.diff(a[:, 0])).sum())
    straightness = abs(dx) / max(horizontal_path, 1e-6)
    return dx, vertical, straightness


def direction_quality(samples, min_swipe):
    """Allow one small preparation before a consistent main movement.

    Full-clip displacement and vertical bounds are checked separately. A
    preparation cannot itself reach command amplitude; both parts must be
    directionally consistent. The original trajectory is never modified.
    """
    dx, _, straightness = motion_metrics(samples)
    if straightness >= MIN_STRAIGHTNESS or dx == 0:
        return straightness, 0.0
    x = trajectory(samples)[:, 0]
    direction = 1 if dx > 0 else -1
    # Split only at the extreme opposite to the final direction, not an
    # arbitrary favorable sub-clip that could hide later back-and-forth motion.
    split = int(np.argmin(direction*x))
    preparation = float(-direction*x[split])
    if preparation <= 0 or preparation >= min_swipe or len(x)-split < 3:
        return straightness, 0.0
    prefix_path = float(np.abs(np.diff(x[:split+1])).sum())
    main_path = float(np.abs(np.diff(x[split:])).sum())
    prefix_quality = preparation / max(prefix_path, 1e-6)
    main_quality = abs(float(x[-1]-x[split])) / max(main_path, 1e-6)
    if prefix_quality >= MIN_STRAIGHTNESS and main_quality >= MIN_STRAIGHTNESS:
        return main_quality, preparation
    return straightness, 0.0


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
    dx, vertical, _ = motion_metrics(samples)
    quality, _ = direction_quality(samples, cfg['min_swipe'])
    valid = (abs(dx) >= cfg['min_swipe'] and vertical <= cfg['max_vertical']
             and quality >= MIN_STRAIGHTNESS)
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
        self.last_attempt = None
        self.last_attempt_at = -math.inf
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
        self.last_open_time = None

    def update(self, t, points):
        c = self.cfg
        if points is None:
            if self.action:
                self.last_attempt, self.last_attempt_at = 'tracking lost', t
            self.reset()  # never finish a gesture after tracking loss
            return None
        if self.last_time is not None and (t <= self.last_time or
                                           t-self.last_time > c.get('max_frame_gap_seconds', .6)):
            if self.action:
                self.last_attempt, self.last_attempt_at = 'frame gap', t
            self.reset()
        self.last_time = t
        center, relative, pose = features(points)
        sample = {'t': t, 'center': center.tolist(), 'relative': relative.tolist()}
        if pose == 'open':
            self.last_open_time = t
        if pose != self.pose:
            self.pose, self.pose_since = pose, t
        if pose in ('open','fist') and t-self.pose_since >= c['hold_seconds']:
            desired = pose == 'open'
            if self.enabled != desired:
                self.enabled = desired
                self.reset()
                return 'enabled' if desired else 'paused'
        open_enough = pose == 'open' or (bool(self.action) and pose == 'idle'
                       and self.last_open_time is not None
                       and t-self.last_open_time <= c.get('pose_grace_seconds', .15))
        if not self.enabled or not open_enough or t-self.last_command < c['cooldown_seconds']:
            if self.action and not open_enough:
                self.last_attempt, self.last_attempt_at = 'hand shape changed', t
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
                self.last_attempt, self.last_attempt_at = 'motion timeout', t
                self.reset()
            elif t-self.still_since >= c['stable_seconds']:
                label = classify(self.action, c, self.templates)
                dx, vertical, _ = motion_metrics(self.action)
                quality, preparation = direction_quality(self.action, c['min_swipe'])
                self.last_attempt = (f'{label} dx={dx:+.2f}/{c["min_swipe"]:.2f} '
                                     f'y={vertical:.2f}/{c["max_vertical"]:.2f} '
                                     f'straight={quality:.2f}')
                if preparation:
                    self.last_attempt += f' prep={preparation:.2f}'
                self.last_attempt_at = t
                self.reset()
                if label != 'idle':
                    self.last_command = t
                    return label
        return None
