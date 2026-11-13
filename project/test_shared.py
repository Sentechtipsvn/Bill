"""End-to-end regressions for the new JSON, native SVG coercion and startup cache."""
import copy,json,hashlib,re,base64,unittest
from pathlib import Path
from workflow import build,OPTIONS
from bill_builder import build_bill,SAVE
from shared import DEFAULTS,UI_NAME,UI_URL
from simulate_shortcut import Simulator,File,text,validate
from test_workflow import APP,NOW,ROW,record,files_for,saved,ledger,qr_files
OCR='''Ngày 12 tháng 11 năm 2026
Số: 3856
Đơn vị: TIỆM THỬ
Địa chỉ: 12 Đường Mẫu
SĐT: 0900000000
Tiền hàng: 2.165.000'''
class SharedTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bill=build_bill();cls.manager=build()
 def ui(self):return (Path(__file__).parents[1]/'data'/UI_NAME).read_text()
 def cache(self):return {APP+UI_NAME:File(APP+UI_NAME,self.ui())}
 def bill_run(self,ocr=OCR,files=None,answers=None,choices=None):
  f=copy.deepcopy(files or self.cache());f.update(self.cache())
  return Simulator(self.bill,files=f,shortcut_input=[File('share/invoice.png',ocr,NOW,1032,643,'PNG')],choices=choices or [SAVE],answers=answers,now=NOW).run()
 def data(self,s):return json.loads(s.files[APP+'DonHang.json'].data)
 def manager_run(self,files,choices=None,answers=None):
  f=copy.deepcopy(files);f.update(self.cache())
  return Simulator(self.manager,files=f,choices=choices,answers=answers,now=NOW).run()
 def test_bill_writes_only_five_fields_and_numeric_photo_filename(self):
  s=self.bill_run();r=self.data(s)['3856']
  self.assertEqual(r,dict(Name='TIỆM THỬ',Money='2165000',ID='3856',DC='12 Đường Mẫu',Number='0900000000'))
  self.assertIn(APP+'Ảnh Đơn Hàng/3856.png',s.files)
  self.assertFalse(any('/Đơn mới/' in p for p in s.files))
 def test_bill_missing_number_automatically_allocates_four_digits(self):
  s=self.bill_run(OCR.replace('Số: 3856',''));key=next(iter(self.data(s)))
  self.assertRegex(key,r'^[1-9][0-9]{3}$');self.assertIn(APP+'Ảnh Đơn Hàng/'+key+'.png',s.files)
  self.assertFalse(any('Mã phiếu' in t for t,d,k in s.asks))
 def test_invoice_id_collision_never_overwrites_other_customer(self):
  a=self.bill_run();before=a.files[APP+'Ảnh Đơn Hàng/3856.png'].data
  b=self.bill_run(OCR.replace('TIỆM THỬ','TIỆM KHÁC'),a.files)
  self.assertEqual(len(self.data(b)),2);self.assertEqual(b.files[APP+'Ảnh Đơn Hàng/3856.png'].data,before)
  other=next(k for k in self.data(b) if k!='3856');self.assertRegex(other,r'^[1-9][0-9]{3}$')
 def test_same_number_name_money_with_different_photo_is_a_new_order(self):
  a=self.bill_run();b=self.bill_run(OCR+'\nOTHER PRODUCTS',a.files)
  self.assertEqual(len(self.data(b)),2)
 def test_same_invoice_reimport_is_idempotent(self):
  a=self.bill_run();b=self.bill_run(files=a.files)
  self.assertEqual(self.data(a),self.data(b));self.assertEqual(len([p for p in b.files if '/Ảnh Đơn Hàng/' in p]),1)
 def test_bill_never_touches_financial_ledger(self):
  f=self.cache();f[APP+'DonHang.json']=File(APP+'DonHang.json','{}');f[APP+'orders.json']=File(APP+'orders.json','PRIVATE LEDGER')
  s=self.bill_run(files=f);self.assertEqual(s.files[APP+'orders.json'].data,'PRIVATE LEDGER');self.assertNotIn(APP+'orders.json',s.file_reads)
 def test_new_bill_to_manager_without_photo_folder_scan(self):
  a=self.bill_run();b=self.manager_run(a.files)
  r=next(json.loads(v) for k,v in ledger(b).items() if re.fullmatch('[a-f0-9]{64}',k))
  self.assertEqual((r['filename'],r['invoiceCode'],r['phone']),('3856.png','3856','0900000000'))
  self.assertEqual(b.last_ui,('Phiếu Giao Hàng 11-2026',[ROW,OPTIONS]))
  self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in b.file_reads))
 def test_warm_launch_reads_no_folders_or_network(self):
  a=self.bill_run();b=self.manager_run(a.files);c=self.manager_run(b.files)
  self.assertEqual(c.folder_reads,[]);self.assertEqual(c.network,[])
  self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in c.file_reads))
 def test_first_download_is_saved_and_shared_by_both_shortcuts(self):
  s=Simulator(self.bill,shortcut_input=[File('share/invoice.png',OCR,NOW,1032,643,'PNG')],choices=[SAVE],now=NOW)
  s.network_handler=lambda u:json.loads(self.ui());s.run()
  self.assertEqual(s.network,[UI_URL]);self.assertIn(APP+UI_NAME,s.files)
  b=self.manager_run(s.files);self.assertEqual(b.network,[])
 def test_bad_ui_download_is_not_cached(self):
  s=Simulator(self.manager,now=NOW);s.network_handler=lambda u:dict(schema='wrong',strings={});s.run()
  self.assertNotIn(APP+UI_NAME,s.files);self.assertFalse(s.last_ui)
 def test_cash_default_is_full_required_cash_and_ok_commits(self):
  f=files_for();a=self.manager_run(f,[ROW,'💵 Thu tiền mặt'])
  self.assertEqual(a.asks[-1][:2],('Tiền mặt','2165000'))
  b=self.manager_run(f,[ROW,'💵 Thu tiền mặt'],['__DEFAULT__'])
  self.assertEqual(saved(b)['cash'],'2165000');self.assertEqual(saved(b)['bank'],'0')
 def test_cash_default_deducts_existing_transfer(self):
  a=self.manager_run(files_for(record(bank='1500000')),[ROW,'💵 Thu tiền mặt'],['__DEFAULT__'])
  self.assertEqual(a.asks[-1][1],'665000');self.assertEqual(saved(a)['cash'],'665000')
 def test_full_cash_reopen_and_ok_never_adds_again(self):
  f=files_for(record(cash='2165000'))
  a=self.manager_run(f,[ROW,'💵 Thu tiền mặt'],['__DEFAULT__']);self.assertEqual(saved(a)['cash'],'2165000')
 def test_svg_download_as_image_does_not_go_through_get_text(self):
  svg=Path(__file__).with_name('fixtures').joinpath('vietqr-public-example.svg').read_text()
  image=File('network/payment.svg',svg,NOW,540,640,'SVG')
  self.assertEqual(text(image),'payment.svg') # old path cannot see XML on this content type
  s=Simulator(self.manager,files=files_for(extra=qr_files()),choices=[ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],now=NOW)
  s.network_handler=lambda u:image;s.run()
  html=text(s.previews[0]);body=re.search('data:image/svg\\+xml;base64,([^\"]+)',html)[1]
  self.assertEqual(base64.b64decode(body).decode(),svg)
 def test_png_response_is_also_supported(self):
  s=Simulator(self.manager,files=files_for(extra=qr_files()),choices=[ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],now=NOW)
  s.network_handler=lambda u:File('qr.png',b'\x89PNG\r\n\x1a\n'+b'\x00'*16,NOW,540,640,'PNG');s.run()
  self.assertIn('data:image/png;base64,',text(s.previews[0]))
 def test_old_ledger_migration_preserves_receipts_fee_and_original_photo(self):
  r=record(cash='665000',bank='1500000',signedDay='2026-11-12',signedMonth='2026-11',fee='5000')
  f=self.cache();f[APP+'orders.json']=File(APP+'orders.json',json.dumps({'_schema':'sen-orders-v3',r['id']:json.dumps(r)}))
  a=self.manager_run(f);rr=saved(a)
  self.assertEqual((rr['cash'],rr['bank'],rr['fee'],rr['filename']),('665000','1500000','5000',r['filename']))
  self.assertEqual(self.data(a)['3856']['Name'],r['name']);self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in a.file_reads))
 def test_new_data_matching_old_invoice_does_not_duplicate_finances(self):
  a=self.bill_run();r=record(cash='665000',bank='1500000',fee='5000',signedDay='2026-11-12')
  a.files[APP+'orders.json']=File(APP+'orders.json',json.dumps({'_schema':'sen-orders-v3',r['id']:json.dumps(r)}))
  b=self.manager_run(a.files);ids=[k for k in ledger(b) if re.fullmatch('[a-f0-9]{64}',k)]
  self.assertEqual(ids,[r['id']]);self.assertEqual(saved(b)['cash'],'665000')
 def test_editing_details_updates_the_shared_five_field_json(self):
  a=self.manager_run(files_for(),[ROW,'🧾 Thông tin / ký nhận','✏️ Sửa thông tin'],['TIỆM MỚI','99 Đường Thử','0911111111','Giao sau'])
  r=self.data(a)['3856'];self.assertEqual((r['Name'],r['DC'],r['Number']),('TIỆM MỚI','99 Đường Thử','0911111111'));self.assertEqual(len(r),5)
  b=self.manager_run(a.files);self.assertIn('TIỆM MỚI — 2.165.000₫',b.last_ui[1])
 def test_new_smaller_total_cannot_erase_existing_receipts(self):
  f=files_for(record(cash='1000000'));data=json.loads(f[APP+'DonHang.json'].data);data['3856']['Money']='100';f[APP+'DonHang.json'].data=json.dumps(data)
  a=self.manager_run(f);self.assertEqual(saved(a)['cash'],'1000000');self.assertTrue(any('Số tiền' in t for t,m in a.alerts))
 def test_both_native_workflows_have_no_embedded_ui_dictionary(self):
  for w in [self.bill,self.manager]:
   validate(w)
   ui=set(json.loads(self.ui())['strings'])
   for a in w['WFWorkflowActions']:
    if a['WFWorkflowActionIdentifier'].endswith('dictionary'):
     keys={i['WFKey']['Value']['string'] for i in a['WFWorkflowActionParameters'].get('WFItems',{}).get('Value',{}).get('WFDictionaryFieldValueItems',[])}
     self.assertFalse(keys & ui)

 def test_missing_metadata_with_backup_is_never_reset(self):
  f=self.cache();f[APP+'DonHang.backup.json']=File(APP+'DonHang.backup.json','{"3856":{"Name":"TIỆM"}}')
  s=self.manager_run(f);self.assertNotIn(APP+'DonHang.json',s.files);self.assertTrue(any('khôi phục' in t for t,m in s.alerts))
 def test_old_ledger_requires_migration_before_new_bill(self):
  f=self.cache();f[APP+'orders.json']=File(APP+'orders.json','OLD LEDGER')
  s=self.bill_run(files=f);self.assertNotIn(APP+'DonHang.json',s.files);self.assertTrue(any('v4.1' in t for t,m in s.alerts))
 def test_empty_manager_initializes_metadata_for_the_first_bill(self):
  a=self.manager_run(self.cache());self.assertEqual(self.data(a),{})
  b=self.bill_run(files=a.files);self.assertIn('3856',self.data(b))

if __name__=='__main__':unittest.main()
