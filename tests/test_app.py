import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np

import app
from test_core import hand


class AppTests(unittest.TestCase):
    def test_same_swipe_only_sends_a_key_in_control_mode(self):
        frames = []
        preview = np.zeros((480,640,3), dtype=np.uint8)
        for i in range(220):
            t = i / 30
            x = .4 + min(max(t - 1.5, 0), .5) * .5
            frames.append((t, preview, hand(x)))
        for control in (False, True):
            with self.subTest(control=control):
                camera = SimpleNamespace(read=Mock(side_effect=frames),
                                         close=Mock(), capture_ms=20, infer_ms=8)
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                trace_path = Path(directory.name)/'trace.jsonl'
                argv = ['app.py', '--trace', str(trace_path)] + (['--control'] if control else [])
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(app.sys, 'argv', argv))
                    stack.enter_context(patch.object(app.sys, 'platform', 'win32'))
                    stack.enter_context(patch.object(app, 'Camera', return_value=camera))
                    stack.enter_context(patch.object(app.time, 'monotonic', return_value=0))
                    stack.enter_context(patch.object(app.cv2, 'imshow'))
                    draw = stack.enter_context(patch.object(app.cv2, 'putText'))
                    stack.enter_context(patch.object(app.cv2, 'getWindowProperty', return_value=1))
                    stack.enter_context(patch.object(app.cv2, 'waitKey',
                                                     side_effect=[-1] * (len(frames)-1) + [27]))
                    send = stack.enter_context(patch.object(app, 'send_key'))
                    stack.enter_context(contextlib.redirect_stdout(output))
                    app.main()
                camera.close.assert_called_once()
                if control:
                    send.assert_called_once_with('right')
                    self.assertIn('Key: right accepted by Windows', output.getvalue())
                else:
                    send.assert_not_called()
                    self.assertNotIn('Key:', output.getvalue())
                self.assertIn('Gesture: enabled', output.getvalue())
                self.assertIn('Gesture: right', output.getvalue())
                self.assertEqual(output.getvalue().count('Motion:'), 1)
                # Retain the result after the old three-second display timeout.
                final_lines = [call.args[1] for call in draw.call_args_list[-6:]]
                self.assertTrue(any('Last motion: right' in line for line in final_lines))
                records = [json.loads(line) for line in trace_path.read_text().splitlines()]
                self.assertEqual(records[0]['mode'], 'control' if control else 'demo')
                self.assertEqual(records[0]['schema'], 1)
                self.assertEqual(len(records), len(frames)+1)
                self.assertEqual(records[1]['t'], 0)
                self.assertEqual(records[1]['points'], frames[0][2])
                # Recording does not alter the recognizer's decisions and can be replayed.
                replay = app.Controller(records[0]['config'])
                for record in records[1:]:
                    self.assertEqual(replay.update(record['t'], record['points']), record['event'])

    def test_trace_refuses_to_overwrite_before_opening_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'existing.jsonl'
            path.write_text('existing recording', encoding='utf-8')
            with patch.object(app.sys, 'argv', ['app.py', '--trace', str(path)]), \
                 patch.object(app, 'Camera') as camera:
                with self.assertRaises(FileExistsError):
                    app.main()
                camera.assert_not_called()
            self.assertEqual(path.read_text(), 'existing recording')
