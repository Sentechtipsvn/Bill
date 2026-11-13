"""Regressions for the 13 November iPhone failure reports.

Envelope checks use the native text-input parameter shape, independently of
the host simulator. These do not assert that iPhone execution was performed.
"""
import copy,json,re,unittest
from workflow import build,OPTIONS
from bill_builder import build_bill,SAVE
from shared import UI_NAME
from simulate_shortcut import Simulator,File,validate
from test_workflow import APP,NOW,ROW,record,files_for,ledger,saved

OCR='Số: 3856\nĐơn vị: TIỆM THỬ\nĐịa chỉ: 12 Đường Mẫu\nSĐT: 0900000000\nTiền hàng: 2.165.000'

class DeviceRegressions(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bill=build_bill();cls.manager=build()
 def cache(self):
  from pathlib import Path
  p=APP+UI_NAME
  return {p:File(p,(Path(__file__).parents[1]/'data'/UI_NAME).read_text())}
 def manager_run(self,files,choices=None,answers=None,**kwargs):
  f=copy.deepcopy(files);f.update(self.cache())
  return Simulator(self.manager,files=f,choices=choices,answers=answers,now=NOW,**kwargs).run()
 def bill_run(self,files=None):
  f=copy.deepcopy(files or self.cache());f.update(self.cache())
  return Simulator(self.bill,files=f,shortcut_input=[File('share/invoice.png',OCR,NOW,1032,643,'PNG')],choices=[SAVE],now=NOW).run()
 def test_native_dictionary_value_is_a_text_input_not_a_bare_attachment(self):
  for w in (self.bill,self.manager):
   validate(w)
   for a in w['WFWorkflowActions']:
    if a['WFWorkflowActionIdentifier'].endswith('setvalueforkey'):
     p=a['WFWorkflowActionParameters']
     for key in ('WFDictionaryKey','WFDictionaryValue'):
      v=p[key];self.assertTrue(isinstance(v,str) or v['WFSerializationType']=='WFTextTokenString')
 def test_previous_empty_native_value_envelope_is_rejected(self):
  bad={'WFWorkflowActions':[{'WFWorkflowActionIdentifier':'is.workflow.actions.setvalueforkey','WFWorkflowActionParameters':{'UUID':'bad','WFDictionaryKey':'3856','WFDictionaryValue':{'Value':{'Type':'Variable','VariableName':'BillRecord'},'WFSerializationType':'WFTextTokenAttachment'}}}],'WFWorkflowImportQuestions':[]}
  with self.assertRaisesRegex(AssertionError,'text-input'):validate(bad)
 def test_blank_resets_remain_native_text_and_no_property_macros_remain(self):
  for w in (self.bill,self.manager):
   raw=json.dumps(w,ensure_ascii=False)
   self.assertNotIn('WFDictionaryValueVariableAggrandizement',raw)
   self.assertNotIn('Hằng số',raw)
   self.assertTrue(any(a['WFWorkflowActionIdentifier'].endswith('gettext') and a['WFWorkflowActionParameters'].get('WFTextActionText')=='' for a in w['WFWorkflowActions']))
 def test_limit_asks_with_previous_value_and_accepts_ok(self):
  s=self.manager_run(files_for(),[OPTIONS,'🔢 Giới hạn hiển thị'],['__DEFAULT__'])
  self.assertEqual(s.asks[-1][1],'50');self.assertEqual(ledger(s)['_displayLimit'],'50')
  self.assertEqual(s.last_ui[1],[ROW,OPTIONS])
 def test_limit_invalid_then_valid_and_zero_persist(self):
  a=self.manager_run(files_for(),[OPTIONS,'🔢 Giới hạn hiển thị'],['501','7'])
  self.assertEqual(ledger(a)['_displayLimit'],'7');self.assertEqual(len(a.asks),2)
  b=self.manager_run(a.files,[OPTIONS,'🔢 Giới hạn hiển thị'],['0'])
  self.assertEqual(b.asks[-1][1],'7');self.assertEqual(ledger(b)['_displayLimit'],'0')
 def test_bill_repairs_photo_left_by_failed_v340_without_creating_another(self):
  original=self.bill_run();path=APP+'Ảnh Đơn Hàng/3856.png'
  s=self.bill_run({**self.cache(),path:original.files[path]})
  data=json.loads(s.files[APP+'DonHang.json'].data)
  self.assertEqual(data['3856']['Name'],'TIỆM THỬ')
  self.assertEqual([p for p in s.files if '/Ảnh Đơn Hàng/' in p],[path])
 def test_old_photos_without_any_ledger_appear_using_names_only(self):
  names=['TIỆM MỘT - 2.165.000 · 261112-082214639.png','TIỆM HAI - 985.000.png']
  f={APP+'Ảnh Đơn Hàng/'+n:File(APP+'Ảnh Đơn Hàng/'+n,'DO NOT READ',NOW,3200,1800,'PNG') for n in names}
  s=self.manager_run(f)
  self.assertEqual(set(s.last_ui[1]),{'TIỆM MỘT — 2.165.000₫','TIỆM HAI — 985.000₫',OPTIONS})
  self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in s.file_reads));self.assertFalse(s.previews)
  for k,v in ledger(s).items():
   if re.fullmatch('[a-f0-9]{64}',k):
    r=json.loads(v);self.assertEqual((r['cash'],r['bank'],r['fee'],r['signedDay']),('0','0','0',''))
  self.assertEqual(self.manager_run(s.files).folder_reads,[])
 def test_old_photos_index_when_provider_omits_extension(self):
  n='TIỆM CŨ - 1.892.000 · 261112-082214639.png';p=APP+'Ảnh Đơn Hàng/'+n
  s=self.manager_run({p:File(p,'UNCHANGED',NOW,3200,1800,'PNG')},names_include_extension=False)
  self.assertIn('TIỆM CŨ — 1.892.000₫',s.last_ui[1])
 def test_first_reindex_preserves_existing_financial_record(self):
  f=files_for(record(cash='665000',bank='1500000',signedDay='2026-11-12',fee='5000'))
  l=json.loads(f[APP+'orders.json'].data);l.pop('_legacyFilenamesV412');f[APP+'orders.json'].data=json.dumps(l)
  s=self.manager_run(f);r=saved(s)
  self.assertEqual((r['cash'],r['bank'],r['fee'],r['signedDay']),('665000','1500000','5000','2026-11-12'))
  self.assertEqual(len([k for k in ledger(s) if re.fullmatch('[a-f0-9]{64}',k)]),1)
 def test_manual_reindex_finds_an_old_file_added_after_the_first_run(self):
  f=files_for();n='TIỆM THÊM - 50.000.png';p=APP+'Ảnh Đơn Hàng/'+n
  f[p]=File(p,'UNCHANGED',NOW,3200,1800,'PNG')
  s=self.manager_run(f,[OPTIONS,'🛠️ Dữ liệu / công cụ','🔄 Đọc lại tên ảnh trong kho'])
  self.assertIn('TIỆM THÊM — 50.000₫',s.last_ui[1]);self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in s.file_reads))
 def test_selecting_migrated_legacy_invoice_opens_only_that_file(self):
  n='TIỆM CŨ - 985.000.png';p=APP+'Ảnh Đơn Hàng/'+n
  s=self.manager_run({p:File(p,'ORIGINAL',NOW,3200,1800,'PNG')},['TIỆM CŨ — 985.000₫','👁️ Xem phiếu'])
  self.assertEqual([p for p in s.file_reads if '/Ảnh Đơn Hàng/' in p],[p]);self.assertEqual(len(s.previews),1)

if __name__=='__main__':unittest.main()
