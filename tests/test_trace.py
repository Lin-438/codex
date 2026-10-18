import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import tools


def meta(**changes):
    return dict({'type': 'meta', 'schema': 1, 'config': {'mirror': True}, 'mode': 'control'}, **changes)


def frame(t, x=None, y=.4, **changes):
    points = None if x is None else [[x, y, 0.] for _ in range(21)]
    return dict({'type': 'frame', 't': t, 'points': points, 'event': None,
                 'phase': 'READY', 'attempt': None}, **changes)


def write_trace(path, records):
    path.write_text(''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')


class TraceTests(unittest.TestCase):
    def test_statistics_keep_segments_separate_and_do_not_infer_intent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.jsonl'
            write_trace(path, [meta(), frame(0, .2, event='enabled'),
                              frame(.1, .3, .5, event='right', attempt='right dx=+0.13'),
                              frame(.2, phase='HOLD STILL', attempt='tracking lost'),
                              frame(.3, .8, .7),
                              frame(.4, .6, .6, event='left', attempt='left dx=-0.20')])
            # Inspection does not need MediaPipe, the camera, or the key sender.
            with mock.patch.dict(sys.modules, {'gesture.runtime': None}):
                report = tools.summarize_trace(path)
        self.assertEqual(report['frames'], 5)
        self.assertAlmostEqual(report['duration_seconds'], .4)
        self.assertAlmostEqual(report['average_fps'], 10)
        self.assertEqual(report['missing_frames'], 1)
        self.assertAlmostEqual(report['missing_ratio'], .2)
        self.assertEqual(report['event_counts'], {'enabled': 1, 'paused': 0, 'left': 1, 'right': 1})
        self.assertEqual(report['attempts'], [{'t': .1, 'text': 'right dx=+0.13'},
                                             {'t': .2, 'text': 'tracking lost'},
                                             {'t': .4, 'text': 'left dx=-0.20'}])
        first, second = report['tracked_segments']
        self.assertEqual(first['frames'], 2)
        self.assertAlmostEqual(first['x_range'], .1)
        self.assertAlmostEqual(first['y_range'], .1)
        self.assertAlmostEqual(second['x_range'], .2)
        self.assertAlmostEqual(second['y_range'], .1)
        self.assertAlmostEqual(second['start_seconds'], .3)
        self.assertNotIn('accuracy', report)
        self.assertIn('不是识别准确率', report['note'])

    def test_single_missing_frame_has_no_fps_or_tracked_segment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.jsonl'
            write_trace(path, [meta(), frame(0)])
            report = tools.summarize_trace(path)
        self.assertIsNone(report['average_fps'])
        self.assertEqual(report['duration_seconds'], 0)
        self.assertEqual(report['missing_ratio'], 1)
        self.assertEqual(report['tracked_segments'], [])

    def test_rejects_corrupt_or_incomplete_records(self):
        no_points = frame(0)
        del no_points['points']
        no_schema = meta()
        del no_schema['schema']
        invalid_traces = {
            'empty': [],
            'no_frames': [meta()],
            'no_meta': [frame(0)],
            'no_schema': [no_schema, frame(0)],
            'unknown_schema': [meta(schema=2), frame(0)],
            'boolean_schema': [meta(schema=True), frame(0)],
            'bad_config': [meta(config=[]), frame(0)],
            'bad_mode': [meta(mode='anything'), frame(0)],
            'duplicate_time': [meta(), frame(0), frame(0)],
            'decreasing_time': [meta(), frame(.2), frame(.1)],
            'negative_time': [meta(), frame(-1)],
            'boolean_time': [meta(), frame(True)],
            'nan_time': [meta(), frame(float('nan'))],
            'infinite_time': [meta(), frame(float('inf'))],
            'missing_points_field': [meta(), no_points],
            'wrong_point_count': [meta(), frame(0, points=[[0, 0, 0]] * 20)],
            'wrong_point_dimension': [meta(), frame(0, points=[[0, 0]] * 21)],
            'string_coordinate': [meta(), frame(0, points=[['0', 0, 0]] * 21)],
            'boolean_coordinate': [meta(), frame(0, points=[[True, 0, 0]] * 21)],
            'infinite_coordinate': [meta(), frame(0, points=[[float('inf'), 0, 0]] * 21)],
            'unknown_event': [meta(), frame(0, event='enable')],
            'bad_event_type': [meta(), frame(0, event=[])],
            'unknown_phase': [meta(), frame(0, phase='unknown')],
            'bad_attempt': [meta(), frame(0, attempt=3)],
            'duplicate_meta': [meta(), frame(0), meta()],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.jsonl'
            for name, records in invalid_traces.items():
                with self.subTest(name=name):
                    write_trace(path, records)
                    with self.assertRaises(ValueError):
                        tools.summarize_trace(path)
            path.write_text('{"type":', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'line 1'):
                tools.summarize_trace(path)

    def test_cli_stdout_matches_optional_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.jsonl'
            output = Path(temp) / 'reports' / 'summary.json'
            write_trace(path, [meta(), frame(0, .5), frame(.1, .6)])
            result = subprocess.run([sys.executable, str(Path(tools.__file__).resolve()),
                                     'inspect-trace', '--input', str(path), '--output', str(output)],
                                    capture_output=True, text=True, encoding='utf-8', check=True)
            self.assertEqual(json.loads(result.stdout), json.loads(output.read_text(encoding='utf-8')))
            # The report is also emitted when no output file was requested.
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                tools.inspect_trace(SimpleNamespace(input=path, output=None))
            self.assertEqual(json.loads(stdout.getvalue())['frames'], 2)

    def test_summary_cannot_replace_original_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'trace.jsonl'
            write_trace(path, [meta(), frame(0, .5)])
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                tools.inspect_trace(SimpleNamespace(input=path, output=path))
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
