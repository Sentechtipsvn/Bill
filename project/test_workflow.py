import unittest, json, hashlib, plistlib, copy
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs
from workflow import build, OPTIONS, BACK
from bill_builder import build_bill
from shared import DEFAULTS
import base64,re
from simulate_shortcut import Simulator, File, validate, text

APP='shortcuts/SenTechTips_AnhDonHang/'
NOW=datetime(2026,11,13,9,0,tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
ROW='TIỆM THỬ — 2.165.000₫'
OID='a'*64

def record(id=OID,**kw):
    r=dict(id=id,filename='TIỆM THỬ - 2.165.000 · 261112-082214639.png',name='TIỆM THỬ',total='2165000',cash='0',bank='0',
           createdAt='2026-11-12T08:22:14+07:00',createdMonth='2026-11',invoiceCode='3856',address='12 Đường Mẫu',phone='0900000000',deliveryNote='Trước 10h',
           deliveredAt='',deliveryMonth='',deleted='0',destroyed='0',cancelled='0',latestReport='',reportHistory='',note='')
    r.update(kw);return r

def files_for(*records,extra=None):
    rs=records or [record()]
    ledger={'_schema':'sen-orders-v3','_version':'3.2.0',**{r['id']:json.dumps(r,ensure_ascii=False) for r in rs}}
    files={APP+'orders.json':File(APP+'orders.json',json.dumps(ledger,ensure_ascii=False),NOW)}
    data={};links={}
    for i,r in enumerate(rs):
        external=r.get('dataID') or r.get('invoiceCode','')
        if not external.isdigit() or external in data:external=str(4000+i)
        data[external]=dict(Name=r['name'],Money=r['total'],ID=external,DC=r.get('address',''),Number=r.get('phone',''))
        normalized={**DEFAULTS,**r,'dataID':external}
        ledger[r['id']]=json.dumps(normalized,ensure_ascii=False);links[external]=r['id']
    ledger['_sourceMap']=json.dumps(links);ledger['_legacyIndexDone']='1';ledger['_sourceMigrated']='1'
    files[APP+'orders.json'].data=json.dumps(ledger,ensure_ascii=False)
    files[APP+'DonHang.json']=File(APP+'DonHang.json',json.dumps(data,ensure_ascii=False),NOW)
    ledger['_sharedDataHash']=hashlib.sha256(files[APP+'DonHang.json'].data.encode()).hexdigest()
    files[APP+'orders.json'].data=json.dumps(ledger,ensure_ascii=False)
    files[APP+'ui-v4.1.json']=File(APP+'ui-v4.1.json',(Path(__file__).parents[1]/'data/ui-v4.1.json').read_text())
    for r in rs:
        path=APP+'Ảnh Đơn Hàng/'+r['filename'];files[path]=File(path,'ORIGINAL INVOICE '+r['id'],NOW,3200,1800,'PNG')
    if extra:files.update(extra)
    return files

def ledger(s):return json.loads(s.files[APP+'orders.json'].data)
def saved(s,id=OID):return json.loads(ledger(s)[id])

def qr_files(name='CONG TY THU',account='0012345678',bin='970416'):
    cfg=dict(schema='sen-qr-v1',name=name,account=account,bank='ACB',bin=bin,baseFile='base_'+'b'*64+'.html')
    return {APP+'QR/config.json':File(APP+'QR/config.json',json.dumps(cfg)),APP+'QR/'+cfg['baseFile']:File(APP+'QR/'+cfg['baseFile'],'BASE',NOW,540,640,'PNG')}

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_bill();cls.w=build()
    def run_flow(self,choices=None,answers=None,files=None,**kw):
        files=copy.deepcopy(files or files_for())
        files.setdefault(APP+'ui-v4.1.json',File(APP+'ui-v4.1.json',(Path(__file__).parents[1]/'data/ui-v4.1.json').read_text()))
        if choices:
            choices=list(choices)
            for i in range(len(choices)-1,-1,-1):
                if choices[i]=='💵 Thu tiền mặt' and i+1<len(choices) and choices[i+1]=='✅ Lưu khoản thu':choices.pop(i+1)
        return Simulator(self.w,files=files,choices=choices,answers=answers,now=NOW,**kw).run()
    def test_native_graph_and_no_automatic_messaging(self):
        info=validate(self.w);self.assertGreater(info['actions'],100)
        ids=[a['WFWorkflowActionIdentifier'] for a in self.w['WFWorkflowActions']]
        self.assertFalse(any('sendmessage' in x or 'sendemail' in x or 'runjavascript' in x for x in ids))
        self.assertEqual(self.w['WFWorkflowImportQuestions'],[])
    def test_launch_is_text_only_and_never_lists_image_folder(self):
        s=self.run_flow()
        self.assertEqual(s.last_ui[1],[ROW,OPTIONS]);self.assertFalse(s.previews);self.assertFalse(s.network)
        self.assertEqual(s.folder_reads,[])
        self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in s.file_reads))
        self.assertTrue(all(isinstance(v,str) for v in s.last_ui[1]))
    def test_select_image_reads_exactly_one_invoice(self):
        other=record(id='b'*64,name='TIỆM KHÁC',filename='OTHER.png')
        s=self.run_flow([ROW,'👁️ Xem phiếu'],files=files_for(record(),other))
        reads=[p for p in s.file_reads if '/Ảnh Đơn Hàng/' in p]
        self.assertEqual(reads,[APP+'Ảnh Đơn Hàng/'+record()['filename']]);self.assertEqual(len(s.previews),1)
    def test_real_bill33_graph_and_metadata_fields(self):
        path=Path(__file__).with_name('fixtures')/'Bill-v3.3.0-unsigned.json'
        w=json.loads(path.read_text())
        ocr='Ngày 12 tháng 11 năm 2026\nSố: 1234\nĐơn vị: TIỆM MẪU\nĐịa chỉ: 12 Đường Thử\nĐiện thoại: 0900000000\nĐịa chỉ giao hàng: Sau 9h\nTiền hàng: 2.165.000'
        s=Simulator(w,shortcut_input=[File('share/invoice.png',ocr,NOW,1032,643,'PNG')],choices=['💾 Lưu đơn'],now=NOW).run()
        m=self.run_flow(files=s.files)
        r=next(json.loads(v) for k,v in ledger(m).items() if len(k)==64)
        self.assertEqual((r['invoiceCode'],r['address'],r['phone'],r['deliveryNote']),('1234','12 Đường Thử','0900000000','Sau 9h'))
        self.assertEqual((r['cash'],r['bank'],r['signedDay']),('0','0',''))
        self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in m.file_reads))
    def test_known_sidecar_never_resets_cash_or_reads_images(self):
        key='20261112082214639-123456';id=hashlib.sha256(('sen-bill-v1:'+key).encode()).hexdigest()
        r=record(id=id,filename='TIỆM THỬ - 2.165.000 · '+key+'.png',cash='665000',bank='1500000')
        meta=dict(schema='sen-bill-v1',version='3.3.0',imageKey=key,id=id,filename=r['filename'],name=r['name'],total=r['total'])
        f=files_for(r);p=APP+'Đơn mới/'+id+'.json';f[p]=File(p,json.dumps(meta))
        s=self.run_flow(files=f)
        self.assertEqual((saved(s,id)['cash'],saved(s,id)['bank']),('665000','1500000'))
        self.assertNotIn(p,s.file_reads)
    def test_corrupt_new_sidecar_is_skipped_without_destroying_old_ledger(self):
        f=files_for();p=APP+'Đơn mới/'+'e'*64+'.json';f[p]=File(p,'{broken')
        l=json.loads(f[APP+'orders.json'].data);l.pop('_legacyIndexDone');f[APP+'orders.json'].data=json.dumps(l)
        s=self.run_flow(files=f);self.assertIn(ROW,s.last_ui[1]);self.assertEqual(saved(s)['cash'],'0')
        self.assertTrue(any('gói Bill' in title for title,msg in s.alerts))
    def test_wrong_filename_identity_is_rejected(self):
        key='20261112082214639-123456';id=hashlib.sha256(('sen-bill-v1:'+key).encode()).hexdigest()
        meta=dict(schema='sen-bill-v1',imageKey=key,id=id,filename='wrong.png',name='TIỆM',total='1')
        f=files_for();p=APP+'Đơn mới/'+id+'.json';f[p]=File(p,json.dumps(meta))
        s=self.run_flow(files=f);self.assertNotIn(id,ledger(s))
    def test_same_name_amount_uses_second_identity_picker(self):
        other=record(id='b'*64,invoiceCode='OTHER',filename='OTHER.png')
        s=self.run_flow([ROW,'Số OTHER · 2026-11-12T08:22:14+07:00 · #1','👁️ Xem phiếu'],files=files_for(record(),other))
        self.assertEqual(s.previews[0].path,APP+'Ảnh Đơn Hàng/OTHER.png')
        self.assertEqual(self.run_flow(files=files_for(record(),other)).last_ui[1].count(ROW),1)
    def test_duplicate_ids_still_selectable_beyond_visible_limit(self):
        other=record(id='b'*64,invoiceCode='OTHER',filename='OTHER.png')
        f=files_for(record(),other);l=json.loads(f[APP+'orders.json'].data);l['_displayLimit']='1';f[APP+'orders.json'].data=json.dumps(l)
        s=self.run_flow([ROW,'Số OTHER · 2026-11-12T08:22:14+07:00 · #1','👁️ Xem phiếu'],files=f)
        self.assertEqual(s.previews[0].path,APP+'Ảnh Đơn Hàng/OTHER.png')
    def test_newest_metadata_first(self):
        other=record(id='b'*64,name='MỚI',filename='NEW.png',createdAt='2026-11-13T10:00:00+07:00')
        s=self.run_flow(files=files_for(record(),other));self.assertEqual(s.last_ui[1][0],'MỚI — 2.165.000₫')
    def test_missing_photo_does_not_discard_money(self):
        f=files_for(record(cash='100000'));f.pop(APP+'Ảnh Đơn Hàng/'+record()['filename'])
        s=self.run_flow([ROW,'👁️ Xem phiếu'],files=f)
        self.assertTrue(any('ảnh' in t for t,m in s.alerts));self.assertEqual(saved(s)['cash'],'100000')
    def test_cash_cumulative_not_additive_and_does_not_sign(self):
        s=self.run_flow([ROW,'💵 Thu tiền mặt','✅ Lưu khoản thu'],['665000'])
        self.assertEqual((saved(s)['cash'],saved(s)['bank']),('665000','0'))
        self.assertFalse(saved(s).get('signedDay'));self.assertFalse(saved(s)['deliveredAt'])
        t=self.run_flow([ROW,'💵 Thu tiền mặt','✅ Lưu khoản thu'],['665000'],s.files)
        self.assertEqual(saved(t)['cash'],'665000')
    def test_partial_mixed_receipt(self):
        s=self.run_flow([ROW,'🤝 Tiền mặt + CK','✅ Ghi tổng tiền thực thu','✅ Lưu khoản thu'],['600000','1500000'])
        self.assertEqual((saved(s)['cash'],saved(s)['bank']),('600000','1500000'))
        self.assertEqual(int(saved(s)['total'])-int(saved(s)['cash'])-int(saved(s)['bank']),65000)
    def test_negative_decimal_and_overpayment_are_not_silently_cleaned(self):
        s=self.run_flow([ROW,'💵 Thu tiền mặt','✅ Lưu khoản thu'],['-100','1.5','100000'])
        self.assertEqual(saved(s)['cash'],'100000');self.assertEqual(len(s.alerts),2)
        t=self.run_flow([ROW,'💵 Thu tiền mặt'],['3000000','4000000','5000000'])
        self.assertEqual(saved(t)['cash'],'0')
    def test_cancel_payment_keeps_ledger(self):
        f=files_for();s=self.run_flow([ROW,'💵 Thu tiền mặt'],[None],f)
        self.assertEqual(s.files[APP+'orders.json'].data,f[APP+'orders.json'].data)

    def test_sign_date_counts_once_and_snapshots_rate(self):
        choices=[ROW,'🧾 Thông tin / ký nhận','✍️ Xác nhận ngày ký nhận','✅ Đã ký — ghi công']
        s=self.run_flow(choices,['2026-11-12']);r=saved(s)
        self.assertEqual((r['signedDay'],r['signedMonth'],r['fee']),('2026-11-12','2026-11','5000'))
        t=self.run_flow([ROW,'🧾 Thông tin / ký nhận','✍️ Xác nhận ngày ký nhận'],files=s.files)
        self.assertEqual(saved(t)['fee'],'5000');self.assertTrue(any('đã xác nhận' in t for t,m in t.alerts))
    def test_delivery_failure_still_counts_commission(self):
        r=record(signedDay='2026-11-12',signedMonth='2026-11',fee='5000',feeReversed='0')
        s=self.run_flow([ROW,'📦 Giao hàng & báo cáo','❌ Giao thất bại',BACK,OPTIONS,'📊 Công đơn & đối soát'],files=files_for(r))
        self.assertEqual(saved(s)['outcome'],'failed');self.assertIn('1 đơn · 5.000₫',s.last_ui[0])
    def test_old_delivered_slips_never_automatically_accrue_fee_today(self):
        r=record(deliveredAt='2026-11-12T10:00:00+07:00',deliveryMonth='2026-11')
        s=self.run_flow([OPTIONS,'📊 Công đơn & đối soát','💰 Số tiền đang giữ'],files=files_for(r))
        self.assertIn('0 đơn · 0₫',s.last_ui[0]);self.assertTrue(any('Chưa tính công: 1 hồ sơ' in m for t,m in s.alerts))
    def test_impossible_or_future_signature_day_is_rejected(self):
        for day in ['2026-02-29','2026-11-31','2026-12-01','2026-00-01']:
            with self.subTest(day=day):
                s=self.run_flow([ROW,'🧾 Thông tin / ký nhận','✍️ Xác nhận ngày ký nhận'],[day])
                self.assertFalse(saved(s).get('signedDay'))
    def test_archiving_keeps_fee(self):
        r=record(signedDay='2026-11-12',signedMonth='2026-11',fee='5000',feeReversed='0')
        s=self.run_flow([ROW,'🧾 Thông tin / ký nhận','🗃️ Cất đơn / khôi phục',OPTIONS,'📊 Công đơn & đối soát'],files=files_for(r))
        self.assertEqual(saved(s)['deleted'],'1');self.assertIn('1 đơn · 5.000₫',s.last_ui[0])
    def test_show_qr_uses_outstanding_not_original_total_and_never_records_payment(self):
        f=files_for(record(cash='665000'),extra=qr_files())
        s=self.run_flow([ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],files=f)
        qs=parse_qs(urlparse(s.network[0]).query);self.assertEqual(qs['amount'],['1500000'])
        self.assertEqual((saved(s)['cash'],saved(s)['bank']),('665000','0'))
        self.assertEqual(len(s.previews),1)
    def test_qr_cache_works_without_new_network_request(self):
        f=files_for(extra=qr_files())
        s=self.run_flow([ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],files=f)
        t=self.run_flow([ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],files=s.files)
        self.assertEqual(t.network,[])
    def test_fully_paid_order_never_generates_zero_qr(self):
        f=files_for(record(cash='665000',bank='1500000'),extra=qr_files())
        s=self.run_flow([ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],files=f)
        self.assertFalse(s.network);self.assertFalse(s.previews)
    def test_mixed_qr_does_not_commit_proposed_cash(self):
        s=self.run_flow([ROW,'🤝 Tiền mặt + CK','📲 Hiện QR phần cần chuyển'],['665000'],files_for(extra=qr_files()))
        self.assertEqual(parse_qs(urlparse(s.network[0]).query)['amount'],['1500000'])
        self.assertEqual(saved(s)['cash'],'0');self.assertEqual(saved(s)['bank'],'0')
    def test_first_qr_setup_keeps_leading_zero_and_encodes_name(self):
        s=self.run_flow([OPTIONS,'🏦 Thiết lập QR',0,'✅ Tạo và lưu QR'],['CÔNG TY A & B','0012345678','ACB'])
        cfg=json.loads(s.files[APP+'QR/config.json'].data)
        self.assertEqual(cfg['account'],'0012345678');self.assertEqual(cfg['bin'],'970416')
        qs=parse_qs(urlparse(s.network[0]).query);self.assertEqual(qs['accountName'],['CÔNG TY A & B'])
        self.assertEqual(saved(s)['cash'],'0')
    def test_base_qr_is_loaded_without_network(self):
        s=self.run_flow([OPTIONS,'🏦 Thiết lập QR','👁️ Xem QR gốc đã lưu'],files=files_for(extra=qr_files()))
        self.assertEqual(s.network,[]);self.assertEqual(s.previews[0].data,'BASE')
    def test_change_recipient_invalidates_amount_cache(self):
        a=self.run_flow([ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],files=files_for(extra=qr_files()))
        f=copy.deepcopy(a.files);f.update(qr_files(account='999999999'))
        b=self.run_flow([ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],files=f)
        self.assertEqual(len(b.network),1);self.assertIn('999999999',b.network[0])
    def test_bank_change_resets_company_verification(self):
        s=self.run_flow([ROW,'🏦 Chuyển khoản / QR','✅ Ghi CK khách báo','✅ Lưu khoản thu'],['1000000'],files_for(record(bank='500000',bankVerified='500000')))
        self.assertEqual(saved(s)['bankVerified'],'0')
    def test_quick_call_only_receives_chosen_image(self):
        s=self.run_flow([ROW,'📞 Liên hệ / chỉ đường','📞 Quick Call Image'])
        self.assertEqual(len(s.calls),1);self.assertEqual(s.calls[0][0],'Quick Call Image')
        self.assertEqual(s.calls[0][1].path,APP+'Ảnh Đơn Hàng/'+record()['filename'])
    def test_deferred_report_has_signature_and_invoice_but_no_fake_bank_money(self):
        s=self.run_flow([ROW,'🏦 Chuyển khoản / QR','⏳ Khách hẹn CK sau','📷 Chụp ảnh','✅ Lưu và mở chia sẻ','⏸ Chưa gửi / chỉ xem'],['Khách hẹn chuyển sau'])
        self.assertEqual(len(s.shares[0]),2);self.assertEqual(saved(s)['bank'],'0')
        self.assertFalse(saved(s)['reportSentAt']);self.assertTrue(saved(s)['latestReport'])
    def test_mixed_report_three_images_and_manual_sent_confirmation(self):
        r=record(cash='665000',bank='1500000',outcome='delivered')
        s=self.run_flow([ROW,'📦 Giao hàng & báo cáo','📝 Chuẩn bị báo cáo','🤝 Tiền mặt + chuyển khoản','📷 Chụp ảnh','🖼️ Chọn từ Ảnh','✅ Lưu và mở chia sẻ','✅ Đã gửi nhóm'],['Nội dung đã kiểm tra'],files_for(r))
        self.assertEqual(len(s.shares[0]),3);self.assertTrue(saved(s)['reportSentAt'])
        self.assertEqual((saved(s)['cash'],saved(s)['bank']),('665000','1500000'))
        self.assertTrue(all(max(f.width,f.height)<=2048 and f.image_format=='JPEG' for f in s.shares[0]))
    def test_cancel_proof_does_not_write_or_send(self):
        f=files_for();s=self.run_flow([ROW,'🏦 Chuyển khoản / QR','⏳ Khách hẹn CK sau','↩️ Về hồ sơ'],files=f)
        self.assertEqual(s.files[APP+'orders.json'].data,f[APP+'orders.json'].data);self.assertFalse(s.shares)
    def test_resend_never_adds_money_or_commission(self):
        r=record(cash='665000',bank='1500000',signedDay='2026-11-12',signedMonth='2026-11',fee='5000')
        a=self.run_flow([ROW,'📦 Giao hàng & báo cáo','📝 Chuẩn bị báo cáo','🤝 Tiền mặt + chuyển khoản','📷 Chụp ảnh','🖼️ Chọn từ Ảnh','✅ Lưu và mở chia sẻ','⏸ Chưa gửi / chỉ xem'],['Báo cáo mẫu'],files_for(r))
        b=self.run_flow([ROW,'📦 Giao hàng & báo cáo','♻️ Gửi lại báo cáo gần nhất','⏸ Chưa gửi / chỉ xem'],files=a.files)
        self.assertEqual(len(b.shares),1);self.assertEqual(saved(b)['cash'],'665000');self.assertEqual(saved(b)['fee'],'5000')
    def test_cash_handover_cannot_reduce_earned_fee(self):
        r=record(cash='665000',signedDay='2026-11-12',signedMonth='2026-11',fee='5000')
        s=self.run_flow([OPTIONS,'📊 Công đơn & đối soát','💵 Ghi nộp tiền mặt','✅ Đã nộp tiền','💰 Số tiền đang giữ'],['600000'],files_for(r))
        self.assertEqual(ledger(s)['_cashHanded'],'600000');self.assertEqual(saved(s)['fee'],'5000');self.assertTrue(any('65.000₫' in message for title,message in s.alerts))
    def test_receipt_correction_below_handed_cash_is_blocked(self):
        f=files_for(record(cash='665000'));l=json.loads(f[APP+'orders.json'].data);l['_cashHanded']='600000';f[APP+'orders.json'].data=json.dumps(l)
        s=self.run_flow([ROW,'💵 Thu tiền mặt','✅ Lưu khoản thu'],['100000'],f)
        self.assertEqual(saved(s)['cash'],'665000');self.assertTrue(any('Khoản thu' in t for t,m in s.alerts))
    def test_export_csv_contains_signed_failure_and_escapes_formula(self):
        r=record(name='=TIỆM THỬ',signedDay='2026-11-12',signedMonth='2026-11',fee='5000',outcome='failed')
        s=self.run_flow([OPTIONS,'📊 Công đơn & đối soát','💾 Xuất CSV công tháng'],files=files_for(r))
        content=s.shares[0].data;self.assertIn("'=TIỆM THỬ",content);self.assertIn('5000',content)
    def test_display_limit_persists_and_options_stays_last(self):
        other=record(id='b'*64,name='MỚI',filename='NEW.png',createdAt='2026-11-13T10:00:00+07:00')
        s=self.run_flow([OPTIONS,'🔢 Giới hạn hiển thị'],['1'],files_for(record(),other))
        self.assertEqual(s.last_ui[1],['MỚI — 2.165.000₫',OPTIONS]);self.assertEqual(ledger(s)['_displayLimit'],'1')
    def test_invalid_primary_is_never_overwritten_or_reset(self):
        f=files_for();f[APP+'orders.json'].data='{broken'
        s=self.run_flow(files=f);self.assertEqual(s.files[APP+'orders.json'].data,'{broken')
        self.assertFalse(s.last_ui)
    def test_large_ledger_still_opens_only_metadata(self):
        rs=[record(id=f'{n:064x}',name=f'TIỆM {n}',filename=f'{n}.png') for n in range(150)]
        s=self.run_flow(files=files_for(*rs))
        self.assertEqual(len(s.last_ui[1]),51);self.assertFalse(s.previews);self.assertFalse(s.network)
        self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in s.file_reads))

    def test_actual_vietqr_svg_keeps_vector_qr_and_all_embedded_images(self):
        svg=Path(__file__).with_name('fixtures').joinpath('vietqr-public-example.svg').read_text()
        s=Simulator(self.w,files=files_for(extra=qr_files()),choices=[ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],now=NOW)
        s.network_handler=lambda url:File('network/qr.svg',svg)
        s.run()
        html=text(s.previews[0]);encoded=re.search(r'data:image/svg\+xml;base64,([^\"]+)',html)[1]
        actual=base64.b64decode(encoded).decode()
        self.assertEqual(svg,actual);self.assertIn('<path ',actual)
        self.assertIn('data:image/png;base64,',actual);self.assertIn('data:image/jpeg;base64,',actual)
        self.assertTrue(s.previews[0].name.endswith('.html'))
    def test_bad_svg_does_not_replace_saved_config(self):
        f=files_for(extra=qr_files());original=f[APP+'QR/config.json'].data
        s=Simulator(self.w,files=f,choices=[OPTIONS,'🏦 Thiết lập QR','⚙️ Thiết lập / đổi tài khoản',0,'✅ Tạo và lưu QR'],answers=['TEST COMPANY','123456789','ACB'],now=NOW)
        s.network_handler=lambda url:File('network/error.html','<html>unavailable</html>')
        s.run();self.assertEqual(s.files[APP+'QR/config.json'].data,original)
    def test_svg_is_rendered_as_an_image_with_no_inline_script(self):
        for body in ['<script>alert(1)</script>','<image href="https://example.com/a.png"/>','<path onclick="alert(1)"/>']:
            with self.subTest(body=body):
                s=Simulator(self.w,files=files_for(extra=qr_files()),choices=[ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],now=NOW)
                s.network_handler=lambda url:File('network/qr.svg','<svg><path d="M0 0h1v1h-1z"/>'+body+'</svg>')
                s.run();self.assertEqual(len(s.previews),1)
                self.assertNotIn('<script>',text(s.previews[0]));self.assertIn('default-src',text(s.previews[0]))
    def test_restore_existing_old_image_preserves_money_and_fee(self):
        r=record();r['id']=hashlib.sha256(r['filename'].encode()).hexdigest();r.update(cash='665000',signedDay='2026-11-12',fee='5000')
        f=files_for(r);f.pop(APP+'Ảnh Đơn Hàng/'+r['filename'])
        chosen=File('picked/'+r['filename'],'RESTORED IMAGE',NOW,3200,1800,'PNG')
        s=Simulator(self.w,files=f,choices=[OPTIONS,'🛠️ Dữ liệu / công cụ','📂 Nạp/khôi phục ảnh cũ'],now=NOW)
        s.file_picks=[chosen];s.run()
        self.assertEqual(saved(s,r['id'])['cash'],'665000');self.assertEqual(saved(s,r['id'])['fee'],'5000')
        self.assertIn(APP+'Ảnh Đơn Hàng/'+r['filename'],s.files)

    def test_bill33_sidecar_aliases_existing_v32_filename_record(self):
        key='20261112082214639-123456';mid=hashlib.sha256(('sen-bill-v1:'+key).encode()).hexdigest()
        filename='TIỆM THỬ - 2.165.000 · '+key+'.png';oldid=hashlib.sha256(filename.encode()).hexdigest()
        r=record(id=oldid,filename=filename,cash='665000',bank='1500000',signedDay='2026-11-12',signedMonth='2026-11',fee='5000',invoiceCode='',address='')
        meta=dict(schema='sen-bill-v1',imageKey=key,id=mid,filename=filename,name=r['name'],total=r['total'],invoiceCode='3856',address='12 TEST')
        path=APP+'Đơn mới/'+mid+'.json';f=files_for(r,extra={path:File(path,json.dumps(meta))})
        l=json.loads(f[APP+'orders.json'].data);l.pop('_legacyIndexDone',None);f[APP+'orders.json'].data=json.dumps(l)
        a=self.run_flow(files=f)
        self.assertNotIn(mid,ledger(a));self.assertEqual(saved(a,oldid)['cash'],'665000');self.assertEqual(saved(a,oldid)['fee'],'5000')
        self.assertEqual(saved(a,oldid)['invoiceCode'],'3856');self.assertEqual(ledger(a)['_bill_'+mid],oldid)
        b=self.run_flow(files=a.files);self.assertNotIn(path,b.file_reads)

    def test_portrait_invoice_rotates_preview_only(self):
        f=files_for();original=f[APP+'Ảnh Đơn Hàng/'+record()['filename']];original.width=1000;original.height=2000
        s=self.run_flow([ROW,'👁️ Xem phiếu'],files=f)
        self.assertEqual((s.previews[0].width,s.previews[0].height),(2000,1000))
        stored=s.files[original.path];self.assertEqual((stored.width,stored.height),(1000,2000))
    def test_copy_shop_name_does_not_read_photos(self):
        s=self.run_flow([ROW,'📞 Liên hệ / chỉ đường','📋 Sao chép tên tiệm'])
        self.assertEqual(s.clipboard,'TIỆM THỬ');self.assertFalse(any('/Ảnh Đơn Hàng/' in p for p in s.file_reads))
    def test_monthly_json_separates_commission_and_all_time_balances(self):
        r=record(cash='665000',signedDay='2026-11-12',signedMonth='2026-11',fee='5000')
        s=self.run_flow([OPTIONS,'📊 Công đơn & đối soát','💾 Lưu tổng kết JSON'],files=files_for(r))
        data=json.loads(text(s.shares[0]));self.assertEqual(data['signedFeeTotal'],'5000');self.assertEqual(data['cashHeldAllTime'],'665000')

if __name__=='__main__':unittest.main()
