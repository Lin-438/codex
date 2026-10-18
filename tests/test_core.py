import json
import unittest
import numpy as np
from gesture.core import Controller, classify, dtw, features

CFG = json.load(open('config.json'))


def hand(x=.5, fist=False, bent=0):
    p = np.zeros((21,3))
    p[0] = [x,.7,0]
    for finger,(mcp,pip,dip,tip) in enumerate([(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]):
        xx = x+(mcp-9)*.006
        for idx,y in [(mcp,.58),(pip,.49),(dip,.42),(tip,.63 if fist or finger<bent else .35)]:
            p[idx] = [xx,y,0]
    return p.tolist()


class Tests(unittest.TestCase):
    def test_pose(self):
        self.assertEqual(features(hand())[2],'open')
        self.assertEqual(features(hand(bent=1))[2],'open')
        self.assertEqual(features(hand(bent=2))[2],'idle')
        self.assertEqual(features(hand(bent=3))[2],'idle')
        self.assertEqual(features(hand(fist=True))[2],'fist')

    def test_moderate_swipe_survives_one_unsteady_pose_frame(self):
        c = Controller(CFG)
        c.enabled = True
        events = []
        for i in range(90):
            t = i/30
            x = .3 + .14*min(max((t-.4)/.5, 0), 1)
            event = c.update(t, hand(x, bent=2 if i==25 else 0))
            if event:
                events.append(event)
        self.assertEqual(events, ['right'])

    def test_return_swing_does_not_trigger(self):
        c = Controller(CFG)
        c.enabled = True
        events = []
        for i in range(90):
            t = i/30
            if t < .4:
                x = .3
            elif t < .7:
                x = .3 + .16*(t-.4)/.3
            elif t < 1.0:
                x = .46 - .16*(t-.7)/.3
            else:
                x = .3
            event = c.update(t, hand(x))
            if event:
                events.append(event)
        self.assertEqual(events, [])

    def test_swipe_once_and_loss(self):
        c = Controller(CFG)
        events = []
        for i in range(220):
            t=i/30
            x=.4 if t<1.5 else (.4+min(t-1.5,.5)*.5)
            event=c.update(t,hand(x))
            if event: events.append(event)
        self.assertEqual(events,['enabled','right'])
        c.update(8,None)
        self.assertFalse(c.armed)
        self.assertEqual(c.action,[])

    def test_pause(self):
        c=Controller(CFG); c.enabled=True
        events=[c.update(i/30,hand(fist=True)) for i in range(40)]
        self.assertEqual([e for e in events if e],['paused'])
        self.assertFalse(c.enabled)

    def test_jitter_and_paused(self):
        c=Controller(CFG)
        for i in range(120):
            event=c.update(i/30,hand(.5+.005*np.sin(i)))
            self.assertNotIn(event,('left','right'))
        c=Controller(CFG)
        for i in range(15):
            self.assertIsNone(c.update(i/30,hand(.2+i*.03)))

    def test_rule_dtw(self):
        samples=[{'center':[i*.02,0]} for i in range(15)]
        self.assertEqual(classify(samples,CFG),'right')
        reverse=[{'center':[-i*.02,0]} for i in range(15)]
        self.assertEqual(classify(reverse,CFG),'left')
        cfg=dict(CFG,method='dtw')
        templates=[{'label':'right','trajectory':[[i*.02,0] for i in range(15)]}]
        self.assertEqual(classify(samples,cfg,templates),'right')
        self.assertAlmostEqual(dtw([[0,0],[1,0]],[[0,0],[1,0]]),0)

    def test_tracking_loss_cancels(self):
        c=Controller(CFG); c.enabled=True
        for i in range(10): c.update(i/30,hand(.3))
        for i in range(10,20): c.update(i/30,hand(.3+(i-10)*.025))
        c.update(20/30,None)
        for i in range(21,35):
            self.assertIsNone(c.update(i/30,hand(.55)))


if __name__=='__main__': unittest.main()
