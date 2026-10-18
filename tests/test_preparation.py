"""Regression checks for one small preparation before a completed swipe."""
import unittest
from unittest.mock import patch

import numpy as np

from gesture.core import Controller, classify, direction_quality, trajectory
from test_core import CFG, hand


def samples(knots, subdivisions=7):
    """Interpolate knots so validation exercises sampled trajectories."""
    x = np.concatenate([
        np.linspace(a, b, subdivisions, endpoint=False)
        for a, b in zip(knots, knots[1:])
    ] + [np.array([knots[-1]])])
    return [{'center': [float(v), 0.0]} for v in x]


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(CFG, stable_seconds=.30, max_vertical=.20)

    def test_single_small_preparation_in_both_directions(self):
        for sign, label in [(1, 'left'), (-1, 'right')]:
            with self.subTest(label=label):
                clip = samples(np.array([0, .07, -.13]) * sign)
                self.assertEqual(classify(clip, self.cfg), label)
                quality, preparation = direction_quality(clip, .12)
                self.assertAlmostEqual(quality, 1.0)
                self.assertAlmostEqual(preparation, .07)

    def test_reversals_and_insufficient_net_displacement_are_rejected(self):
        cases = {
            'opposite_swipe_already_command_sized': [0, .13, -.16],
            'insufficient_net_displacement': [0, .08, -.10],
            'preparation_changes_direction': [0, -.08, .08, -.16],
            'main_movement_changes_direction': [0, .08, -.18, .03, -.14],
            'complete_return': [0, .16, 0],
        }
        for name, knots in cases.items():
            for sign in [-1, 1]:
                with self.subTest(case=name, sign=sign):
                    self.assertEqual(classify(samples(np.array(knots)*sign), self.cfg), 'idle')

    def test_preparation_cannot_reach_minimum_command_amplitude(self):
        for sign, label in [(1, 'left'), (-1, 'right')]:
            for preparation, expected in [(.119, label), (.12, 'idle'), (.121, 'idle')]:
                with self.subTest(sign=sign, preparation=preparation):
                    clip = samples(np.array([0, preparation, -.13])*sign)
                    self.assertEqual(classify(clip, self.cfg), expected)

    def test_vertical_bound_still_applies_to_entire_clip(self):
        for sign in [-1, 1]:
            clip = samples(np.array([0, .07, -.13])*sign)
            # A vertical excursion during the preparation cannot be discarded.
            clip[3]['center'][1] = .21
            self.assertEqual(classify(clip, self.cfg), 'idle')

    def test_extreme_plateau_and_stationary_clip(self):
        for sign, label in [(1, 'left'), (-1, 'right')]:
            clip = samples(np.array([0, .07, .07, .07, -.13])*sign)
            self.assertEqual(classify(clip, self.cfg), label)
        still = samples([0, 0, 0])
        self.assertEqual(direction_quality(still, .12), (0.0, 0.0))
        self.assertEqual(classify(still, self.cfg), 'idle')

    def test_main_segment_needs_at_least_three_samples(self):
        for sign, label in [(1, 'left'), (-1, 'right')]:
            # The two-sample main segment must not qualify via preparation.
            short = samples(np.array([0, .07, -.13])*sign, subdivisions=1)
            self.assertEqual(classify(short, self.cfg), 'idle')
            enough = samples(np.array([0, .07, -.03, -.13])*sign, subdivisions=1)
            self.assertEqual(classify(enough, self.cfg), label)

    def test_preparation_quality_threshold(self):
        for sign, label in [(1, 'left'), (-1, 'right')]:
            for quality, expected in [(.79, 'idle'), (.81, label)]:
                # Prefix: 0 -> -wobble -> .08. Its net/path is quality.
                wobble = (.08/quality - .08)/2
                clip = samples(np.array([0, -wobble, .08, -.13])*sign)
                self.assertEqual(classify(clip, self.cfg), expected)

    def test_dtw_receives_complete_original_trajectory(self):
        clip = samples([0, .07, -.13])
        original = trajectory(clip).copy()
        template = original.tolist()
        with patch('gesture.core.dtw', return_value=0.0) as matcher:
            result = classify(clip, dict(self.cfg, method='dtw'),
                              [{'label': 'left', 'trajectory': template}])
        self.assertEqual(result, 'left')
        self.assertEqual(matcher.call_count, 1)
        np.testing.assert_array_equal(matcher.call_args.args[0], original)
        self.assertEqual(matcher.call_args.args[1], template)
        np.testing.assert_array_equal(trajectory(clip), original)

    def test_controller_triggers_once_and_ignores_return_during_cooldown(self):
        for sign, expected in [(1, ['left', 'right']), (-1, ['right', 'left'])]:
            with self.subTest(sign=sign):
                controller = Controller(self.cfg)
                controller.enabled = True
                # First swipe, return during cooldown, stable rearm, then opposite swipe.
                times = [0, .5, .7, 1.2, 1.7, 1.95, 3.3, 3.5, 4.0, 5.0]
                offsets = np.array([0, 0, .07, -.14, -.14, 0, 0, -.07, .15, .15])*sign
                events = []
                for i in range(151):
                    t = i/30
                    event = controller.update(t, hand(.5+np.interp(t, times, offsets)))
                    if event:
                        events.append((t, event))
                self.assertEqual([event for _, event in events], expected)
                self.assertGreaterEqual(events[1][0]-events[0][0], self.cfg['cooldown_seconds'])

    def test_controller_tracking_loss_cancels_prepared_swipe(self):
        for sign in [-1, 1]:
            controller = Controller(self.cfg)
            controller.enabled = True
            times = [0, .5, .7, 1.1]
            offsets = np.array([0, 0, .07, -.14])*sign
            events = []
            for i in range(34):
                t = i/30
                event = controller.update(t, hand(.5+np.interp(t, times, offsets)))
                if event:
                    events.append(event)
            self.assertTrue(controller.action)
            self.assertIsNone(controller.update(34/30, None))
            self.assertEqual(controller.last_attempt, 'tracking lost')
            self.assertFalse(controller.action)
            for i in range(35, 85):
                event = controller.update(i/30, hand(.5-.14*sign))
                if event:
                    events.append(event)
            self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
