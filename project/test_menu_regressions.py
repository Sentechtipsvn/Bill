"""Blank menu recovery: native iteration, Bill input and retained finances.

These execute emitted native actions locally; they do not assert device tests.
"""
import copy
import json
import re
import unittest
from pathlib import Path

from shortcut_builder import Builder, ref
from workflow import build, OPTIONS
from simulate_shortcut import Simulator, File, validate
from test_workflow import APP, NOW, ROW, record, files_for, ledger, saved


class MenuRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = build()

    def run_manager(self, files, **kwargs):
        return Simulator(self.workflow, files=files, now=NOW, **kwargs).run()

    def cache(self):
        path = APP + 'ui-v4.1.json'
        return {path: File(path, (Path(__file__).parents[1] / 'data/ui-v4.1.json').read_text())}

    def test_bill_metadata_without_financial_row_is_visible(self):
        f = self.cache()
        p = APP + 'DonHang.json'
        f[p] = File(p, json.dumps({'2888': {
            'ID': '2888', 'Name': 'TIỆM KIỂM TRA', 'Money': '1892000',
            'DC': '31 Đường Thử', 'Number': ''
        }}, ensure_ascii=False))
        # A previous run has already set migration flags and a stale cache.
        p = APP + 'orders.json'
        f[p] = File(p, json.dumps({
            '_schema': 'sen-orders-v3', '_version': '4.1.1',
            '_sourceMigrated': '1', '_legacyFilenamesV411': '1',
            '_legacyIndexDone': '1', '_sourceMap': '{}',
            '_sharedDataHash': 'stale'
        }))
        s = self.run_manager(f)
        self.assertEqual(s.last_ui[1], ['TIỆM KIỂM TRA — 1.892.000₫', OPTIONS])
        self.assertFalse(any('/Ảnh Đơn Hàng/' in path for path in s.file_reads))
        warm = self.run_manager(s.files)
        self.assertEqual(warm.last_ui, s.last_ui)
        self.assertEqual(warm.folder_reads, [])
        self.assertEqual(warm.network, [])

    def test_partial_old_migration_recovers_all_rows_without_resetting_receipts(self):
        records = [record(id=f'{i:064x}', name=f'TIỆM {i}', invoiceCode=str(2800+i),
                          cash=str(i*1000), bank='2000', signedDay='2026-11-12', fee='5000')
                   for i in range(1, 7)]
        f = files_for(*records)
        original = json.loads(f[APP+'orders.json'].data)
        for marker in ['_iterationFixV412', '_legacyFilenamesV412']:
            original.pop(marker)
        # Reproduce completion flags left behind while rows have no dataID.
        for r in records:
            old = json.loads(original[r['id']]); old['dataID'] = ''
            original[r['id']] = json.dumps(old)
        original['_sourceMap'] = '{}'
        f[APP+'orders.json'].data = json.dumps(original)
        f[APP+'DonHang.json'].data = '{}'
        s = self.run_manager(f)
        self.assertEqual(len(s.last_ui[1]), 7)
        for r in records:
            actual = saved(s, r['id'])
            self.assertEqual([actual[k] for k in ['cash','bank','fee','signedDay','filename']],
                             [r[k] for k in ['cash','bank','fee','signedDay','filename']])
        self.assertEqual(len([k for k in ledger(s) if re.fullmatch('[a-f0-9]{64}', k)]), 6)

    def test_empty_native_sort_result_cannot_hide_nonempty_index(self):
        class EmptySort(Simulator):
            def action(self, action):
                if action['WFWorkflowActionIdentifier'].endswith('filter.files'):
                    p = action['WFWorkflowActionParameters']
                    if p.get('WFContentItemSortProperty') == 'Name':
                        return []
                return super().action(action)
        s = EmptySort(self.workflow, files=files_for(), now=NOW).run()
        self.assertEqual(s.last_ui[1], [ROW, OPTIONS])

    def test_nested_iteration_does_not_read_localized_repeat_variable_names(self):
        b = Builder()
        b.empty_list('Visited')
        with b.repeat(1):
            with b.each(b.add('list', WFItems=['A','B','C']), 'Outer'):
                with b.each(b.add('list', WFItems=['1','2']), 'Inner'):
                    from shortcut_builder import token
                    b.append('Visited', b.text(token(ref('Outer'), ref('Inner'))))
        w = {'WFWorkflowActions': b.actions, 'WFWorkflowImportQuestions': []}
        s = Simulator(w).run()
        self.assertEqual(s.vars['Visited'], ['A1','A2','B1','B2','C1','C2'])
        self.assertNotIn('Repeat Index', json.dumps(w))
        self.assertNotIn('Repeat Item', json.dumps(w))
        self.assertTrue(any(a['WFWorkflowActionIdentifier'].endswith('repeat.each') for a in b.actions))

    def test_manager_uses_named_counters_and_valid_native_inputs(self):
        validate(self.workflow)
        raw = json.dumps(self.workflow)
        self.assertNotIn('"VariableName": "Repeat Index', raw)
        self.assertNotIn('"VariableName": "Repeat Item', raw)


if __name__ == '__main__':
    unittest.main()
