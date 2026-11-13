"""Shared native Shortcuts storage, JSON catalog and five-field order format."""
from pathlib import Path
import copy,json
from shortcut_builder import Builder,ref,token,dyn,uid,storage
ROOT=Path(__file__).resolve().parents[1]
DATA_NAME='DonHang.json'
UI_NAME='ui-v4.1.json'
UI_URL='https://raw.githubusercontent.com/Sentechtipsvn/Bill/master/data/'+UI_NAME
CODE=r'\A[A-Za-z0-9][A-Za-z0-9_-]{0,23}\z'
SHA=r'\A[a-f0-9]{64}\z'
MONEY=r'\A(?:0|[1-9][0-9]{0,11}|1000000000000)\z'
DEFAULTS={k:'' for k in ['id','filename','name','total','createdAt','createdMonth','invoiceCode','address','phone','deliveryNote','signedDay','signedMonth','deliveredAt','deliveryMonth','events','latestReport','reportHistory','note','reportSentAt','updatedAt','dataID']}
DEFAULTS.update({k:'0' for k in ['cash','bank','bankVerified','fee','feeReversed','deleted','destroyed','cancelled']})
DEFAULTS.update(outcome='pending',_v41='1')
def field(source,key):
 return ref(source,props=[{'Type':'WFDictionaryValueVariableAggrandizement','DictionaryKey':key}])
def put_object(b,dictionary,key,value,var):
 # WFDictionaryValue is a text-input parameter on iOS. A bare attachment
 # imports as an unconfigured value; a sole dictionary token preserves type.
 typed=copy.deepcopy(value)
 typed['Value'].setdefault('Aggrandizements',[]).append({'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFDictionaryContentItem'})
 return b.set(var,b.add('setvalueforkey',WFDictionary=dictionary,WFDictionaryKey=dyn(key),WFDictionaryValue=dyn(typed)))
def load_ui(b,force=False):
 cached=b.load(ref('AppFolder'),UI_NAME)
 b.set('UICacheFile',cached)
 if force:b.set('UICacheFile','')
 with b.if_(ref('UICacheFile'),'empty'):
  response=b.add('downloadurl',WFURL=dyn(UI_URL));b.parse(response,'SharedUI')
  with b.if_(field('SharedUI','schema'),'ne','sen-bill-ui-v1'):
   b.alert('Giao diện không hợp lệ','Chưa thay dữ liệu đã lưu.');b.stop()
  b.save(b.text(ref('SharedUI')),ref('AppFolder'),UI_NAME,'UICacheFile')
 b.parse(ref('UICacheFile'),'SharedUI')
 with b.if_(field('SharedUI','schema'),'ne','sen-bill-ui-v1'):
  b.alert('Giao diện không hợp lệ','Tải lại ui-v4.1.json.');b.stop()
 b.set('Nội dung giao diện',field('SharedUI','strings'))

def ui_keys(workflow):
 # Follow only values that reach a visible prompt/list. Never localize routes,
 # file names, hash prefixes, MIME types, or state-machine constants.
 import re,hashlib
 actions={a['WFWorkflowActionParameters']['UUID']:a for a in workflow['WFWorkflowActions']}
 variables={}
 for a in workflow['WFWorkflowActions']:
  p=a['WFWorkflowActionParameters']
  if a['WFWorkflowActionIdentifier'].endswith(('setvariable','appendvariable')):variables.setdefault(p.get('WFVariableName'),[]).append(p.get('WFInput'))
 found=set();seen=set()
 def add(value):
  if value and not re.fullmatch(r'[0-9]+',value):
   label=re.sub(r'[^\w]+','_',value,flags=re.UNICODE).strip('_')[:40] or 'Nội_dung'
   found.add(label+'_'+hashlib.sha256(value.encode()).hexdigest()[:8])
 def visit(value):
  if isinstance(value,str):add(value);return
  if not isinstance(value,dict):return
  kind=value.get('WFSerializationType')
  if kind=='WFTextTokenString':
   state=value['Value'];raw=state['string'].encode('utf-16-le');offset=0
   for loc,att in sorted(state.get('attachmentsByRange',{}).items(),key=lambda i:int(i[0].strip('{}').split(',')[0])):
    start,length=map(int,loc.strip('{}').split(','));add(raw[offset:start*2].decode('utf-16-le'));visit({'Value':att,'WFSerializationType':'WFTextTokenAttachment'});offset=(start+length)*2
   add(raw[offset:].decode('utf-16-le'));return
  if kind!='WFTextTokenAttachment':return
  v=value['Value']
  if any(p.get('Type')=='WFDictionaryValueVariableAggrandizement' for p in v.get('Aggrandizements',[])):return
  key=(v.get('Type'),v.get('VariableName') or v.get('OutputUUID'))
  if key in seen:return
  seen.add(key)
  if v.get('Type')=='Variable':
   for item in variables.get(v.get('VariableName'),[]):visit(item)
  elif v.get('Type')=='ActionOutput':
   a=actions.get(v.get('OutputUUID'),{});p=a.get('WFWorkflowActionParameters',{})
   if a.get('WFWorkflowActionIdentifier','').endswith('gettext'):visit(p.get('WFTextActionText'))
 fields={'WFMenuPrompt','WFAlertActionTitle','WFAlertActionMessage','WFAskActionPrompt','WFChooseFromListActionPrompt','WFNotificationActionTitle','WFNotificationActionBody'}
 for a in workflow['WFWorkflowActions']:
  p=a['WFWorkflowActionParameters']
  for key in fields & p.keys():visit(p[key])
  if a['WFWorkflowActionIdentifier'].endswith('choosefromlist'):visit(p.get('WFInput'))
 return found

def externalize(workflow):
 from ui_catalog_legacy import centralize
 visible=ui_keys(workflow)
 w=centralize(workflow,visible_only=visible)
 prefix=w['WFWorkflowActions'][:3]
 assert prefix[1]['WFWorkflowActionIdentifier'].endswith('dictionary')
 items=prefix[1]['WFWorkflowActionParameters']['WFItems']['Value']['WFDictionaryFieldValueItems']
 strings={i['WFKey']['Value']['string']:i['WFValue']['Value']['string'] for i in items}
 path=ROOT/'data'/UI_NAME;path.parent.mkdir(parents=True,exist_ok=True)
 asset={'schema':'sen-bill-ui-v1','version':'4.1.0','strings':{},'banks':json.loads(Path(__file__).with_name('banks.json').read_text())}
 if path.exists():asset=json.loads(path.read_text())
 asset['strings'].update({k:v for k,v in strings.items() if k in visible});path.write_text(json.dumps(asset,ensure_ascii=False,indent=2))
 boot=Builder();storage(boot);load_ui(boot)
 mapping={a['WFWorkflowActionParameters']['UUID']:uid('bootstrap:'+str(i)) for i,a in enumerate(boot.actions)}
 def remap(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ('UUID','OutputUUID') and isinstance(v,str) and v in mapping:x[k]=mapping[v]
    else:remap(v)
  elif isinstance(x,list):
   for v in x:remap(v)
 remap(boot.actions)
 # Keep reset values and route/state constants as real Text action outputs.
 # A missing/empty dictionary property is Nothing, not an empty Text output.
 # Expand dictionary-property macros to explicit native Get Dictionary Value
 # actions, so iOS has an unambiguous, configured input at every use site.
 w['WFWorkflowActions']=expand_fields(boot.actions+w['WFWorkflowActions'][3:])
 return w

def expand_fields(actions):
 result=[]
 for action in actions:
  pending=[];memo={}
  def expand(obj):
   if isinstance(obj,list):return [expand(v) for v in obj]
   if not isinstance(obj,dict):return obj
   props=obj.get('Aggrandizements',[])
   if obj.get('Type') in ('Variable','ActionOutput') and any(p.get('Type')=='WFDictionaryValueVariableAggrandizement' for p in props):
    index=next(i for i,p in enumerate(props) if p['Type']=='WFDictionaryValueVariableAggrandizement')
    base=copy.deepcopy(obj);base['Aggrandizements']=props[:index]+[{'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFDictionaryContentItem'}]
    signature=json.dumps([base,props[index]['DictionaryKey']],sort_keys=True,ensure_ascii=False)
    if signature not in memo:
     ident=uid('field:'+action['WFWorkflowActionParameters']['UUID']+':'+str(len(memo)))
     pending.append({'WFWorkflowActionIdentifier':'is.workflow.actions.getvalueforkey','WFWorkflowActionParameters':{'UUID':ident,'WFInput':{'Value':base,'WFSerializationType':'WFTextTokenAttachment'},'WFGetDictionaryValueType':'Value','WFDictionaryKey':props[index]['DictionaryKey'],'CustomOutputName':props[index]['DictionaryKey']}})
     memo[signature]={'Type':'ActionOutput','OutputUUID':ident,'OutputName':props[index]['DictionaryKey']}
    replacement=copy.deepcopy(memo[signature])
    if props[index+1:]:replacement['Aggrandizements']=props[index+1:]
    return expand(replacement)
   return {k:expand(v) for k,v in obj.items()}
  expanded=expand(action);result.extend(pending);result.append(expanded)
 return result

def random_id(b, data, variable):
 b.set(variable,'0')
 with b.repeat(8):
  with b.if_(ref(variable),'eq','0'):
   candidate=b.text(b.add('number.random',WFRandomNumberMinimum=1000,WFRandomNumberMaximum=9999))
   with b.if_(b.get(data,candidate),'empty'):b.set(variable,candidate)
 with b.if_(ref(variable),'eq','0'):
  b.alert('Chưa cấp được ID','Không ghi đè đơn cũ.');b.stop()
 return ref(variable)

def read_data(b,require_migration=False):
 source=b.load(ref('AppFolder'),DATA_NAME);b.set('DataDiskHash','missing');b.dictionary(var='OrdersData');b.set('DataDirty','0')
 with b.if_(source,'empty'):
  for name in ['DonHang.backup.json','DonHang.pending.json']:
   backup=b.load(ref('AppFolder'),name)
   with b.if_(backup):b.alert('Cần khôi phục dữ liệu','DonHang.json đang thiếu. Giữ bản sao lưu.');b.stop()
  if require_migration:
   old=b.load(ref('AppFolder'),'orders.json')
   with b.if_(old):b.alert('Chạy Phiếu Giao Hàng v4.1 trước','Chuyển sổ cũ trước khi nhập đơn.');b.stop()
 with b.if_(source):
  b.hash(b.text(source),'DataDiskHash');b.parse(source,'OrdersData')

def save_data(b):
 fresh=b.load(ref('AppFolder'),DATA_NAME);b.set('LatestDataHash','missing')
 with b.if_(fresh):b.hash(b.text(fresh),'LatestDataHash')
 with b.if_(ref('LatestDataHash'),'ne',ref('DataDiskHash')):
  b.alert('Dữ liệu đã thay đổi','Chạy lại phím tắt.');b.stop()
 payload=b.text(ref('OrdersData'));expected=b.hash(payload)
 b.save(payload,ref('AppFolder'),'DonHang.pending.json')
 pending=b.load(ref('AppFolder'),'DonHang.pending.json')
 with b.if_(b.hash(b.text(pending)),'ne',expected):b.alert('Chưa lưu được dữ liệu','Sổ cũ được giữ nguyên.');b.stop()
 with b.if_(fresh):b.save(fresh,ref('AppFolder'),'DonHang.backup.json')
 b.save(payload,ref('AppFolder'),DATA_NAME);stored=b.load(ref('AppFolder'),DATA_NAME)
 with b.if_(b.hash(b.text(stored)),'ne',expected):b.alert('Chưa xác minh được dữ liệu','Giữ bản chờ và bản sao lưu.');b.stop()
 b.set('DataDiskHash',expected);b.set('DataDirty','0')

def read_links(b):
 b.dictionary(var='SourceMap');raw=b.get(ref('Ledger'),'_sourceMap')
 with b.if_(raw):b.parse(raw,'SourceMap')

def get_link(b,key):
 name='SourceLink_'+str(len(b.actions));b.get(ref('SourceMap'),key,name)
 with b.if_(ref(name),'empty'):
  old=b.get(ref('Ledger'),b.text(token('_source_',key)))
  with b.if_(old):b.set(name,old)
 return ref(name)

def put_link(b,key,value):
 b.put(ref('SourceMap'),key,value,'SourceMap')
