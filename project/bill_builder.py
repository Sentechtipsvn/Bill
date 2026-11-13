"""Bill 3.4: preserved OCR, five-field shared JSON and non-overwriting photo IDs."""
import copy,json,plistlib
from pathlib import Path
from shortcut_builder import Builder,BUILD,ref,token,uid,output,current_time
from shared import CODE,MONEY,DATA_NAME,field,put_object,read_data,save_data,random_id,externalize
VERSION='3.4.0'
CODE_PATTERN=CODE
SAVE='💾 Lưu đơn'
EDIT_NAME='✏️ Sửa tên khách'
EDIT_TOTAL='✏️ Sửa số tiền'
EDIT_CODE='🧾 Sửa mã phiếu'
EDIT_ADDRESS='📍 Sửa địa chỉ'
EDIT_PHONE='☎️ Sửa điện thoại'
HEADER_PATTERNS = {
    "BillCode": r'(?im)(?:^|[ \t])[Ss][ốoô]\p{M}*\s*[:：]\s*([^\s]+)',
    "BillAddress": r'(?im)(?:^|[ \t])[ĐđDd][ịi]\p{M}*a[ \t]+ch[ỉi]\p{M}*[ \t]*[:：][ \t]*([^\r\n]+)',
    "BillPhone": r'(?im)(?:^|[ \t])(?:[Ss][ĐđDd][Tt]|[ĐđDd]i[ệeê]\p{M}*n[ \t]+tho[ạa]\p{M}*i)[ \t]*[:：][ \t]*([+0-9][0-9 .()+-]{8,22})',
    "BillDeliveryNote": r'(?im)(?:^|[ \t])[ĐđDd][ịi]\p{M}*a[ \t]+ch[ỉi]\p{M}*[ \t]+giao[ \t]+h[àa]\p{M}*ng[ \t]*[:：][ \t]*([^\r\n]+)'
}

def header_fields(b):
    # Proven OCR action UUID from the supplied Bill 3.2.0 (248-action graph).
    raw = output("2DB7BBEA-3304-4EBA-90CA-00EC058ECB2E", "Văn bản sạch")
    for key, pattern in HEADER_PATTERNS.items():
        b.set(key, "")
        matches = b.match(raw, pattern)
        with b.if_(b.count(matches), "gt", 0):
            selected = b.first(matches)
            value = b.replace(selected, r'^[^:：]*[:：][ \t]*', "")
            # Stop at adjacent labels when OCR flattens the two header columns.
            value = b.replace(value, r'(?i)[ \t]+(?:NV[ \t]+b[áa]\p{M}*n[ \t]+h[àa]\p{M}*ng|[ĐđDd]i[ệeê]\p{M}*n[ \t]+tho[ạa]\p{M}*i|[ĐđDd][ịi]\p{M}*a[ \t]+ch[ỉi]\p{M}*)[ \t]*[:：].*$', "")
            value = b.replace(value, r'^\s+|\s+$', "")
            if key == "BillCode":
                value = b.first(b.split(value, " "))
                with b.if_(b.match(value, CODE_PATTERN)):
                    b.set(key, value)
            elif key == "BillPhone":
                value = b.replace(value, r'[^+0-9]', "")
                with b.if_(b.match(value, r'\A(?:0[0-9]{9,10}|\+84[0-9]{9,10})\z')):
                    b.set(key, value)
            else:
                b.set(key, value)

def read_name(b, default=""):
    entered = b.ask("Tên tiệm", default, var="EnteredName")
    entered = b.replace(entered, r'\s+', " ")
    b.replace(entered, r'^\s+|\s+$', "", "EnteredName")
    with b.if_(b.match(ref("EnteredName"), r'\p{L}')):
        b.set("BillName", ref("EnteredName"))
        b.otherwise()
        b.alert("Tên khách chưa hợp lệ", "Tên cần có chữ cái. Chưa có tệp nào được lưu.")

def read_total(b, default=""):
    entered = b.ask("Tổng tiền", default, "Number")
    with b.if_(b.match(entered, r'\A[0-9]+\z')):
        b.replace(entered, r'^0+(?=[0-9])', "", "BillTotal")
        b.otherwise()
        b.alert("Số tiền chưa hợp lệ", "Nhập số nguyên không âm, không có dấu phân cách. Chưa có tệp nào được lưu.")

def build_bill():
 b=Builder();b.actions=copy.deepcopy(json.loads(Path(__file__).with_name('bill_ocr_actions.json').read_text()))
 for i,a in enumerate(b.actions):a['WFWorkflowActionParameters'].setdefault('UUID',uid(f'bill-ocr:{i}'))
 b.actions[0]['WFWorkflowActionParameters']['WFCommentActionText']='Bill 3.4.0 · © Sentechtipsvn'
 header_fields(b);b.set('BillName','');b.set('BillTotal','')
 with b.if_(ref('Đã có tên khách'),'eq','1'):b.set('BillName',ref('Tên khách đã chọn'))
 with b.if_(ref('Đã có tiền tổng'),'eq','1'):b.set('BillTotal',ref('Tiền tổng đã chọn'))
 with b.repeat(3):
  with b.if_(ref('BillName'),'empty'):read_name(b)
  with b.if_(ref('BillTotal'),'empty'):read_total(b)
 with b.if_(ref('BillName'),'empty'):b.alert('Thiếu tên tiệm','Chưa lưu đơn.');b.stop()
 with b.if_(ref('BillTotal'),'empty'):b.alert('Thiếu số tiền','Chưa lưu đơn.');b.stop()
 with b.if_(b.match(ref('BillCode'),CODE),'empty'):
  b.set('BillCode',b.text(b.add('number.random',WFRandomNumberMinimum=1000,WFRandomNumberMaximum=9999)))
 with b.repeat(20):
  with b.menu(token('Bill · ',ref('BillName'),' — ',b.money(ref('BillTotal')),'₫'),[SAVE,EDIT_NAME,EDIT_TOTAL,EDIT_CODE,EDIT_ADDRESS,EDIT_PHONE,'👁️ Xem ảnh','Huỷ']):
   b.case(SAVE);current_time(b);read_data(b,require_migration=True)
   b.set('BillPNG',b.add('image.convert',WFInput=ref('Hình ảnh'),WFImageFormat='PNG',WFImagePreserveMetadata=False))
   b.set('BillID',ref('BillCode'));existing=b.get(ref('OrdersData'),ref('BillID'));b.set('IsDuplicate','0')
   with b.if_(existing):
    b.load(ref('ImagesFolder'),b.text(token(ref('BillID'),'.png')),'PreviousImage')
    with b.if_(ref('PreviousImage'),'empty'):
     previous_ledger=b.load(ref('AppFolder'),'orders.json')
     with b.if_(previous_ledger):
      b.parse(previous_ledger,'PreviousLedger');b.dictionary(var='PreviousSourceMap')
      mapping=b.get(ref('PreviousLedger'),'_sourceMap')
      with b.if_(mapping):b.parse(mapping,'PreviousSourceMap')
      b.get(ref('PreviousSourceMap'),ref('BillID'),'PreviousLink')
      with b.if_(ref('PreviousLink'),'empty'):b.get(ref('PreviousLedger'),b.text(token('_source_',ref('BillID'))),'PreviousLink')
      link=ref('PreviousLink')
      with b.if_(link):
       b.parse(b.get(ref('PreviousLedger'),link),'PreviousFinance')
       old_name=field('PreviousFinance','filename')
       with b.if_(b.match(old_name,r'(?i)\A[^/\\\x00-\x1f]{1,240}\.(?:png|jpg|jpeg|heic|heif|webp)\z')):b.load(ref('ImagesFolder'),old_name,'PreviousImage')
    with b.if_(ref('PreviousImage')):
     with b.if_(b.hash(ref('BillPNG')),'eq',b.hash(ref('PreviousImage'))):b.set('IsDuplicate','1')
    with b.if_(ref('IsDuplicate'),'eq','0'):random_id(b,ref('OrdersData'),'BillID')
   filename=b.text(token(ref('BillID'),'.png'))
   present=b.load(ref('ImagesFolder'),filename)
   with b.if_(present):
    with b.if_(ref('IsDuplicate'),'eq','0'):random_id(b,ref('OrdersData'),'BillID')
   # Check orphan/collision paths even after choosing another metadata ID.
   b.set('PhotoReady','0')
   with b.repeat(8):
    with b.if_(ref('PhotoReady'),'eq','0'):
     filename=b.text(token(ref('BillID'),'.png'));present=b.load(ref('ImagesFolder'),filename)
     with b.if_(present,'empty'):b.set('PhotoReady','1')
     with b.if_(present):
      with b.if_(ref('IsDuplicate'),'eq','1'):b.set('PhotoReady','1')
      with b.if_(ref('IsDuplicate'),'eq','0'):random_id(b,ref('OrdersData'),'BillID')
   with b.if_(ref('PhotoReady'),'eq','0'):b.alert('Chưa cấp được ID','Không ghi đè ảnh cũ.');b.stop()
   b.text(token(ref('BillID'),'.png'),'BillFilename')
   existing_photo=b.load(ref('ImagesFolder'),ref('BillFilename'))
   with b.if_(existing_photo,'empty'):
    b.save(ref('BillPNG'),ref('ImagesFolder'),ref('BillFilename'),overwrite=False)
   with b.if_(ref('IsDuplicate'),'eq','0'):
    b.dictionary({'Name':ref('BillName'),'Money':ref('BillTotal'),'ID':ref('BillID'),'DC':ref('BillAddress'),'Number':ref('BillPhone')},'BillRecord')
    put_object(b,ref('OrdersData'),ref('BillID'),ref('BillRecord'),'OrdersData');save_data(b)
   b.alert('Đã lưu đơn',token(ref('BillName'),' — ',b.money(ref('BillTotal')),'₫'));b.stop()
   b.case(EDIT_NAME);read_name(b,ref('BillName'))
   b.case(EDIT_TOTAL);read_total(b,ref('BillTotal'))
   b.case(EDIT_CODE);entered=b.ask('Mã phiếu',ref('BillCode'))
   with b.if_(b.match(entered,CODE)):b.set('BillCode',entered)
   for label,key,prompt in [(EDIT_ADDRESS,'BillAddress','Địa chỉ'),(EDIT_PHONE,'BillPhone','SĐT')]:
    b.case(label);b.ask(prompt,ref(key),var=key)
   b.case('👁️ Xem ảnh');b.add('previewdocument',WFInput=ref('Hình ảnh'))
   b.case('Huỷ');b.stop()
 workflow={'WFWorkflowActions':b.actions,'WFWorkflowClientVersion':'3612.0.1.3','WFWorkflowMinimumClientVersion':1106,'WFWorkflowMinimumClientVersionString':'1106',
  'WFWorkflowIcon':{'WFWorkflowIconStartColor':431817727,'WFWorkflowIconGlyphNumber':59511},'WFWorkflowName':'Bill',
  'WFWorkflowInputContentItemClasses':['WFImageContentItem'],'WFWorkflowOutputContentItemClasses':[],
  'WFWorkflowTypes':['ActionExtension'],'WFQuickActionSurfaces':[],'WFWorkflowHasShortcutInputVariables':True,'WFWorkflowHasOutputFallback':False,'WFWorkflowImportQuestions':[]}
 workflow=externalize(workflow);BUILD.mkdir(exist_ok=True)
 (BUILD/'Bill-v3.4.0-unsigned.shortcut').write_bytes(plistlib.dumps(workflow,fmt=plistlib.FMT_BINARY,sort_keys=False))
 (BUILD/'bill-workflow.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2));return workflow

if __name__=='__main__':print('Built Bill:',len(build_bill()['WFWorkflowActions']),'native actions')
