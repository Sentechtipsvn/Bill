"""Migrate old metadata without opening photos; preserve the financial ledger."""
from shortcut_builder import ref,token
from shared import DEFAULTS,CODE,SHA,MONEY,field,put_object,random_id,read_data,read_links,get_link,put_link

def sync41(b):
 with b.route('sync41'):
  read_data(b);read_links(b)
  # Earlier imports may have marked migration complete after visiting only
  # part of the ledger. Reconcile headers and links once with the fixed loop.
  # Existing receipt, fee, signature and image fields remain authoritative.
  with b.if_(b.get(ref('Ledger'),'_iterationFixV412'),'empty'):
   b.put(ref('Ledger'),'_sourceMigrated','','Ledger')
   b.put(ref('Ledger'),'_sharedDataHash','','Ledger')
   b.put(ref('Ledger'),'_iterationFixV412','1','Ledger');b.set('Dirty','1')
  with b.if_(b.get(ref('Ledger'),'_jsonTextV413'),'empty'):
   # A cached file hash is not proof that its orders were actually imported.
   b.put(ref('Ledger'),'_sourceMigrated','','Ledger')
   b.put(ref('Ledger'),'_sharedDataHash','','Ledger')
   b.put(ref('Ledger'),'_jsonTextV413','1','Ledger');b.set('Dirty','1')
  with b.if_(ref('DataDiskHash'),'eq','missing'):b.set('DataDirty','1')
  b.set('IndexNeedsRepair','0')
  with b.each(b.keys(ref('OrdersData')),'IndexDataID'):
   indexed=b.get(ref('SourceMap'),ref('IndexDataID'))
   with b.if_(indexed,'empty'):b.set('IndexNeedsRepair','1')
   with b.if_(indexed):
    with b.if_(b.get(ref('Ledger'),indexed),'empty'):b.set('IndexNeedsRepair','1')
  with b.if_(ref('IndexNeedsRepair'),'eq','1'):
   b.put(ref('Ledger'),'_sourceMigrated','','Ledger')
  with b.if_(b.get(ref('Ledger'),'_sourceMigrated'),'empty'):
   with b.each(b.keys(ref('Ledger')),'ExistingFinanceID'):
    with b.if_(b.match(ref('ExistingFinanceID'),SHA)):
     b.parse(b.get(ref('Ledger'),ref('ExistingFinanceID')),'OldFinance')
     with b.if_(field('OldFinance','_v41'),'empty'):
      b.dictionary(DEFAULTS,'Normalized')
      with b.each(b.keys(ref('OldFinance')),'OldField'):
       b.put(ref('Normalized'),ref('OldField'),b.get(ref('OldFinance'),ref('OldField')),'Normalized')
      b.set('OldFinance',ref('Normalized'));b.set('Dirty','1')
     with b.if_(field('OldFinance','dataID'),'empty'):
      b.set('AssignedID',field('OldFinance','invoiceCode'))
      with b.if_(b.match(ref('AssignedID'),CODE),'empty'):random_id(b,ref('OrdersData'),'AssignedID')
      candidate=b.get(ref('OrdersData'),ref('AssignedID'));b.set('CanLink','0')
      with b.if_(candidate):
       b.parse(candidate,'CandidateData')
       with b.if_(field('CandidateData','Name'),'eq',field('OldFinance','name')):
        with b.if_(field('CandidateData','Money'),'eq',field('OldFinance','total')):b.set('CanLink','1')
       with b.if_(ref('CanLink'),'eq','0'):random_id(b,ref('OrdersData'),'AssignedID')
      alias=get_link(b,ref('AssignedID'))
      with b.if_(alias):
       with b.if_(alias,'ne',ref('ExistingFinanceID')):random_id(b,ref('OrdersData'),'AssignedID')
      with b.if_(b.get(ref('OrdersData'),ref('AssignedID')),'empty'):
       b.dictionary({'Name':field('OldFinance','name'),'Money':field('OldFinance','total'),'ID':ref('AssignedID'),'DC':field('OldFinance','address'),'Number':field('OldFinance','phone')},'MigratedData')
       put_object(b,ref('OrdersData'),ref('AssignedID'),ref('MigratedData'),'OrdersData');b.set('DataDirty','1')
      b.put(ref('OldFinance'),'dataID',ref('AssignedID'),'OldFinance')
      put_link(b,ref('AssignedID'),ref('ExistingFinanceID'));b.set('Dirty','1')
     existing_data_id=field('OldFinance','dataID')
     with b.if_(b.match(existing_data_id,CODE)):
      existing_link=get_link(b,existing_data_id);b.set('RepairOwnLink','0')
      with b.if_(existing_link,'empty'):b.set('RepairOwnLink','1')
      with b.if_(existing_link):
       with b.if_(b.get(ref('Ledger'),existing_link),'empty'):b.set('RepairOwnLink','1')
      with b.if_(ref('RepairOwnLink'),'eq','1'):
       put_link(b,existing_data_id,ref('ExistingFinanceID'));b.set('Dirty','1')
     b.put(ref('Ledger'),ref('ExistingFinanceID'),b.text(ref('OldFinance')),'Ledger')
   b.put(ref('Ledger'),'_sourceMigrated','1','Ledger');b.set('Dirty','1')
  b.set('DataChanged','0')
  with b.if_(b.get(ref('Ledger'),'_sharedDataHash'),'ne',ref('DataDiskHash')):b.set('DataChanged','1')
  with b.if_(ref('DataDirty'),'eq','1'):b.set('DataChanged','1')
  # Check the import index even when the file hash is unchanged. A previous
  # incomplete import must never make a real order disappear indefinitely.
  with b.if_(ref('IndexNeedsRepair'),'eq','1'):b.set('DataChanged','1')
  with b.if_(ref('DataChanged'),'eq','1'):
   with b.each(b.keys(ref('OrdersData')),'DataID'):
    with b.if_(b.match(ref('DataID'),CODE),'empty'):b.alert('ID chưa hợp lệ','Dữ liệu cũ được giữ nguyên.');b.stop()
    b.parse(b.get(ref('OrdersData'),ref('DataID')),'DataRecord')
    for key,pattern in [('Name',r'\p{L}'),('Money',MONEY),('ID',CODE)]:
     with b.if_(b.match(field('DataRecord',key),pattern),'empty'):b.alert('Đơn chưa hợp lệ','Kiểm tra DonHang.json.');b.stop()
    with b.if_(field('DataRecord','ID'),'ne',ref('DataID')):b.alert('ID không khớp','Dữ liệu cũ được giữ nguyên.');b.stop()
    with b.if_(b.count(b.keys(ref('DataRecord'))),'ne','5'):b.alert('Sai cấu trúc đơn','Cần Name, Money, ID, DC, Number.');b.stop()
    b.hash(b.text(token('sen-bill-id:',ref('DataID'))),'DataFinanceID')
    alias=get_link(b,ref('DataID'))
    with b.if_(b.match(alias,SHA)):b.set('DataFinanceID',alias)
    old=b.get(ref('Ledger'),ref('DataFinanceID'))
    with b.if_(old,'empty'):
     values={**DEFAULTS,'id':ref('DataFinanceID'),'filename':b.text(token(ref('DataID'),'.png')),'dataID':ref('DataID'),
      'name':field('DataRecord','Name'),'total':field('DataRecord','Money'),'invoiceCode':ref('DataID'),'address':field('DataRecord','DC'),'phone':field('DataRecord','Number'),
      'createdAt':ref('NowISO'),'createdMonth':ref('CurrentMonth')}
     b.dictionary(values,'ImportedFinance');b.put(ref('Ledger'),ref('DataFinanceID'),b.text(ref('ImportedFinance')),'Ledger')
     b.set('Dirty','1')
    with b.if_(old):
     b.parse(old,'ExistingFinance');b.set('HeaderChanged','0')
     with b.if_(b.math(field('ExistingFinance','cash'),'+',field('ExistingFinance','bank')),'gt',field('DataRecord','Money')):
      b.alert('Số tiền cần kiểm tra','Tổng mới nhỏ hơn số tiền đã thu.');b.stop()
     pairs=[('name','Name'),('total','Money'),('address','DC'),('phone','Number')]
     for internal,external in pairs:
      with b.if_(field('ExistingFinance',internal),'ne',field('DataRecord',external)):b.set('HeaderChanged','1')
     with b.if_(ref('HeaderChanged'),'eq','1'):
      for internal,external in pairs:b.put(ref('ExistingFinance'),internal,field('DataRecord',external),'ExistingFinance')
      b.put(ref('Ledger'),ref('DataFinanceID'),b.text(ref('ExistingFinance')),'Ledger');b.set('Dirty','1')
    with b.if_(b.get(ref('SourceMap'),ref('DataID')),'ne',ref('DataFinanceID')):
     put_link(b,ref('DataID'),ref('DataFinanceID'));b.set('Dirty','1')
  with b.if_(ref('Dirty'),'eq','1'):b.set('SaveReturn','main');b.go('save')
  with b.if_(ref('Dirty'),'eq','0'):b.go('main')
