"""Regressions following the on-device storage diagnostic, 13 Nov 2026."""
import hashlib
import json
import re
import unittest
from pathlib import Path
from workflow import build, OPTIONS
from simulate_shortcut import Simulator, File
from test_workflow import APP, NOW, ROW, record, files_for, ledger, saved


class JSONBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = build()

    def cached_metadata_without_finances(self, repaired=False):
        raw = json.dumps({'1001':{'ID':'1001','Name':'TIỆM THỬ','Money':'10000','DC':'','Number':''}})
        data = {'_schema':'sen-orders-v3','_version':'4.1.2','_legacyIndexDone':'1',
                '_legacyFilenamesV411':'1','_legacyFilenamesV412':'1','_iterationFixV412':'1',
                '_sourceMigrated':'1','_sharedDataHash':hashlib.sha256(raw.encode()).hexdigest(),
                '_sourceMap':'{}','_displayLimit':'6'}
        self.assertEqual(len(data), 10)
        if repaired:
            data['_jsonTextV413'] = '1'
        return {APP+'DonHang.json':File(APP+'DonHang.json', raw),
                APP+'orders.json':File(APP+'orders.json', json.dumps(data)),
                APP+'ui-v4.1.json':File(APP+'ui-v4.1.json', (Path(__file__).parents[1]/'data/ui-v4.1.json').read_text())}

    def run_manager(self, files, **kwargs):
        return Simulator(self.workflow, files=files, now=NOW, **kwargs).run()

    def test_old_equal_hash_with_missing_finances_is_reimported(self):
        s = self.run_manager(self.cached_metadata_without_finances())
        self.assertEqual(s.last_ui[1], ['TIỆM THỬ — 10.000₫', OPTIONS])
        self.assertEqual(ledger(s)['_displayLimit'], '6')
        self.assertEqual(len([k for k in ledger(s) if re.fullmatch('[a-f0-9]{64}', k)]), 1)

    def test_equal_hash_is_not_trusted_when_index_disappears_after_repair(self):
        s = self.run_manager(self.cached_metadata_without_finances(repaired=True))
        self.assertEqual(s.last_ui[1], ['TIỆM THỬ — 10.000₫', OPTIONS])
        warm = self.run_manager(s.files)
        self.assertEqual(warm.last_ui, s.last_ui)
        self.assertFalse(warm.folder_reads or warm.network)

    def test_lost_source_map_restores_existing_receipts_without_duplicate(self):
        f = files_for(record(cash='665000',bank='1500000',fee='5000',signedDay='2026-11-12'))
        data = json.loads(f[APP+'orders.json'].data)
        data['_sourceMap'] = '{}'
        f[APP+'orders.json'].data = json.dumps(data)
        s = self.run_manager(f)
        self.assertEqual(s.last_ui[1], [ROW, OPTIONS])
        self.assertEqual(len([k for k in ledger(s) if re.fullmatch('[a-f0-9]{64}', k)]), 1)
        self.assertEqual([saved(s)[k] for k in ['cash','bank','fee','signedDay']],
                         ['665000','1500000','5000','2026-11-12'])

    def test_number_prompt_displays_the_saved_limit_on_next_run(self):
        f = files_for();data = json.loads(f[APP+'orders.json'].data)
        data['_displayLimit'] = '6';f[APP+'orders.json'].data = json.dumps(data)
        s = self.run_manager(f, choices=[OPTIONS,'🔢 Giới hạn hiển thị'])
        self.assertEqual(s.asks[-1][1], '6')
        changed = self.run_manager(f, choices=[OPTIONS,'🔢 Giới hạn hiển thị'], answers=['7'])
        self.assertEqual(ledger(changed)['_displayLimit'], '7')
        reopened = self.run_manager(changed.files, choices=[OPTIONS,'🔢 Giới hạn hiển thị'])
        self.assertEqual(reopened.asks[-1][1], '7')

    def test_native_number_default_uses_number_parameter(self):
        asks = [a['WFWorkflowActionParameters'] for a in self.workflow['WFWorkflowActions']
                if a['WFWorkflowActionIdentifier'].endswith('ask')]
        for p in asks:
            if p['WFInputType'] == 'Number':
                self.assertIn('WFAskActionDefaultAnswerNumber', p)
                self.assertNotIn('WFAskActionDefaultAnswer', p)

    def test_metadata_parser_is_fed_by_explicit_text_action(self):
        actions = self.workflow['WFWorkflowActions']
        by_id = {a['WFWorkflowActionParameters']['UUID']:a for a in actions}
        parsers = []
        for a in actions:
            p = a['WFWorkflowActionParameters']
            if a['WFWorkflowActionIdentifier'].endswith('setvariable') and p.get('WFVariableName') == 'OrdersData':
                source = by_id[p['WFInput']['Value']['OutputUUID']]
                if source['WFWorkflowActionIdentifier'].endswith('detect.dictionary'):
                    parsers.append(source)
        self.assertTrue(parsers)
        for a in parsers:
            token = a['WFWorkflowActionParameters']['WFInput']['Value']
            text_action = by_id[token['OutputUUID']]
            self.assertTrue(text_action['WFWorkflowActionIdentifier'].endswith('gettext'))


if __name__ == '__main__':
    unittest.main()
