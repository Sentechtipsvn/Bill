from pathlib import Path
import unittest,sys,json,io
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'project'))
suite=unittest.defaultTestLoader.discover(str(root/'project'),pattern='test*.py')
log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=1).run(suite)
(root/'test.log').write_text(log.getvalue())
summary={'tests':result.testsRun,'passed':result.wasSuccessful(),'failures':[{'test':str(t),'reason':e.splitlines()[-1][:450]} for t,e in result.failures+result.errors]}
(root/'test-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)
