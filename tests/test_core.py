import json
import unittest
import numpy as np
from gesture.core import Controller, classify, dtw, features

CFG = json.load(open('config.json'))


def hand(x=.5, fist=False):
    p = np.zeros((21,3))
    p[0] = [x,.7,0]
    for mcp,pip,dip,tip in [(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]:
        xx = x+(mcp-9)*.006
        for idx,y in [(mcp,.58),(pip,.49),(dip,.42),(tip,.35 if not fist else .63)]:
            p[idx] = [xx,y,0]
    return p.tolist()


class Tests(unittest.TestCase):
    def test_pose(self):
        self.assertEqual(features(hand())[2],'open')
        self.assertEqual(features(hand(fist=True))[2],'fist')

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
