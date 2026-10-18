import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import tools
from test_core import hand
from gesture.core import features


class ToolTests(unittest.TestCase):
    def test_pipeline_synthetic_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for person in range(5):
                for label in tools.LABELS:
                    samples=[]
                    for i in range(60):
                        t=i/30
                        x=.4
                        if label in ('left','right'):
                            x += (1 if label=='right' else -1)*min(max(t-.4,0),.5)*.5
                        points=hand(x,fist=label=='fist') if label!='idle' else None
                        s={'t':t,'points':points}
                        if points:
                            center,relative,pose=features(points)
                            s.update(center=center.tolist(),relative=relative.tolist(),pose=pose)
                        samples.append(s)
                    tools.save(root/f'{person}_{label}.json',{'person':str(person),'recording':f'{person}_session','label':label,'intent_start':.4,'samples':samples})
            split=root/'split.json'
            tools.split(SimpleNamespace(data=str(root),group='person',seed=42,output=str(split)))
            templates=root/'templates.json'
            tools.train(SimpleNamespace(split=str(split),partition='train',output=str(templates)))
            output=root/'results.json'
            with contextlib.redirect_stdout(io.StringIO()):
                tools.evaluate(SimpleNamespace(config='config.json',split=str(split),partition='test',templates=str(templates),output=str(output)))
            result=json.loads(output.read_text())
            self.assertEqual(set(result),{'rule','dtw'})
            self.assertEqual(result['rule']['clips'],5)
            self.assertEqual(sum(map(sum,result['dtw']['confusion_rows_true_columns_pred'])),5)
            # Confirm grouped train and test people never overlap.
            manifest=json.loads(split.read_text())
            people=lambda k:{json.loads(Path(p).read_text())['person'] for p in manifest[k]}
            self.assertFalse(people('train') & people('test'))
            with self.assertRaises(ValueError):
                tools.train(SimpleNamespace(split=str(split),partition='test',output=str(templates)))
