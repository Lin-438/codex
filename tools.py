"""Model acquisition, labeled recording, grouped splits, DTW templates, offline evaluation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import urllib.request
import numpy as np
from gesture.core import LABELS, Controller, classify, features, trajectory

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def download(args):
    path = Path(args.output)
    if path.exists():
        raise FileExistsError('Refusing to overwrite existing model')
    path.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(MODEL_URL,timeout=60) as response:
        blob = response.read()
    digest = hashlib.sha256(blob).hexdigest()
    if args.sha256 and digest != args.sha256.lower():
        raise ValueError('Model SHA256 mismatch')
    path.write_bytes(blob)
    print('Model downloaded over verified HTTPS; SHA256:',digest)


def collect(args):
    import cv2
    from gesture.runtime import Camera, load_config
    cfg = load_config(args.config)
    if args.camera is not None:
        cfg['camera'] = args.camera
    path = Path(args.output)
    if path.exists():
        raise FileExistsError(path)
    camera = Camera(cfg)
    samples = []
    start = None
    try:
        while True:
            t,frame,points = camera.read()
            if start is not None:
                if points is None:
                    sample = {'t':t-start,'points':None}
                else:
                    center,relative,pose = features(points)
                    sample = {'t':t-start,'points':points,'center':center.tolist(),'relative':relative.tolist(),'pose':pose}
                samples.append(sample)
            cv2.putText(frame,f'{args.label} | SPACE start | Q finish | {len(samples)} frames',(10,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
            cv2.imshow('Collect',frame)
            key = cv2.waitKey(1)&255
            if key == 32 and start is None:
                start = t
            if key in (27,ord('q')) or cv2.getWindowProperty('Collect',cv2.WND_PROP_VISIBLE)<1:
                break
    finally:
        camera.close()
    if not samples:
        raise ValueError('No recording; press SPACE first')
    save(path,{'schema':1,'person':args.person,'recording':args.recording,'label':args.label,
               'mirror':cfg['mirror'],'intent_start':args.intent_start,'samples':samples})
    print('Saved',path)


def split(args):
    records = [(p,json.loads(p.read_text(encoding='utf-8'))) for p in sorted(Path(args.data).glob('*.json'))]
    groups = sorted({r[args.group] for _,r in records})
    if len(groups)<3:
        raise ValueError('Need at least 3 distinct groups for train/val/test')
    rng = np.random.default_rng(args.seed)
    rng.shuffle(groups)
    ntest = max(1,round(len(groups)*.2))
    nval = max(1,round(len(groups)*.2))
    partitions = {'test':groups[:ntest],'val':groups[ntest:ntest+nval],'train':groups[ntest+nval:]}
    result = {k:[str(p.resolve()) for p,r in records if r[args.group] in v] for k,v in partitions.items()}
    result['_group'] = args.group
    save(args.output,result)


def read_partition(args):
    manifest = json.loads(Path(args.split).read_text(encoding='utf-8'))
    sets = {k:set(manifest[k]) for k in ('train','val','test')}
    group = manifest.get('_group', 'recording')
    group_sets = {k:{json.loads(Path(p).read_text(encoding='utf-8'))[group] for p in paths} for k,paths in sets.items()}
    for a,b in [('train','test'),('train','val'),('val','test')]:
        if sets[a]&sets[b] or group_sets[a]&group_sets[b]:
            raise ValueError('Overlapping recordings in manifest')
    return [json.loads(Path(p).read_text(encoding='utf-8')) for p in manifest[args.partition]]


def action_samples(record):
    # One clip = one labeled action, including a short stable start and finish.
    # Reject tracking loss rather than joining separated trajectories.
    if any(s['points'] is None for s in record['samples']):
        return []
    return record['samples']


def train(args):
    if args.partition != 'train':
        raise ValueError('Templates must use train partition only')
    records = read_partition(args)
    templates = [{'label':r['label'],'trajectory':trajectory(action_samples(r)).tolist(),
                  'person':r['person'],'recording':r['recording']}
                 for r in records if r['label'] in ('left','right') and len(action_samples(r))>=3]
    if {t['label'] for t in templates} != {'left','right'}:
        raise ValueError('Training needs tracked left and right clips')
    save(args.output,templates)


def predict(record,cfg,templates):
    samples = action_samples(record)
    if len(samples)<3:
        return 'idle'
    poses = [s['pose'] for s in samples]
    # Static class requires a contiguous hold, not a count of unrelated frames.
    for pose in ('open','fist'):
        begin = None
        for s,p in zip(samples,poses):
            begin = (s['t'] if begin is None else begin) if p==pose else None
            if begin is not None and s['t']-begin>=cfg['hold_seconds']:
                # Movement takes precedence over static open-palm posture.
                motion = classify(samples,cfg,templates)
                return motion if motion!='idle' else pose
    return classify(samples,cfg,templates)


def evaluate(args):
    from gesture.runtime import load_config
    cfg = load_config(args.config)
    records = read_partition(args)
    if not records:
        raise ValueError('Empty evaluation partition')
    templates = json.loads(Path(args.templates).read_text(encoding='utf-8')) if args.templates else None
    if templates and args.partition != 'train':
        group = json.loads(Path(args.split).read_text(encoding='utf-8')).get('_group', 'recording')
        if {t[group] for t in templates} & {r[group] for r in records}:
            raise ValueError('Template/evaluation group leakage')
    report = {}
    for method in (['rule','dtw'] if templates else ['rule']):
        cfg['method'] = method
        matrix = np.zeros((5,5),dtype=int)
        successes = total = 0
        latencies, idle_seconds, false_commands = [],0,0
        for record in records:
            label = record['label']
            pred = predict(record,cfg,templates)
            matrix[LABELS.index(label),LABELS.index(pred)] += 1
            ctrl = Controller(cfg,templates)
            # Swipe clips model an already-enabled presentation; static enable/pause
            # clips start in the opposite state to measure their intended transition.
            ctrl.enabled = label != 'open'
            events = []
            for s in record['samples']:
                event = ctrl.update(s['t'],s['points'])
                if event:
                    events.append((s['t'],event))
            if label=='idle':
                idle_seconds += record['samples'][-1]['t']-record['samples'][0]['t']
                false_commands += sum(e in ('left','right') for _,e in events)
            else:
                total += 1
                target = {'open':'enabled','fist':'paused'}.get(label,label)
                matching = [t for t,e in events if e==target]
                success = len(matching)==1 and len(events)==1
                successes += int(success)
                if success and record.get('intent_start') is not None:
                    delay = matching[0]-record['intent_start']
                    if delay>=0:
                        latencies.append(delay)
        counts = matrix.sum(axis=1)
        report[method] = {'labels':LABELS,'confusion_rows_true_columns_pred':matrix.tolist(),
            'clips':int(matrix.sum()),'accuracy':float(np.trace(matrix)/matrix.sum()),
            'per_class_accuracy':{l:float(matrix[i,i]/counts[i]) if counts[i] else None for i,l in enumerate(LABELS)},
            'trigger_success_rate':successes/total if total else None,'trigger_successes':successes,'trigger_trials':total,
            'response_seconds_mean':float(np.mean(latencies)) if latencies else None,'response_samples':len(latencies),
            'idle_seconds':idle_seconds,'false_commands':false_commands,
            'false_commands_per_minute':false_commands/(idle_seconds/60) if idle_seconds else None}
    save(args.output,report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


def summarize_trace(path):
    """Inspect recorded observations only; never open hardware or send input."""
    meta = None
    frame_count = missing_count = 0
    first_time = last_time = None
    segments, attempts = [], []
    segment = None
    events = {name: 0 for name in ('enabled', 'paused', 'left', 'right')}
    phases = {'PAUSED', 'COOLDOWN', 'MOVING', 'READY', 'HOLD STILL'}

    def invalid(line, message):
        raise ValueError(f'Trace line {line}: {message}')

    def reject_constant(value):
        raise ValueError(f'Non-finite JSON number: {value}')

    def parse_finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f'Non-finite JSON number: {value}')
        return result

    def finite_number(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    with Path(path).open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line, parse_constant=reject_constant,
                                    parse_float=parse_finite_float)
            except ValueError as error:
                invalid(line_number, f'invalid JSON ({error})')
            if not isinstance(record, dict):
                invalid(line_number, 'expected a JSON object')
            if meta is None:
                if (record.get('type') != 'meta' or type(record.get('schema')) is not int
                        or record['schema'] != 1):
                    invalid(line_number, 'first record must be meta with schema 1')
                if not isinstance(record.get('config'), dict):
                    invalid(line_number, 'meta.config must be an object')
                if record.get('mode') not in ('demo', 'control'):
                    invalid(line_number, 'meta.mode must be demo or control')
                meta = record
                continue
            if record.get('type') != 'frame':
                invalid(line_number, 'expected a frame record')
            if not {'t', 'points', 'event', 'phase', 'attempt'} <= record.keys():
                invalid(line_number, 'missing required frame fields')
            t = record['t']
            if not finite_number(t) or t < 0 or (last_time is not None and t <= last_time):
                invalid(line_number, 'frame times must be finite, non-negative and strictly increasing')
            event = record['event']
            if event is not None and (not isinstance(event, str) or event not in events):
                invalid(line_number, 'unknown event')
            if not isinstance(record['phase'], str) or record['phase'] not in phases:
                invalid(line_number, 'unknown phase')
            attempt = record['attempt']
            if attempt is not None and not isinstance(attempt, str):
                invalid(line_number, 'attempt must be a string or null')
            points = record['points']
            if points is not None:
                if (not isinstance(points, list) or len(points) != 21
                        or any(not isinstance(p, list) or len(p) != 3
                               or not all(finite_number(v) for v in p) for p in points)):
                    invalid(line_number, 'points must be null or 21 rows of 3 finite numbers')
                # Match the controller's palm center without normalizing away motion.
                center = np.asarray(points, dtype=float)[[0, 5, 9, 13, 17], :2].mean(axis=0)
                if not np.isfinite(center).all():
                    invalid(line_number, 'palm center is not finite')
                x, y = map(float, center)
                if segment is None:
                    segment = {'start_seconds': t, 'end_seconds': t, 'frames': 0,
                               'x_min': x, 'x_max': x, 'y_min': y, 'y_max': y}
                    segments.append(segment)
                segment['end_seconds'] = t
                segment['frames'] += 1
                segment['x_min'] = min(segment['x_min'], x)
                segment['x_max'] = max(segment['x_max'], x)
                segment['y_min'] = min(segment['y_min'], y)
                segment['y_max'] = max(segment['y_max'], y)
            else:
                missing_count += 1
                segment = None
            if event is not None:
                events[event] += 1
            if attempt is not None:
                attempts.append({'t': t, 'text': attempt})
            frame_count += 1
            first_time = t if first_time is None else first_time
            last_time = t
    if meta is None:
        raise ValueError('Trace is empty or missing meta with schema 1')
    if not frame_count:
        raise ValueError('Trace contains no frames')
    for segment in segments:
        segment['duration_seconds'] = segment['end_seconds'] - segment['start_seconds']
        segment['x_range'] = segment['x_max'] - segment['x_min']
        segment['y_range'] = segment['y_max'] - segment['y_min']
    duration = last_time - first_time
    return {
        'schema': 1, 'kind': 'trace_summary', 'mode': meta['mode'], 'config': meta['config'],
        'note': ('仅为已记录关键点和程序事件的诊断统计，不包含动作意图标注，不是识别准确率。'
                 'tracked 段按相邻非空帧划分；掌心坐标为画面归一化坐标，范围不是一次动作的净位移，'
                 '不代表动作已通过判定；事件记录不能证明 Windows 已接收按键或 PPT 已翻页。'),
        'frames': frame_count, 'duration_seconds': duration,
        'average_fps': (frame_count - 1) / duration if duration else None,
        'missing_frames': missing_count, 'missing_ratio': missing_count / frame_count,
        'tracked_segments': segments, 'event_counts': events, 'attempts': attempts,
    }


def inspect_trace(args):
    if args.output and Path(args.output).resolve() == Path(args.input).resolve():
        raise ValueError('Summary output must differ from the input trace')
    report = summarize_trace(args.input)
    if args.output:
        save(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('download-model'); p.set_defaults(fn=download)
    p.add_argument('--output',default='models/hand_landmarker.task'); p.add_argument('--sha256')
    p = sub.add_parser('collect'); p.set_defaults(fn=collect)
    p.add_argument('--config',default='config.json'); p.add_argument('--camera',type=int)
    p.add_argument('--label',choices=LABELS,required=True); p.add_argument('--person',required=True)
    p.add_argument('--recording',required=True); p.add_argument('--output',required=True)
    p.add_argument('--intent-start',type=float,help='Seconds after SPACE; annotate actual intent onset offline')
    p = sub.add_parser('split'); p.set_defaults(fn=split)
    p.add_argument('--data',default='data/clips'); p.add_argument('--group',choices=['person','recording'],default='person')
    p.add_argument('--seed',type=int,default=42); p.add_argument('--output',default='data/split.json')
    p = sub.add_parser('inspect-trace'); p.set_defaults(fn=inspect_trace)
    p.add_argument('--input',required=True,help='JSONL trace recorded by app.py --trace')
    p.add_argument('--output',help='Also save the diagnostic JSON summary')
    for name,fn in [('train-dtw',train),('evaluate',evaluate)]:
        p = sub.add_parser(name); p.set_defaults(fn=fn)
        p.add_argument('--split',default='data/split.json')
        p.add_argument('--partition',choices=['train','val','test'],default='train' if name=='train-dtw' else 'test')
        p.add_argument('--output',default='data/templates.json' if name=='train-dtw' else 'reports/evaluation.json')
        if name=='evaluate':
            p.add_argument('--config',default='config.json'); p.add_argument('--templates')
    args = parser.parse_args()
    args.fn(args)


if __name__=='__main__':
    main()
