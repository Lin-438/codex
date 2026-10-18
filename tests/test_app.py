import contextlib
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import app
from test_core import hand


class AppTests(unittest.TestCase):
    def test_same_swipe_only_sends_a_key_in_control_mode(self):
        frames = []
        for i in range(220):
            t = i / 30
            x = .4 + min(max(t - 1.5, 0), .5) * .5
            frames.append((t, object(), hand(x)))
        for control in (False, True):
            with self.subTest(control=control):
                camera = SimpleNamespace(read=Mock(side_effect=frames),
                                         close=Mock(), capture_ms=20, infer_ms=8)
                argv = ['app.py'] + (['--control'] if control else [])
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(app.sys, 'argv', argv))
                    stack.enter_context(patch.object(app.sys, 'platform', 'win32'))
                    stack.enter_context(patch.object(app.Camera, '__new__', return_value=camera))
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
