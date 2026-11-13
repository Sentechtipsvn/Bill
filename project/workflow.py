"""Ảnh đơn hàng 4: metadata-first native Shortcuts, no image enumeration at launch."""
from pathlib import Path
import json, plistlib
from shortcut_builder import Builder, ref, token, dyn, current_time, storage, BUILD, VERSION
from shared import field,put_object,save_data,load_ui

ID = r'\A[a-f0-9]{64}\z'
MONEY = r'\A(?:0|[1-9][0-9]{0,11}|1000000000000)\z'
MONTH = r'\A20[0-9]{2}-(?:0[1-9]|1[0-2])\z'
DAY = r'\A(?:20[0-9]{2}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12][0-9]|3[01])|(?:0[469]|11)-(?:0[1-9]|[12][0-9]|30)|02-(?:0[1-9]|1[0-9]|2[0-8]))|20(?:[02468][048]|[13579][26])-02-29)\z'
FILENAME = r'\A[^/\\\x00-\x1f]{1,240}\.(?:png|jpg|jpeg|heic|heif|webp)\z'
FLAT = r'\A\s*\{\s*"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"\s*:\s*"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"(?:\s*,\s*"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"\s*:\s*"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*")*\s*\}\s*\z'
OPTIONS = '⚙️ Tuỳ chỉnh'
BACK = '↩️ Danh sách đơn'

def val(b,key,source='CurrentRecord',default=''):
    return field(source,key)

def put(b, key, value): b.put(ref('Draft'), key, value, 'Draft')

def draft(b): b.set('Draft', ref('CurrentRecord'))

def commit(b, after='order', action='Cập nhật hồ sơ'):
    current_time(b)
    put(b, 'updatedAt', ref('NowISO'))
    b.dictionary({'at':ref('NowISO'),'action':action,'cash':val(b,'cash','Draft','0'),
                  'bank':val(b,'bank','Draft','0'),'outcome':val(b,'outcome','Draft')}, 'Event')
    old=val(b,'events','Draft')
    b.text(token(old,'\n',b.text(ref('Event'))),'EventLog')
    put(b,'events',ref('EventLog'))
    b.put(ref('Ledger'), ref('SelectedID'), b.text(ref('Draft')), 'Ledger')
    save_to(b,after)

def save_to(b,after):
    b.set('SaveReturn',after); b.go('save')

def number_input(b, prompt, default, variable, maximum='1000000000000'):
    # The default may refer to the output variable itself (display limit/fee).
    # Snapshot it before asking; never gate an Ask on a cleared dictionary value.
    suffix=str(len(b.actions));accepted='NumberAccepted_'+suffix
    frozen='NumberDefault_'+suffix;b.set(frozen,default);b.set(accepted,'0')
    with b.repeat(3):
        with b.if_(ref(accepted),'eq','0'):
            answer=b.ask(prompt,ref(frozen),'Number')
            with b.if_(b.match(answer,MONEY)):
                with b.if_(answer,'le',maximum): b.set(variable,answer);b.set(accepted,'1')
                with b.if_(answer,'gt',maximum): b.alert('Vượt số tiền còn được ghi','Chưa thay đổi sổ. Sếp nhập lại số tiền thực tế.')
            with b.if_(b.match(answer,MONEY),'empty'): b.alert('Số tiền chưa hợp lệ','Nhập số nguyên VND, không chấm/phẩy, không âm.')
    with b.if_(ref(accepted),'eq','0'): b.stop()
    return ref(variable)

def load_invoice(b):
    b.set('ImageReady','0')
    filename=val(b,'filename')
    with b.if_(b.match(filename,'(?i)'+FILENAME)):
        b.load(ref('ImagesFolder'),filename,'InvoiceFile')
        images=b.add('filter.images',WFContentItemInputParameter=ref('InvoiceFile'),WFContentItemLimitEnabled=False)
        with b.if_(b.count(images),'gt',0): b.set('InvoiceFile',b.first(images));b.set('ImageReady','1')
    with b.if_(ref('ImageReady'),'eq','0'):
        b.alert('Chưa đọc được ảnh của đơn này','Sổ vẫn còn. Tải đúng ảnh trong Tệp/iCloud rồi thử lại; hoặc vào Tuỳ chỉnh → Nạp/khôi phục ảnh cũ.')
        b.go('order')

def compress(b, image, output):
    # Exact coercion/property envelopes from the supplied native 3.2 shortcut.
    src=f'CompressSource_{len(b.actions)}';b.set(src,image)
    properties=[{'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFImageContentItem'}]
    w=ref(src,props=properties+[{'Type':'WFPropertyVariableAggrandizement','PropertyName':'Width'}])
    h=ref(src,props=properties+[{'Type':'WFPropertyVariableAggrandizement','PropertyName':'Height'}])
    b.set(output,ref(src))
    with b.if_(w,'ge',h):
        with b.if_(w,'gt',2048):
            nh=b.add('round',WFInput=b.math(h,'*2048/',w),WFRoundMode='Normal',WFRoundTo='Ones Place')
            b.set(output,b.add('image.resize',WFImage=ref(src),WFImageResizeKey='Size',WFImageResizeWidth=2048,WFImageResizeHeight=nh))
        b.otherwise()
        with b.if_(h,'gt',2048):
            nw=b.add('round',WFInput=b.math(w,'*2048/',h),WFRoundMode='Normal',WFRoundTo='Ones Place')
            b.set(output,b.add('image.resize',WFImage=ref(src),WFImageResizeKey='Size',WFImageResizeWidth=nw,WFImageResizeHeight=2048))
    b.set(output,b.add('image.convert',WFInput=ref(output),WFImageFormat='JPEG',WFImageCompressionQuality=0.85,WFImagePreserveMetadata=False))

def pick_proof(b, label, output):
    with b.menu(label,['📷 Chụp ảnh','🖼️ Chọn từ Ảnh','↩️ Về hồ sơ']):
        b.case('📷 Chụp ảnh');b.set(output,b.add('takephoto',WFCameraCaptureDevice='Back',WFCameraCaptureShowPreview=True,WFPhotoCount=1))
        b.case('🖼️ Chọn từ Ảnh');b.set(output,b.add('selectphoto',WFSelectMultiplePhotos=False))
        b.case('↩️ Về hồ sơ');b.go('order')

def qr_url(b, amount):
    name=b.add('urlencode',WFInput=dyn(val(b,'name','QRConfig')))
    memo=b.add('urlencode',WFInput=dyn(ref('QRMemo')))
    if amount=='':
        return b.text(token('https://img.vietqr.io/image/',val(b,'bin','QRConfig'),'-',val(b,'account','QRConfig'),'-compact2.svg?accountName=',name))
    return b.text(token('https://img.vietqr.io/image/',val(b,'bin','QRConfig'),'-',val(b,'account','QRConfig'),
                        '-compact2.svg?amount=',amount,'&addInfo=',memo,'&accountName=',name))

def fetch_qr(b,url,output):
    # Keep downloaded SVG/PNG/JPEG as BINARY. Get Text on an SVG image may
    # return its filename/OCR on iOS, so never parse that coercion as XML.
    response=b.add('downloadurl',WFURL=dyn(url))
    encoded=b.add('base64encode',WFInput=response)
    encoded=b.replace(encoded,r'\s+','')
    b.set(output,'');b.set('QRVector',response);b.set('QRMime','');b.set('QRExt','svg')
    for pattern,mime in [(r'\APHN2Z','image/svg+xml'),(r'\APD94bWw','image/svg+xml'),(r'\AiVBORw0KGgo','image/png'),(r'\A/9j/','image/jpeg')]:
        with b.if_(b.match(encoded,pattern)):
            b.set('QRMime',mime);b.set('QRExt',{'image/svg+xml':'svg','image/png':'png','image/jpeg':'jpg'}[mime])
    with b.if_(ref('QRMime')):
        b.text(token('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'"><title>VietQR</title><style>html,body{margin:0;background:white}body{min-height:100vh;display:flex;align-items:center;justify-content:center}img{display:block;width:100%;max-width:540px;height:auto}</style><img alt="VietQR" src="data:',ref('QRMime'),';base64,',encoded,'"></html>'),output)
    return ref(output)

def build():
    b=Builder()
    b.add('comment',WFCommentActionText=f'Phiếu Giao Hàng {VERSION} · © Sentechtipsvn')
    for var,path in [('ReportsFolder','Báo cáo'),('MonthlyFolder','Số lượng đơn hàng'),('QRFolder','QR')]:
        b.set(var,b.add('file.createfolder',WFFolder=ref('AppFolder'),WFFilePath=path))
    current_time(b)
    b.set('DiskHash','missing');b.set('Dirty','0');b.set('Scope','active');b.set('Search','');b.set('StatsMonth',ref('CurrentMonth'))
    b.set('SelectedID','');b.set('QRReturn','options');b.set('QRMemo','');b.set('DisplayLimit','50');b.set('FeeRate','5000');b.set('CashHanded','0')
    b.load(ref('AppFolder'),'orders.json','Primary')
    with b.if_(ref('Primary')):
        b.text(ref('Primary'),'OriginalJSON');b.hash(ref('OriginalJSON'),'DiskHash')
        with b.if_(b.match(ref('OriginalJSON'),FLAT),'empty'):
            b.alert('Sổ đơn chưa đọc được','Không tạo sổ rỗng và không ghi đè. Giữ orders.json / orders.backup.json để khôi phục.');b.stop()
        b.parse(ref('OriginalJSON'),'Ledger')
        with b.if_(b.get(ref('Ledger'),'_schema'),'ne','sen-orders-v3'):
            b.alert('Khác định dạng sổ','Chỉ nhận sen-orders-v3 từ Ảnh đơn hàng 3.2.0. Dữ liệu được giữ nguyên.');b.stop()
        for key,var in [('_displayLimit','DisplayLimit'),('_feeRate','FeeRate'),('_cashHanded','CashHanded')]:
            value=b.get(ref('Ledger'),key)
            with b.if_(b.match(value,MONEY)): b.set(var,value)
        b.otherwise()
        backup=b.load(ref('AppFolder'),'orders.backup.json')
        with b.if_(backup):
            b.alert('Có bản sao lưu cũ','Chưa tạo sổ mới để tránh bỏ mất khoản thu. Khôi phục orders.backup.json thành orders.json trong Tệp rồi chạy lại.');b.stop()
        b.dictionary({'_schema':'sen-orders-v3','_version':VERSION},'Ledger')
    b.go('sync')
    with b.repeat(500):
        with b.route('sync'):
            b.set('NewCount','0');b.set('BadCount','0')
            with b.if_(b.get(ref('Ledger'),'_legacyIndexDone'),'empty'):
                entries=b.add('file.getfoldercontents',WFFolder=ref('IncomingFolder'),Recursive=False)
                with b.each(entries,'MetaFile'):
                    filename=b.add('getitemname',WFInput=ref('MetaFile'))
                    b.set('MetaName',filename)
                    with b.if_(b.match(ref('MetaName'),r'\.json\z'),'empty'):
                        ext=b.add('properties.files',WFInput=ref('MetaFile'),WFContentItemPropertyName='File Extension')
                        with b.if_(ext,'eq','json'): b.text(token(ref('MetaName'),'.json'),'MetaName')
                    filename=ref('MetaName')
                    # Index filenames only. Already indexed sidecars are never opened again.
                    with b.if_(b.match(filename,r'\A[a-f0-9]{64}\.json\z')):
                        mid=b.replace(filename,r'\.json\z','')
                        b.set('KnownMeta','0')
                        with b.if_(b.get(ref('Ledger'),mid)): b.set('KnownMeta','1')
                        with b.if_(b.get(ref('Ledger'),b.text(token('_bill_',mid)))): b.set('KnownMeta','1')
                        with b.if_(ref('KnownMeta'),'eq','0'):
                            b.set('MetaOK','1');b.text(ref('MetaFile'),'MetaJSON')
                            b.dictionary(var='Meta')
                            with b.if_(b.match(ref('MetaJSON'),FLAT)): b.parse(ref('MetaJSON'),'Meta')
                            with b.if_(b.match(ref('MetaJSON'),FLAT),'empty'): b.set('MetaOK','0')
                            with b.if_(val(b,'schema','Meta'),'ne','sen-bill-v1'): b.set('MetaOK','0')
                            with b.if_(val(b,'id','Meta'),'ne',mid): b.set('MetaOK','0')
                            expected=b.hash(b.text(token('sen-bill-v1:',val(b,'imageKey','Meta'))))
                            with b.if_(expected,'ne',mid): b.set('MetaOK','0')
                            with b.if_(b.match(val(b,'filename','Meta'),'(?i)'+FILENAME),'empty'): b.set('MetaOK','0')
                            b.set('MetaFilenameOK','0')
                            with b.if_(val(b,'filename','Meta'),'contains',b.text(token(' · ',val(b,'imageKey','Meta'),'.'))): b.set('MetaFilenameOK','1')
                            with b.if_(ref('MetaFilenameOK'),'eq','0'): b.set('MetaOK','0')
                            with b.if_(b.match(val(b,'name','Meta'),r'\p{L}'),'empty'): b.set('MetaOK','0')
                            with b.if_(b.match(val(b,'total','Meta'),MONEY),'empty'): b.set('MetaOK','0')
                            with b.if_(ref('MetaOK'),'eq','1'):
                                oldid=b.hash(val(b,'filename','Meta'))
                                oldrecord=b.get(ref('Ledger'),oldid)
                                with b.if_(oldrecord):
                                    # v3.2 indexed filenames; Bill v3.3 indexes imageKey.
                                    # Alias the new metadata ID to the old record; never
                                    # create a second order or reset its financial fields.
                                    b.parse(oldrecord,'MergedRecord')
                                    for field in ['invoiceCode','address','phone','deliveryNote']:
                                        with b.if_(val(b,field,'MergedRecord'),'empty'):
                                            b.put(ref('MergedRecord'),field,val(b,field,'Meta'),'MergedRecord')
                                    b.put(ref('Ledger'),oldid,b.text(ref('MergedRecord')),'Ledger')
                                    b.put(ref('Ledger'),b.text(token('_bill_',mid)),oldid,'Ledger')
                                    b.otherwise()
                                    b.dictionary({'id':mid,'filename':val(b,'filename','Meta'),'name':val(b,'name','Meta'),
                                        'total':val(b,'total','Meta'),'cash':'0','bank':'0','createdAt':val(b,'createdAt','Meta'),
                                        'createdMonth':val(b,'createdMonth','Meta'),'invoiceCode':val(b,'invoiceCode','Meta'),
                                        'address':val(b,'address','Meta'),'phone':val(b,'phone','Meta'),'deliveryNote':val(b,'deliveryNote','Meta'),
                                        'signedDay':'','signedMonth':'','fee':'0','feeReversed':'0','outcome':'pending',
                                        'deliveredAt':'','deliveryMonth':'','deleted':'0','destroyed':'0','cancelled':'0',
                                        'latestReport':'','reportHistory':'','note':'','bankVerified':'0','reportSentAt':'','events':''},'NewRecord')
                                    b.put(ref('Ledger'),mid,b.text(ref('NewRecord')),'Ledger')
                                b.math(ref('NewCount'),'+1',var='NewCount');b.set('Dirty','1')
                                b.otherwise();b.math(ref('BadCount'),'+1',var='BadCount')
                with b.if_(ref('BadCount'),'gt',0): b.alert('Có gói Bill cần kiểm tra',token(ref('BadCount'),' gói không khớp thông tin. Chưa nhập các gói đó; sổ cũ được giữ.'))
                b.put(ref('Ledger'),'_legacyIndexDone','1','Ledger');b.set('Dirty','1')
            b.go('sync41')

        from legacy_catalog import index_legacy
        with b.route('sync41'):
            index_legacy(b)
        from synchronization import sync41
        sync41(b)

        with b.route('main'):
            b.empty_list('SortedRows')
            with b.each(b.keys(ref('Ledger')),'Key'):
                with b.if_(b.match(ref('Key'),ID)):
                    rr=b.parse(b.get(ref('Ledger'),ref('Key')))
                    b.set('ListRecord',rr);b.set('Include','1')
                    if True:
                        with b.if_(val(b,'deleted','ListRecord','0'),'eq','1'): b.set('Include','0')
                        with b.if_(val(b,'destroyed','ListRecord','0'),'eq','1'): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','trash'):
                            b.set('Include','0')
                            with b.if_(val(b,'deleted','ListRecord','0'),'eq','1'): b.set('Include','1')
                        with b.if_(ref('Scope'),'eq','pending'):
                            with b.if_(val(b,'deliveredAt','ListRecord')): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','delivered'):
                            with b.if_(val(b,'deliveredAt','ListRecord'),'empty'): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','cash'):
                            with b.if_(val(b,'cash','ListRecord','0'),'le',0): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','bank'):
                            with b.if_(val(b,'bank','ListRecord','0'),'le',0): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','mixed'):
                            with b.if_(val(b,'cash','ListRecord','0'),'le',0): b.set('Include','0')
                            with b.if_(val(b,'bank','ListRecord','0'),'le',0): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','debt'):
                            debt=b.math(val(b,'total','ListRecord'),'-',val(b,'cash','ListRecord','0'),'-',val(b,'bank','ListRecord','0'))
                            with b.if_(debt,'le',0): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','unsigned'):
                            with b.if_(val(b,'signedDay','ListRecord')): b.set('Include','0')
                        with b.if_(ref('Scope'),'eq','unreported'):
                            with b.if_(val(b,'reportSentAt','ListRecord')): b.set('Include','0')
                    with b.if_(ref('Search')):
                        searchtext=b.fold(b.text(token(val(b,'name','ListRecord'),' ',val(b,'invoiceCode','ListRecord'),' ',val(b,'phone','ListRecord'))))
                        b.set('Found','0')
                        with b.if_(searchtext,'contains',ref('Search')): b.set('Found','1')
                        with b.if_(ref('Found'),'eq','0'): b.set('Include','0')
                    with b.if_(ref('Include'),'eq','1'):
                        b.append('SortedRows',b.text(token(val(b,'createdAt','ListRecord'),'|',ref('Key'))))
            # This is the native Sort Lines recipe: Filter Files sorts TEXT values, not invoice files.
            sortedrows=b.add('filter.files',WFContentItemInputParameter=ref('SortedRows'),WFContentItemSortProperty='Name',WFContentItemSortOrder='Z to A',WFContentItemLimitEnabled=False)
            b.empty_list('Rows');b.dictionary(var='RowMap');b.set('Shown','0')
            with b.each(sortedrows,'SortRow'):
                match=b.match(b.text(ref('SortRow')),r'[a-f0-9]{64}\z');rid=b.text(b.first(match))
                rr=b.parse(b.get(ref('Ledger'),rid));b.set('ListRecord',rr)
                b.parse(b.get(ref('OrdersData'),val(b,'dataID','ListRecord')),'DisplayData')
                title=b.text(token(val(b,'Name','DisplayData'),' — ',b.money(val(b,'Money','DisplayData')),'₫'))
                rk=b.hash(title);old=b.get(ref('RowMap'),rk)
                b.set('CanShow','1')
                with b.if_(ref('DisplayLimit'),'gt',0):
                    with b.if_(ref('Shown'),'ge',ref('DisplayLimit')):
                        with b.if_(old,'empty'): b.set('CanShow','0')
                with b.if_(ref('CanShow'),'eq','1'):
                    with b.if_(old,'empty'): b.append('Rows',title);b.math(ref('Shown'),'+1',var='Shown')
                    b.text(token(old,'\n',rid),'MappedIDs');b.replace(ref('MappedIDs'),r'^\n','',var='MappedIDs')
                    b.put(ref('RowMap'),rk,ref('MappedIDs'),'RowMap')
            b.append('Rows',b.text(OPTIONS))
            pick=b.choose(ref('Rows'),token('Phiếu Giao Hàng ',b.fmtdate(ref('Now'),'MM-yyyy')))
            with b.if_(pick,'eq',OPTIONS): b.go('options')
            with b.if_(pick,'ne',OPTIONS):
                ids=b.split(b.get(ref('RowMap'),b.hash(pick)))
                with b.if_(b.count(ids),'gt',1):
                    b.empty_list('DuplicateRows');b.dictionary(var='DuplicateMap');b.set('DuplicateNumber','0')
                    with b.each(ids,'DuplicateID'):
                        d=b.parse(b.get(ref('Ledger'),ref('DuplicateID')));b.set('DuplicateRecord',d)
                        b.math(ref('DuplicateNumber'),'+1',var='DuplicateNumber')
                        label=b.text(token('Số ',val(b,'invoiceCode','DuplicateRecord','Chưa có số'),' · ',val(b,'createdAt','DuplicateRecord'),' · #',ref('DuplicateNumber')))
                        b.append('DuplicateRows',label);b.put(ref('DuplicateMap'),b.hash(label),ref('DuplicateID'),'DuplicateMap')
                    selected=b.choose(ref('DuplicateRows'),'Chọn phiếu')
                    b.get(ref('DuplicateMap'),b.hash(selected),'SelectedID')
                    b.otherwise();b.set('SelectedID',b.first(ids))
                b.go('order')

        with b.route('order'):
            b.parse(b.get(ref('Ledger'),ref('SelectedID')),'CurrentRecord')
            b.set('OName',val(b,'name'));b.set('OCode',val(b,'invoiceCode','CurrentRecord','Chưa có số'))
            b.set('OTotal',val(b,'total'));b.set('OCash',val(b,'cash','CurrentRecord','0'));b.set('OBank',val(b,'bank','CurrentRecord','0'))
            b.math(ref('OTotal'),'-',ref('OCash'),'-',ref('OBank'),var='Remaining')
            b.text(token(ref('OName'),' — ',b.money(ref('OTotal')),'₫'),'OrderTitle')
            with b.menu(ref('OrderTitle'),['👁️ Xem phiếu','💵 Thu tiền mặt','🏦 Chuyển khoản / QR','🤝 Tiền mặt + CK','📦 Giao hàng & báo cáo','📞 Liên hệ / chỉ đường','🧾 Thông tin / ký nhận',BACK]):
                for label,route in [('👁️ Xem phiếu','image'),('💵 Thu tiền mặt','cash'),('🏦 Chuyển khoản / QR','bank'),('🤝 Tiền mặt + CK','mixed'),('📦 Giao hàng & báo cáo','delivery'),('📞 Liên hệ / chỉ đường','contact'),('🧾 Thông tin / ký nhận','details'),(BACK,'main')]: b.case(label);b.go(route)

        with b.route('image'):
            load_invoice(b)
            with b.if_(ref('ImageReady'),'eq','1'):
                image_props=[{'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFImageContentItem'}]
                w=ref('InvoiceFile',props=image_props+[{'Type':'WFPropertyVariableAggrandizement','PropertyName':'Width'}])
                h=ref('InvoiceFile',props=image_props+[{'Type':'WFPropertyVariableAggrandizement','PropertyName':'Height'}])
                b.set('PreviewFile',ref('InvoiceFile'))
                with b.if_(w,'lt',h): b.set('PreviewFile',b.add('image.rotate',WFImage=ref('InvoiceFile'),WFImageRotateAmount=90))
                b.add('previewdocument',WFInput=ref('PreviewFile'));b.go('order')

        with b.route('details'):
            signed=val(b,'signedDay');fee=val(b,'fee','CurrentRecord','0')
            with b.menu('Thông tin',['✍️ Xác nhận ngày ký nhận','✏️ Sửa thông tin','🗃️ Cất đơn / khôi phục','🚫 Điều chỉnh công nhập nhầm',BACK]):
                b.case('✍️ Xác nhận ngày ký nhận');b.go('sign')
                b.case('✏️ Sửa thông tin');b.go('edit')
                b.case('🗃️ Cất đơn / khôi phục');draft(b);b.set('ArchiveTarget','1')
                with b.if_(val(b,'deleted','CurrentRecord','0'),'eq','1'): b.set('ArchiveTarget','0')
                put(b,'deleted',ref('ArchiveTarget'));commit(b,'main','Đổi trạng thái cất đơn; giữ công và tiền')
                b.case('🚫 Điều chỉnh công nhập nhầm');b.go('reverse-fee')
                b.case(BACK);b.go('main')

        with b.route('sign'):
            with b.if_(val(b,'signedDay')):
                b.alert('Đơn đã xác nhận ký nhận',token('Ngày ',val(b,'signedDay'),' · Công đã chốt ',b.money(val(b,'fee','CurrentRecord','0')),'₫. Không cộng thêm lần nữa.'));b.go('order')
                b.otherwise()
                today=b.fmtdate(ref('Now'),'yyyy-MM-dd');chosen=b.ask('Ngày Sếp ký nhận đi giao (YYYY-MM-DD; không phải ngày khách ký nhận hàng)',today)
                b.set('ValidDay','0')
                with b.if_(b.match(chosen,DAY)):
                    dn=b.replace(chosen,'-','',regex=False);tn=b.replace(today,'-','',regex=False)
                    with b.if_(dn,'le',tn): b.set('ValidDay','1')
                with b.if_(ref('ValidDay'),'eq','1'):
                    with b.menu(token('Ghi công ',b.money(ref('FeeRate')),'₫ · ',chosen),['✅ Đã ký — ghi công','↩️ Về hồ sơ']):
                        b.case('✅ Đã ký — ghi công');draft(b);put(b,'signedDay',chosen);put(b,'signedMonth',b.text(b.first(b.match(chosen,r'\A[0-9]{4}-[0-9]{2}'))));put(b,'fee',ref('FeeRate'));put(b,'feeReversed','0');commit(b,action='Xác nhận ký nhận đi giao')
                        b.case('↩️ Về hồ sơ');b.go('order')
                    b.otherwise();b.alert('Ngày ký chưa hợp lệ','Dùng YYYY-MM-DD, ngày có thật và không nằm trong tương lai. Chưa ghi công.');b.go('order')

        with b.route('reverse-fee'):
            reason=b.ask('Lý do điều chỉnh công (chỉ dành cho hồ sơ nhập nhầm; giao thất bại vẫn được công)')
            with b.if_(b.match(reason,r'\S')):
                with b.menu('Điều chỉnh công về 0₫?', ['🚫 Xác nhận điều chỉnh','↩️ Về hồ sơ']):
                    b.case('🚫 Xác nhận điều chỉnh');draft(b);put(b,'feeReversed','1');put(b,'feeReason',reason);commit(b,action='Điều chỉnh công có lý do')
                    b.case('↩️ Về hồ sơ');b.go('order')
            with b.if_(b.match(reason,r'\S'),'empty'): b.go('order')

        with b.route('edit'):
            name=b.ask('Tên tiệm',ref('OName'));code=val(b,'invoiceCode')
            address=b.ask('Địa chỉ giao thực tế',val(b,'address'));phone=b.ask('SĐT',val(b,'phone'))
            note=b.ask('Ghi chú / giờ hẹn giao',val(b,'deliveryNote'))
            with b.if_(b.match(name,r'\p{L}')):
                draft(b)
                for k,v in [('name',name),('invoiceCode',code),('address',address),('phone',phone),('deliveryNote',note)]:put(b,k,v)
                b.dictionary({'Name':name,'Money':ref('OTotal'),'ID':val(b,'dataID'),'DC':address,'Number':phone},'EditedData')
                put_object(b,ref('OrdersData'),val(b,'dataID'),ref('EditedData'),'OrdersData');b.set('DataDirty','1')
                commit(b,action='Sửa thông tin')
            with b.if_(b.match(name,r'\p{L}'),'empty'): b.alert('Tên chưa hợp lệ','Chưa sửa hồ sơ.');b.go('order')

        with b.route('contact'):
            with b.menu('Liên hệ',['📞 Quick Call Image','📋 Sao chép tên tiệm','📋 Sao chép số trên phiếu','🗺️ Mở địa chỉ trên Google Maps','↩️ Về hồ sơ']):
                b.case('📞 Quick Call Image');load_invoice(b)
                with b.if_(ref('ImageReady'),'eq','1'): b.add('runworkflow',WFWorkflowName='Quick Call Image',WFWorkflow={'workflowName':'Quick Call Image','isSelf':False},WFInput=ref('InvoiceFile'));b.go('order')
                b.case('📋 Sao chép tên tiệm');b.add('setclipboard',WFInput=ref('OName'),WFLocalOnly=True);b.go('order')
                b.case('📋 Sao chép số trên phiếu');b.add('setclipboard',WFInput=val(b,'phone'),WFLocalOnly=True);b.go('order')
                b.case('🗺️ Mở địa chỉ trên Google Maps')
                with b.if_(val(b,'address')):
                    encoded=b.add('urlencode',WFInput=dyn(val(b,'address')))
                    url=b.add('url',WFURLActionURL=dyn(token('https://www.google.com/maps/search/?api=1&query=',encoded)))
                    b.add('openurl',WFInput=url)
                b.go('order')
                b.case('↩️ Về hồ sơ');b.go('order')

        with b.route('cash'):
            maximum=b.math(ref('OTotal'),'-',ref('OBank'))
            number_input(b,'Tiền mặt',maximum,'CashTarget',maximum)
            draft(b);put(b,'cash',ref('CashTarget'));put(b,'reportSentAt','');commit(b,action='Ghi tổng tiền mặt')

        with b.route('bank'):
            with b.menu(ref('OrderTitle'),['📲 Hiện QR có số tiền','👁️ QR gốc đã lưu','✅ Ghi CK khách báo','⏳ Khách hẹn CK sau','🏦 Xác nhận CK vào công ty','↩️ Về hồ sơ']):
                b.case('📲 Hiện QR có số tiền');b.set('QRAmount',ref('Remaining'));b.set('QRReturn','order');b.go('qr-show')
                b.case('👁️ QR gốc đã lưu');b.set('QRReturn','order');b.go('qr-base')
                b.case('✅ Ghi CK khách báo');number_input(b,'TỔNG tiền khách đã chuyển của đơn; chỉ ghi khi có xác nhận/chứng từ',ref('OBank'),'BankTarget',b.math(ref('OTotal'),'-',ref('OCash')));b.set('CashTarget',ref('OCash'));b.go('receipt-confirm')
                b.case('⏳ Khách hẹn CK sau');b.set('ReportMode','deferred');b.go('report-start')
                b.case('🏦 Xác nhận CK vào công ty')
                with b.menu(token('Sếp đã kiểm tra ',b.money(ref('OBank')),'₫ vào tài khoản công ty?'),['✅ Đã kiểm tra tiền vào','↩️ Về hồ sơ']):
                    b.case('✅ Đã kiểm tra tiền vào');draft(b);put(b,'bankVerified',ref('OBank'));commit(b,action='Đối soát CK vào công ty bằng xác nhận thủ công')
                    b.case('↩️ Về hồ sơ');b.go('order')
                b.case('↩️ Về hồ sơ');b.go('order')

        with b.route('mixed'):
            number_input(b,'TỔNG tiền mặt khách trả của đơn này',ref('OCash'),'CashTarget',b.math(ref('OTotal'),'-',ref('OBank')))
            b.math(ref('OTotal'),'-',ref('CashTarget'),'-',ref('OBank'),var='QRAmount')
            with b.menu(token('Tiền mặt dự kiến ',b.money(ref('CashTarget')),'₫\nCòn cần CK thêm ',b.money(ref('QRAmount')),'₫'),['📲 Hiện QR phần cần chuyển','✅ Ghi tổng tiền thực thu','↩️ Về hồ sơ']):
                b.case('📲 Hiện QR phần cần chuyển');b.set('QRReturn','mixed-receipt');b.go('qr-show')
                b.case('✅ Ghi tổng tiền thực thu');b.go('mixed-receipt')
                b.case('↩️ Về hồ sơ');b.go('order')
        with b.route('mixed-receipt'):
            number_input(b,'TỔNG CK khách đã chuyển của đơn (gồm khoản cũ nếu có)',ref('OBank'),'BankTarget',b.math(ref('OTotal'),'-',ref('CashTarget')))
            b.go('receipt-confirm')
        with b.route('receipt-confirm'):
            with b.menu(token(ref('OName'),'\nTiền mặt ',b.money(ref('CashTarget')),'₫ · CK khách báo ',b.money(ref('BankTarget')),'₫\nCòn ',b.money(b.math(ref('OTotal'),'-',ref('CashTarget'),'-',ref('BankTarget'))),'₫'),['✅ Lưu khoản thu','↩️ Về hồ sơ']):
                b.case('✅ Lưu khoản thu');draft(b);put(b,'cash',ref('CashTarget'));put(b,'bank',ref('BankTarget'))
                with b.if_(ref('BankTarget'),'ne',ref('OBank')): put(b,'bankVerified','0')
                put(b,'reportSentAt','');commit(b,action='Ghi tổng thực thu; độc lập kết quả giao và tiền công')
                b.case('↩️ Về hồ sơ');b.go('order')

        with b.route('delivery'):
            with b.menu(ref('OrderTitle'),['✅ Xác nhận đã giao','⏰ Hẹn giao lại','❌ Giao thất bại','📝 Chuẩn bị báo cáo','♻️ Gửi lại báo cáo gần nhất','↩️ Về hồ sơ']):
                for label,outcome in [('✅ Xác nhận đã giao','delivered'),('⏰ Hẹn giao lại','postponed'),('❌ Giao thất bại','failed')]:
                    b.case(label);draft(b);put(b,'outcome',outcome);put(b,'reportSentAt','')
                    if outcome != 'delivered':
                        put(b,'deliveredAt','');put(b,'deliveryMonth','')
                    if outcome=='delivered':
                        current_time(b)
                        with b.if_(val(b,'deliveredAt'),'empty'): put(b,'deliveredAt',ref('NowISO'));put(b,'deliveryMonth',ref('CurrentMonth'))
                    commit(b,action='Chốt kết quả giao; không thay đổi công ký nhận')
                b.case('📝 Chuẩn bị báo cáo');b.go('report-type')
                b.case('♻️ Gửi lại báo cáo gần nhất');b.go('report-resend')
                b.case('↩️ Về hồ sơ');b.go('order')
        with b.route('report-type'):
            with b.menu('Báo cáo', ['🏦 Khách đã chuyển khoản','⏳ Khách chuyển khoản sau','🤝 Tiền mặt + chuyển khoản','💵 Báo cáo tiền mặt','↩️ Về hồ sơ']):
                for label,mode in [('🏦 Khách đã chuyển khoản','bank'),('⏳ Khách chuyển khoản sau','deferred'),('🤝 Tiền mặt + chuyển khoản','mixed'),('💵 Báo cáo tiền mặt','cash')]: b.case(label);b.set('ReportMode',mode);b.go('report-start')
                b.case('↩️ Về hồ sơ');b.go('order')
        with b.route('report-start'):
            b.set('ReportOK','1')
            with b.if_(ref('ReportMode'),'eq','bank'):
                with b.if_(ref('OBank'),'le',0): b.set('ReportOK','0')
            with b.if_(ref('ReportMode'),'eq','mixed'):
                with b.if_(ref('OBank'),'le',0): b.set('ReportOK','0')
                with b.if_(ref('OCash'),'le',0): b.set('ReportOK','0')
            with b.if_(ref('ReportMode'),'eq','cash'):
                with b.if_(ref('OCash'),'le',0): b.set('ReportOK','0')
            with b.if_(ref('ReportMode'),'eq','deferred'):
                with b.if_(ref('Remaining'),'le',0): b.set('ReportOK','0')
            with b.if_(ref('ReportOK'),'eq','0'): b.alert('Khoản thu chưa khớp loại báo cáo','Ghi đúng tổng tiền mặt/CK thực tế trước khi tạo báo cáo này. Chưa đổi dữ liệu.');b.go('order')
            with b.if_(ref('ReportOK'),'eq','1'):
                load_invoice(b)
                with b.if_(ref('ImageReady'),'eq','1'):
                    b.empty_list('ReportImages');compress(b,ref('InvoiceFile'),'InvoiceShare');b.append('ReportImages',ref('InvoiceShare'))
                    if True:
                        with b.if_(ref('ReportMode'),'ne','cash'):
                            b.set('SignaturePhoto','');pick_proof(b,'Phiếu xuất kho có CHỮ KÝ KHÁCH (khác chữ ký Sếp nhận việc)','SignaturePhoto')
                            with b.if_(ref('SignaturePhoto')):
                                compress(b,b.first(ref('SignaturePhoto')),'SignatureShare');b.append('ReportImages',ref('SignatureShare'))
                        with b.if_(ref('Route'),'eq','report-start'):
                            with b.if_(ref('ReportMode'),'eq','bank'):
                                b.set('TransferPhoto','');pick_proof(b,'Ảnh giao dịch chuyển khoản khách cung cấp','TransferPhoto')
                                with b.if_(ref('TransferPhoto')): compress(b,b.first(ref('TransferPhoto')),'TransferShare');b.append('ReportImages',ref('TransferShare'))
                            with b.if_(ref('ReportMode'),'eq','mixed'):
                                b.set('TransferPhoto','');pick_proof(b,'Ảnh giao dịch chuyển khoản khách cung cấp','TransferPhoto')
                                with b.if_(ref('TransferPhoto')): compress(b,b.first(ref('TransferPhoto')),'TransferShare');b.append('ReportImages',ref('TransferShare'))
                        with b.if_(ref('Route'),'eq','report-start'): b.go('report-confirm')
        with b.route('report-confirm'):
            b.dictionary({'pending':'Chưa giao','delivered':'Đã giao','postponed':'Hẹn giao lại','failed':'Giao thất bại'},'Outcomes')
            b.get(ref('Outcomes'),val(b,'outcome','CurrentRecord','pending'),'OutcomeText')
            b.dictionary({'bank':'Khách đã chuyển khoản; chờ đối soát công ty','mixed':'Tiền mặt + chuyển khoản','deferred':'Khách hẹn chuyển khoản sau','cash':'Khách trả tiền mặt'},'ReportModes')
            b.get(ref('ReportModes'),ref('ReportMode'),'ReportModeText')
            with b.if_(val(b,'outcome'),'empty'):
                with b.if_(val(b,'deliveredAt')): b.set('OutcomeText','Đã giao')
            b.text(token(ref('OName'),' · Phiếu ',ref('OCode'),'\nTổng đơn ',b.money(ref('OTotal')),'₫\nKhách trả tiền mặt ',b.money(ref('OCash')),'₫; chuyển khoản khách báo ',b.money(ref('OBank')),'₫\nCòn chờ ',b.money(ref('Remaining')),'₫\nKết quả giao: ',ref('OutcomeText'),'\nLoại báo cáo: ',ref('ReportModeText')),'ReportText')
            b.set('ReportText',b.add('ask',WFAskActionPrompt=dyn('Nội dung gửi nhóm (có thể sửa)'),WFAskActionDefaultAnswer=dyn(ref('ReportText')),WFInputType='Text',WFAllowsMultilineText=True))
            with b.menu(token('Báo cáo · ',b.count(ref('ReportImages')),' ảnh'),['👁️ Xem ảnh trước','✅ Lưu và mở chia sẻ','↩️ Về hồ sơ']):
                b.case('👁️ Xem ảnh trước');b.add('previewdocument',WFInput=ref('ReportImages'));b.go('report-confirm')
                b.case('✅ Lưu và mở chia sẻ');b.go('report-save')
                b.case('↩️ Về hồ sơ');b.go('order')
        with b.route('report-save'):
            current_time(b);b.empty_list('ReportNames');b.empty_list('ShareImages')
            with b.each(ref('ReportImages'),'ReportImage'):
                name=b.text(token(ref('SelectedID'),'_',ref('ReportStamp'),'_',ref('Repeat Index'),'.jpg'))
                saved=b.save(ref('ReportImage'),ref('ReportsFolder'),name)
                b.append('ShareImages',saved);b.append('ReportNames',name)
            draft(b);b.join(ref('ReportNames'),var='LatestReport')
            put(b,'latestReport',ref('LatestReport'));put(b,'reportHistory',b.text(token(val(b,'reportHistory'),'\n',ref('LatestReport'))))
            put(b,'lastReportType',ref('ReportMode'));put(b,'note',ref('ReportText'));put(b,'reportSentAt','');put(b,'reportPreparedAt',ref('NowISO'))
            b.set('ShareText',ref('ReportText'));commit(b,'share','Chuẩn bị báo cáo; chưa xác nhận gửi')
        with b.route('report-resend'):
            b.empty_list('ShareImages');b.split(val(b,'latestReport'),var='SavedNames')
            with b.each(ref('SavedNames'),'SavedName'):
                with b.if_(b.match(ref('SavedName'),r'\A[a-f0-9]{64}_[0-9_-]+\.jpg\z')):
                    f=b.load(ref('ReportsFolder'),ref('SavedName'))
                    with b.if_(f): b.append('ShareImages',f)
            with b.if_(b.count(ref('ShareImages')),'gt',0): b.set('ShareText',val(b,'note'));b.go('share')
            with b.if_(b.count(ref('ShareImages')),'eq',0): b.alert('Chưa có ảnh báo cáo đọc được','Chọn Chuẩn bị báo cáo để tạo lại.');b.go('order')
        with b.route('share'):
            b.add('setclipboard',WFInput=ref('ShareText'),WFLocalOnly=True);b.add('share',WFInput=ref('ShareImages'))
            with b.menu('Trạng thái báo cáo', ['✅ Đã gửi nhóm','⏸ Chưa gửi / chỉ xem']):
                b.case('✅ Đã gửi nhóm');current_time(b);draft(b);put(b,'reportSentAt',ref('NowISO'));commit(b,action='Sếp xác nhận đã gửi báo cáo')
                b.case('⏸ Chưa gửi / chỉ xem');b.go('order')

        with b.route('qr-show'):
            with b.if_(ref('QRAmount'),'le',0): b.alert('Không còn tiền cần chuyển','Không tạo QR 0₫ hoặc âm. Khoản thu vẫn được giữ nguyên.');b.go(ref('QRReturn'))
            with b.if_(ref('QRAmount'),'gt',0):
                config=b.load(ref('QRFolder'),'config.json')
                with b.if_(config,'empty'): b.set('QRPendingAmount',ref('QRAmount'));b.set('QRSetupReturn','qr-show');b.go('qr-setup')
                with b.if_(config):
                    b.parse(b.text(config),'QRConfig')
                    with b.if_(b.match(val(b,'bin','QRConfig'),r'\A[0-9]{6}\z'),'empty'): b.alert('Cấu hình QR chưa hợp lệ','Thiết lập lại ngân hàng. Không tạo mã chuyển tiền.');b.stop()
                    with b.if_(b.match(val(b,'account','QRConfig'),r'\A[A-Za-z0-9]{1,19}\z'),'empty'): b.alert('Cấu hình QR chưa hợp lệ','Thiết lập lại số tài khoản. Không tạo mã chuyển tiền.');b.stop()
                    b.set('QRMemo',b.replace(b.text(token('THANH TOAN ',ref('OCode'))),r'[^A-Za-z0-9 ]',''))
                    b.set('QRMemo',b.text(b.first(b.match(ref('QRMemo'),r'\A.{1,50}'))))
                    url=qr_url(b,ref('QRAmount'));key=b.hash(b.text(token('qr-binary-v2:',url)))
                    cached=b.load(ref('QRFolder'),b.text(token(key,'.html')))
                    with b.if_(cached,'empty'):
                        decoded=fetch_qr(b,url,'QRDecoded')
                        with b.if_(decoded,'empty'): b.alert('VietQR chưa trả ảnh hợp lệ','Chưa ghi tiền hoặc thay QR đã lưu. Có thể dùng QR gốc trong Tuỳ chỉnh rồi nhập tiền trên app ngân hàng.');b.go('order')
                        with b.if_(decoded):
                            b.save(ref('QRVector'),ref('QRFolder'),b.text(token(key,'.',ref('QRExt'))))
                            b.save(decoded,ref('QRFolder'),b.text(token(key,'.html')),'QRImage')
                        b.otherwise();b.set('QRImage',cached)
                    with b.if_(ref('Route'),'eq','qr-show'):
                        b.alert('QR chuyển khoản',token('Số tiền ',b.money(ref('QRAmount')),'₫\n',val(b,'name','QRConfig'),' · ',val(b,'bank','QRConfig'),'\nSTK ',val(b,'account','QRConfig'),''))
                        preview=b.add('setitemname',WFInput=ref('QRImage'),WFName=dyn(token('QR ',b.money(ref('QRAmount')),' VND.html')),WFDontIncludeFileExtension=False)
                        b.add('previewdocument',WFInput=preview);b.go(ref('QRReturn'))
        with b.route('qr-setup'):
            name=b.ask('Tên chủ tài khoản')
            with b.if_(b.match(name,r'\p{L}'),'empty'): b.alert('Tên chủ tài khoản chưa hợp lệ','Chưa thay QR cũ.');b.stop()
            account=b.ask('Số tài khoản')
            bankquery=b.ask('Ngân hàng')
            b.get(ref('SharedUI'),'banks','Banks')
            b.empty_list('BankRows');query=b.fold(bankquery)
            with b.each(b.keys(ref('Banks')),'BankLabel'):
                label=b.fold(ref('BankLabel'))
                with b.if_(label,'contains',query): b.append('BankRows',ref('BankLabel'))
            with b.if_(b.count(ref('BankRows')),'eq',0): b.alert('Chưa tìm thấy ngân hàng','Nhập tên ngắn như Vietcombank, ACB hoặc MB. Chưa thay QR cũ.');b.go('options')
            with b.if_(b.count(ref('BankRows')),'gt',0):
                selected=b.choose(ref('BankRows'),'Ngân hàng');bankbin=b.get(ref('Banks'),selected)
                with b.if_(b.match(account,r'\A[A-Za-z0-9]{1,19}\z')):
                    with b.menu(token(name,'\nSTK ',account,'\n',selected),['✅ Tạo và lưu QR','↩️ Huỷ thiết lập']):
                        b.case('✅ Tạo và lưu QR')
                        b.dictionary({'schema':'sen-qr-v1','name':name,'account':account,'bank':selected,'bin':bankbin},'QRConfig')
                        b.set('QRMemo','');url=qr_url(b,'')
                        images=fetch_qr(b,url,'QRSetupImages')
                        with b.if_(images):
                            key=b.hash(b.text(ref('QRConfig')))
                            b.save(ref('QRVector'),ref('QRFolder'),b.text(token('base_',key,'.',ref('QRExt'))))
                            basefile=b.text(token('base_',key,'.html'));b.save(images,ref('QRFolder'),basefile)
                            b.put(ref('QRConfig'),'baseFile',basefile,'QRConfig')
                            b.save(b.text(ref('QRConfig')),ref('QRFolder'),'config.pending.json')
                            stored=b.load(ref('QRFolder'),'config.pending.json')
                            with b.if_(b.hash(b.text(stored)),'eq',b.hash(b.text(ref('QRConfig')))):
                                b.save(b.text(ref('QRConfig')),ref('QRFolder'),'config.json')
                                b.alert('Đã lưu QR','')
                                b.go(ref('QRSetupReturn'))
                            with b.if_(b.hash(b.text(stored)),'ne',b.hash(b.text(ref('QRConfig')))): b.alert('Chưa lưu được cấu hình QR','QR cũ được giữ. Kiểm tra iCloud rồi thử lại.');b.go('options')
                        with b.if_(images,'empty'): b.alert('Chưa nhận được ảnh QR','Thử lại khi có mạng.');b.go('options')
                        b.case('↩️ Huỷ thiết lập');b.go('options')
                    b.otherwise();b.alert('Số tài khoản chưa hợp lệ','Chỉ chữ/số, tối đa 19 ký tự; không xoá số 0 ở đầu. Chưa thay QR cũ.');b.go('options')
        with b.route('qr-settings'):
            existing_config=b.load(ref('QRFolder'),'config.json')
            with b.if_(existing_config,'empty'):
                b.set('QRSetupReturn','options');b.go('qr-setup')
            with b.if_(existing_config):
                with b.menu('QR nhận tiền',['⚙️ Thiết lập / đổi tài khoản','👁️ Xem QR gốc đã lưu','↩️ Tuỳ chỉnh']):
                    b.case('⚙️ Thiết lập / đổi tài khoản');b.set('QRSetupReturn','options');b.go('qr-setup')
                    b.case('👁️ Xem QR gốc đã lưu');b.set('QRReturn','options');b.go('qr-base')
                    b.case('↩️ Tuỳ chỉnh');b.go('options')

        with b.route('qr-base'):
            config=b.load(ref('QRFolder'),'config.json')
            with b.if_(config):
                b.parse(b.text(config),'QRConfig')
                filename=val(b,'baseFile','QRConfig')
                with b.if_(b.match(filename,r'\Abase_[a-f0-9]{64}\.html\z')):
                    base=b.load(ref('QRFolder'),filename)
                    with b.if_(base): b.add('previewdocument',WFInput=base)
                    with b.if_(base,'empty'): b.alert('QR gốc chưa có dữ liệu','Tải QR về trong Tệp hoặc thiết lập lại khi có mạng.')
                with b.if_(b.match(filename,r'\Abase_[a-f0-9]{64}\.html\z'),'empty'): b.alert('Tên QR gốc không hợp lệ','Thiết lập lại QR. Không đọc đường dẫn ngoài thư mục QR.')
            with b.if_(config,'empty'): b.alert('Chưa thiết lập QR','Vào Tuỳ chỉnh → Thiết lập QR trước.')
            b.go(ref('QRReturn'))

        with b.route('options'):
            with b.menu(OPTIONS,['🔎 Tìm / lọc đơn','🔢 Giới hạn hiển thị','🏦 Thiết lập QR','📊 Công đơn & đối soát','🛠️ Dữ liệu / công cụ','↩️ Danh sách đầy đủ','Đóng']):
                b.case('🔎 Tìm / lọc đơn');b.go('filter')
                b.case('🔢 Giới hạn hiển thị');number_input(b,'Số dòng muốn xem: 1–500; 0 = toàn bộ (nhiều đơn sẽ chậm)',ref('DisplayLimit'),'DisplayLimit','500');b.put(ref('Ledger'),'_displayLimit',ref('DisplayLimit'),'Ledger');save_to(b,'main')
                b.case('🏦 Thiết lập QR');b.go('qr-settings')
                b.case('📊 Công đơn & đối soát');b.go('stats')
                b.case('🛠️ Dữ liệu / công cụ');b.go('tools')
                b.case('↩️ Danh sách đầy đủ');b.set('Scope','active');b.set('Search','');b.go('main')
                b.case('Đóng');b.stop()
        with b.route('filter'):
            with b.menu('Chọn nhóm đơn',['🔎 Tìm tên / mã / điện thoại','✅ Đã giao','💵 Có thu tiền mặt','🏦 Có CK khách báo','🤝 Thu kết hợp','🚚 Chưa giao','💰 Còn tiền phải thu','✍️ Chưa xác nhận ký','📝 Chưa báo đã gửi','♻️ Đơn đã cất',BACK]):
                b.case('🔎 Tìm tên / mã / điện thoại');b.fold(b.ask('Nhập từ khoá'),'Search');b.set('Scope','active');b.go('main')
                for label,scope in [('✅ Đã giao','delivered'),('💵 Có thu tiền mặt','cash'),('🏦 Có CK khách báo','bank'),('🤝 Thu kết hợp','mixed'),('🚚 Chưa giao','pending'),('💰 Còn tiền phải thu','debt'),('✍️ Chưa xác nhận ký','unsigned'),('📝 Chưa báo đã gửi','unreported'),('♻️ Đơn đã cất','trash')]: b.case(label);b.set('Scope',scope);b.set('Search','');b.go('main')
                b.case(BACK);b.go('main')
        with b.route('stats'):
            b.set('FeeCount','0');b.set('FeeTotal','0');b.set('UnknownCount','0');b.set('TotalCash','0');b.set('WaitingBank','0');b.empty_list('CSVRows')
            b.append('CSVRows',b.text('"Mã phiếu","Tên khách","Ngày ký","Công VND","Tiền mặt hiện tại","CK khách báo hiện tại"'))
            with b.each(b.keys(ref('Ledger')),'StatID'):
                with b.if_(b.match(ref('StatID'),ID)):
                    b.parse(b.get(ref('Ledger'),ref('StatID')),'StatRecord')
                    cash=val(b,'cash','StatRecord','0');bank=val(b,'bank','StatRecord','0')
                    b.math(ref('TotalCash'),'+',cash,var='TotalCash')
                    b.math(ref('WaitingBank'),'+',bank,'-',val(b,'bankVerified','StatRecord','0'),var='WaitingBank')
                    with b.if_(val(b,'signedDay','StatRecord'),'empty'): b.math(ref('UnknownCount'),'+1',var='UnknownCount')
                    with b.if_(val(b,'signedMonth','StatRecord'),'eq',ref('StatsMonth')):
                        with b.if_(val(b,'feeReversed','StatRecord','0'),'ne','1'):
                            with b.if_(val(b,'signedDay','StatRecord')):
                                b.math(ref('FeeCount'),'+1',var='FeeCount');b.math(ref('FeeTotal'),'+',val(b,'fee','StatRecord','0'),var='FeeTotal')
                                safe=[]
                                for k in ['invoiceCode','name','signedDay']:
                                    cell=b.replace(val(b,k,'StatRecord'),r'"','""',regex=False)
                                    cell=b.replace(cell,r'^([\s]*[=+@-])',"'$1")
                                    safe.append(b.text(token('"',cell,'"')))
                                b.append('CSVRows',b.text(token(safe[0],',',safe[1],',',safe[2],',',val(b,'fee','StatRecord','0'),',',cash,',',bank)))
            b.math(ref('TotalCash'),'-',ref('CashHanded'),var='CashHeld')
            with b.menu(token('Công tháng ',ref('StatsMonth'),': ',ref('FeeCount'),' đơn · ',b.money(ref('FeeTotal')),'₫'),['🗓️ Đổi tháng','💰 Số tiền đang giữ','📋 Đối chiếu số đơn kế toán','💾 Lưu tổng kết JSON','💾 Xuất CSV công tháng','💵 Ghi nộp tiền mặt','⚙️ Mức công cho đơn mới',BACK]):
                b.case('🗓️ Đổi tháng');month=b.ask('Tháng công YYYY-MM',ref('StatsMonth'))
                with b.if_(b.match(month,MONTH)): b.set('StatsMonth',month)
                b.go('stats')
                b.case('💰 Số tiền đang giữ');b.alert('Số tiền',token('Tiền mặt ',b.money(ref('CashHeld')),'₫\nCK chờ đối soát ',b.money(ref('WaitingBank')),'₫\nChưa tính công: ',ref('UnknownCount'),' hồ sơ'));b.go('stats')
                b.case('📋 Đối chiếu số đơn kế toán');n=number_input(b,'Số đơn kế toán tính trong tháng',ref('FeeCount'),'AccountantCount')
                b.alert('Đối chiếu công đơn',token('Sổ có ',ref('FeeCount'),' đơn; kế toán tính ',n,'\nChênh lệch (sổ − kế toán): ',b.math(ref('FeeCount'),'-',n),' đơn.\nChưa bao gồm hồ sơ chưa xác nhận ngày ký.'));b.go('stats')
                b.case('💾 Lưu tổng kết JSON');current_time(b)
                b.dictionary({'schema':'sen-delivery-summary-v4','month':ref('StatsMonth'),'signedOrderCount':ref('FeeCount'),'signedFeeTotal':ref('FeeTotal'),
                    'unsignedRecordsAllTime':ref('UnknownCount'),'cashCollectedAllTime':ref('TotalCash'),'cashHandedAllTime':ref('CashHanded'),
                    'cashHeldAllTime':ref('CashHeld'),'bankAwaitingVerificationAllTime':ref('WaitingBank'),'createdAt':ref('NowISO')},'MonthlySummary')
                report=b.save(b.text(ref('MonthlySummary')),ref('MonthlyFolder'),b.text(token(ref('StatsMonth'),'_tong_ket_',ref('ReportStamp'),'.json')))
                b.add('share',WFInput=report);b.go('stats')
                b.case('💾 Xuất CSV công tháng');current_time(b);csv=b.join(ref('CSVRows'))
                file=b.save(csv,ref('MonthlyFolder'),b.text(token(ref('StatsMonth'),'_cong_',ref('ReportStamp'),'.csv')));b.add('share',WFInput=file);b.go('stats')
                b.case('💵 Ghi nộp tiền mặt');n=number_input(b,'Số tiền mặt nộp công ty lần này (không trừ công đơn)','0','Handover',ref('CashHeld'))
                with b.menu(token('Xác nhận đã nộp ',b.money(n),'₫?'),['✅ Đã nộp tiền','↩️ Quay lại']):
                    b.case('✅ Đã nộp tiền');b.math(ref('CashHanded'),'+',n,var='CashHanded');b.put(ref('Ledger'),'_cashHanded',ref('CashHanded'),'Ledger');current_time(b)
                    history=b.get(ref('Ledger'),'_handoverHistory');b.put(ref('Ledger'),'_handoverHistory',b.text(token(history,'\n',ref('NowISO'),'|',n)),'Ledger');save_to(b,'stats')
                    b.case('↩️ Quay lại');b.go('stats')
                b.case('⚙️ Mức công cho đơn mới');number_input(b,'Mức công chỉ áp dụng hồ sơ xác nhận ký TỪ LÚC ĐỔI',ref('FeeRate'),'FeeRate');b.put(ref('Ledger'),'_feeRate',ref('FeeRate'),'Ledger');save_to(b,'stats')
                b.case(BACK);b.go('main')

        with b.route('tools'):
            with b.menu('Dữ liệu / công cụ',['🔄 Đọc gói Bill mới','🔄 Đọc lại tên ảnh trong kho','🛟 Xuất sổ sao lưu','📂 Nạp/khôi phục ảnh cũ','📄 Xem lịch sử hồ sơ đang chọn','🗑️ Xoá ảnh đơn đã cất','🔄 Cập nhật giao diện','↩️ Tuỳ chỉnh']):
                b.case('🔄 Đọc gói Bill mới');b.go('sync41')
                b.case('🔄 Đọc lại tên ảnh trong kho');b.put(ref('Ledger'),'_legacyFilenamesV411','','Ledger');b.put(ref('Ledger'),'_legacyIndexDone','','Ledger');b.go('sync')
                b.case('🔄 Cập nhật giao diện');load_ui(b,force=True);b.alert('Đã cập nhật','');b.stop()
                b.case('🛟 Xuất sổ sao lưu');current_time(b);file=b.save(b.text(ref('Ledger')),ref('MonthlyFolder'),b.text(token('orders_backup_',ref('ReportStamp'),'.json')));b.add('share',WFInput=file);b.go('options')
                b.case('📂 Nạp/khôi phục ảnh cũ');b.go('legacy')
                b.case('📄 Xem lịch sử hồ sơ đang chọn')
                with b.if_(b.match(ref('SelectedID'),ID)):
                    b.parse(b.get(ref('Ledger'),ref('SelectedID')),'HistoryRecord');b.alert('Lịch sử hồ sơ',val(b,'events','HistoryRecord','Chưa có lịch sử v4.'))
                b.go('options')
                b.case('🗑️ Xoá ảnh đơn đã cất');b.go('destroy')
                b.case('↩️ Tuỳ chỉnh');b.go('options')
        with b.route('legacy'):
            b.alert('Nạp ảnh cũ có chủ đích','Chọn đúng một ảnh cũ. Tên và tiền lấy từ tên tệp; không quét cả thư mục. Nếu trùng tên tệp/ID thì chỉ mở hồ sơ đã có.')
            f=b.add('documentpicker.open',WFAskWhereToGetFile=True,WFSelectMultiple=False)
            filename=b.add('getitemname',WFInput=f);b.set('LegacyFilename',filename)
            with b.if_(b.match(ref('LegacyFilename'),'(?i)'+FILENAME),'empty'):
                ext=b.add('properties.files',WFInput=f,WFContentItemPropertyName='File Extension')
                with b.if_(ext): b.text(token(ref('LegacyFilename'),'.',ext),'LegacyFilename')
            filename=ref('LegacyFilename')
            b.hash(filename,'LegacyID')
            keymatch=b.match(filename,r'·\s*([0-9]{14,24}-[0-9]{6})\.png\z')
            with b.if_(keymatch):
                key=b.add('text.match.getgroup',matches=b.first(keymatch),WFGetGroupType='Group At Index',WFGroupIndex=1)
                b.hash(b.text(token('sen-bill-v1:',key)),'LegacyID')
            images=b.add('filter.images',WFContentItemInputParameter=f,WFContentItemLimitEnabled=False)
            with b.if_(b.count(images),'eq',0): b.alert('Không phải ảnh đọc được','Chưa thay sổ. Chọn PNG/JPEG/HEIC có dữ liệu.');b.stop()
            with b.if_(b.get(ref('Ledger'),ref('LegacyID'))):
                existing=b.load(ref('ImagesFolder'),filename)
                with b.if_(existing,'empty'): b.save(f,ref('ImagesFolder'),filename,overwrite=False)
                b.set('SelectedID',ref('LegacyID'));b.go('order')
            with b.if_(b.get(ref('Ledger'),ref('LegacyID')),'empty'):
                b.set('LegacyParsedName','');b.set('LegacyParsedTotal','0')
                from legacy_catalog import NAME_PATTERN
                base=b.replace(filename,r'(?i)\.(?:png|jpe?g|heic|heif|webp)\z','')
                parts=b.match(base,NAME_PATTERN)
                with b.if_(parts):
                    b.set('LegacyParsedName',b.add('text.match.getgroup',matches=b.first(parts),WFGetGroupType='Group At Index',WFGroupIndex=1))
                    raw=b.add('text.match.getgroup',matches=b.first(parts),WFGetGroupType='Group At Index',WFGroupIndex=2)
                    parsed=b.replace(raw,r'[^0-9]','')
                    with b.if_(b.match(parsed,MONEY)):b.set('LegacyParsedTotal',parsed)
                name=b.ask('Kiểm tra tên tiệm lấy từ tên tệp',ref('LegacyParsedName'))
                with b.if_(b.match(name,r'\p{L}'),'empty'):b.alert('Tên tiệm chưa hợp lệ','Chưa thêm hồ sơ.');b.stop()
                total=number_input(b,'Kiểm tra tổng tiền nguyên VND lấy từ tên tệp',ref('LegacyParsedTotal'),'LegacyTotal')
                with b.if_(b.match(filename,'(?i)'+FILENAME)):
                    existing=b.load(ref('ImagesFolder'),filename)
                    with b.if_(existing,'empty'): b.save(f,ref('ImagesFolder'),filename,overwrite=False)
                    b.dictionary({'id':ref('LegacyID'),'filename':filename,'name':name,'total':total,'cash':'0','bank':'0','createdAt':ref('NowISO'),'createdMonth':ref('CurrentMonth'),'deleted':'0','cancelled':'0','destroyed':'0','signedDay':'','fee':'0'},'NewRecord')
                    b.put(ref('Ledger'),ref('LegacyID'),b.text(ref('NewRecord')),'Ledger');b.put(ref('Ledger'),'_sourceMigrated','','Ledger');b.set('SelectedID',ref('LegacyID'));save_to(b,'sync41')
                with b.if_(b.match(filename,'(?i)'+FILENAME),'empty'): b.alert('Tên tệp ảnh chưa phù hợp','Dùng PNG/JPEG/HEIC, tên không chứa đường dẫn. Chưa lưu.');b.go('options')
        with b.route('destroy'):
            b.alert('Chọn đơn cần xoá ảnh','Vào danh sách Đơn đã cất, mở hồ sơ cần xoá, rồi quay lại công cụ này. Giữ tên tệp và số liệu tối thiểu để không mất công/khoản thu.')
            with b.if_(b.match(ref('SelectedID'),ID),'empty'): b.go('options')
            with b.if_(b.match(ref('SelectedID'),ID)):
                b.parse(b.get(ref('Ledger'),ref('SelectedID')),'CurrentRecord')
                with b.if_(val(b,'deleted','CurrentRecord','0'),'ne','1'): b.alert('Đơn chưa được cất','Cất đơn trước để tránh xoá nhầm ảnh đang dùng.');b.go('order')
                with b.if_(val(b,'deleted','CurrentRecord','0'),'eq','1'):
                    with b.menu(token('Xoá ảnh vĩnh viễn · ',val(b,'name'),'?'),['🗑️ Xác nhận xoá ảnh','↩️ Huỷ']):
                        b.case('🗑️ Xác nhận xoá ảnh')
                        filename=val(b,'filename')
                        with b.if_(b.match(filename,'(?i)'+FILENAME)):
                            image=b.load(ref('ImagesFolder'),filename)
                            with b.if_(image): b.add('file.delete',WFInput=image,WFDeleteFileConfirmDeletion=True)
                        names=b.split(val(b,'reportHistory'))
                        with b.each(names,'DeleteName'):
                            with b.if_(b.match(ref('DeleteName'),r'\A[a-f0-9]{64}_[0-9_-]+\.jpg\z')):
                                f=b.load(ref('ReportsFolder'),ref('DeleteName'))
                                with b.if_(f): b.add('file.delete',WFInput=f,WFDeleteFileConfirmDeletion=True)
                        draft(b);put(b,'destroyed','1');put(b,'name','[Đã xoá ảnh]');put(b,'phone','');put(b,'address','')
                        b.dictionary({'Name':'[Đã xoá ảnh]','Money':ref('OTotal'),'ID':val(b,'dataID'),'DC':'','Number':''},'RedactedData')
                        put_object(b,ref('OrdersData'),val(b,'dataID'),ref('RedactedData'),'OrdersData');b.set('DataDirty','1')
                        commit(b,'main','Người dùng xoá ảnh; giữ công và khoản thu')
                        b.case('↩️ Huỷ');b.go('options')

        with b.route('save'):
            # A second instance must not silently overwrite a more recent ledger.
            fresh=b.load(ref('AppFolder'),'orders.json');b.set('FreshHash','missing')
            with b.if_(fresh): b.hash(b.text(fresh),'FreshHash')
            with b.if_(ref('FreshHash'),'ne',ref('DiskHash')):
                b.alert('Sổ đã thay đổi ở phiên khác','Chưa ghi đè. Sếp đóng phiên này rồi chạy lại sau khi iCloud đồng bộ.');b.stop()
            with b.if_(ref('DataDirty'),'eq','1'):save_data(b)
            b.put(ref('Ledger'),'_sharedDataHash',ref('DataDiskHash'),'Ledger')
            b.put(ref('Ledger'),'_sourceMap',b.text(ref('SourceMap')),'Ledger')
            b.set('AllCash','0');b.set('LedgerOK','1')
            with b.each(b.keys(ref('Ledger')),'ValidateID'):
                with b.if_(b.match(ref('ValidateID'),ID)):
                    b.parse(b.get(ref('Ledger'),ref('ValidateID')),'ValidateRecord')
                    for k in ['total','cash','bank']:
                        value=val(b,k,'ValidateRecord','0')
                        with b.if_(b.match(value,MONEY),'empty'): b.set('LedgerOK','0')
                    total=val(b,'total','ValidateRecord','0');cash=val(b,'cash','ValidateRecord','0');bank=val(b,'bank','ValidateRecord','0')
                    with b.if_(b.math(cash,'+',bank),'gt',total): b.set('LedgerOK','0')
                    b.math(ref('AllCash'),'+',cash,var='AllCash')
            with b.if_(ref('CashHanded'),'gt',ref('AllCash')): b.set('LedgerOK','0')
            with b.if_(ref('LedgerOK'),'eq','0'):
                b.alert('Khoản thu cần kiểm tra','Chưa ghi đè sổ. Tổng tiền mặt + CK không được vượt tổng đơn; tiền đã nộp không vượt tiền đã thu.');b.stop()
            b.put(ref('Ledger'),'_schema','sen-orders-v3','Ledger');b.put(ref('Ledger'),'_version',VERSION,'Ledger')
            b.text(ref('Ledger'),'SaveJSON');b.save(ref('SaveJSON'),ref('AppFolder'),'orders.pending.json')
            check=b.load(ref('AppFolder'),'orders.pending.json');expected=b.hash(ref('SaveJSON'))
            with b.if_(b.hash(b.text(check)),'ne',expected): b.alert('Chưa xác minh được bản chờ','Sổ chính chưa bị thay đổi. Kiểm tra iCloud rồi chạy lại.');b.stop()
            with b.if_(fresh): b.save(b.text(fresh),ref('AppFolder'),'orders.backup.json')
            b.save(ref('SaveJSON'),ref('AppFolder'),'orders.json');final=b.load(ref('AppFolder'),'orders.json')
            with b.if_(b.hash(b.text(final)),'ne',expected): b.alert('Chưa xác minh được sổ đã lưu','Bản chờ và bản sao lưu được giữ. Chưa báo hoàn tất.');b.stop()
            b.set('DiskHash',expected);b.set('Dirty','0');b.go(ref('SaveReturn'))
    b.alert('Đã kết thúc phiên','Chạy lại phím tắt để tiếp tục.');b.stop()
    workflow={'WFWorkflowActions':b.actions,'WFWorkflowClientVersion':'3612.0.1.3','WFWorkflowMinimumClientVersion':1106,'WFWorkflowMinimumClientVersionString':'1106',
        'WFWorkflowIcon':{'WFWorkflowIconStartColor':4251333119,'WFWorkflowIconGlyphNumber':59861},'WFWorkflowName':'Phiếu Giao Hàng',
        'WFWorkflowInputContentItemClasses':[],'WFWorkflowOutputContentItemClasses':[],'WFWorkflowTypes':[],'WFQuickActionSurfaces':[],
        'WFWorkflowHasShortcutInputVariables':False,'WFWorkflowHasOutputFallback':False,'WFWorkflowImportQuestions':[]}
    from shared import externalize
    workflow=externalize(workflow)
    BUILD.mkdir(parents=True,exist_ok=True)
    (BUILD/f'Phieu-Giao-Hang-v{VERSION}-unsigned.shortcut').write_bytes(plistlib.dumps(workflow,fmt=plistlib.FMT_BINARY,sort_keys=False))
    (BUILD/'workflow.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2))
    return workflow

if __name__=='__main__': print('Built',len(build()['WFWorkflowActions']),'native actions')
