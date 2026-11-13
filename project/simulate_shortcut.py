"""A strict, local action-graph simulator, not an iOS runtime.

It executes the actual emitted actions and control-flow markers against a
mock filesystem, clock, image picker, camera, menus, and share sheet. Native
permissions, iCloud provider behavior, image readability and device import
must still be checked on iPhone.
"""
from __future__ import annotations
import ast
import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo
import regex


class Pause(Exception):
    pass


class Stop(Exception):
    pass


@dataclass
class File:
    path: str
    data: object = ""
    created: datetime | None = None
    width: int = 0
    height: int = 0
    image_format: str = ""
    quality: float = 1.0

    @property
    def name(self):
        return PurePosixPath(self.path).name


@dataclass
class Named:
    data: object
    name: str


def text(x):
    if x is None:
        return ""
    if isinstance(x, File):
        return text(x.data) if not x.width else x.name
    if isinstance(x, Named):
        return text(x.data)
    if isinstance(x, dict):
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    if isinstance(x, list):
        return "\n".join(text(v) for v in x)
    if isinstance(x, regex.Match):
        return x.group(0)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def flatten(x):
    if isinstance(x, list):
        return [v for i in x for v in flatten(i)]
    return [] if x is None or x == "" else [x]


def graph(actions):
    def parse(index, stop_group=None):
        result = []
        while index < len(actions):
            a = actions[index]
            p = a['WFWorkflowActionParameters']
            mode = p.get('WFControlFlowMode')
            g = p.get('GroupingIdentifier')
            if g == stop_group and mode in (1, 2):
                return result, index
            if mode == 0:
                ident = a['WFWorkflowActionIdentifier'].split('is.workflow.actions.')[-1]
                if ident == 'choosefrommenu':
                    branches = []
                    index += 1
                    while True:
                        marker = actions[index]['WFWorkflowActionParameters']
                        if marker['WFControlFlowMode'] == 2:
                            break
                        assert marker['WFControlFlowMode'] == 1
                        body, end = parse(index + 1, g)
                        branches.append((marker['WFMenuItemTitle'], body))
                        index = end
                    result.append(('menu', a, branches))
                elif ident == 'conditional':
                    yes, index = parse(index + 1, g)
                    no = []
                    if actions[index]['WFWorkflowActionParameters']['WFControlFlowMode'] == 1:
                        no, index = parse(index + 1, g)
                    result.append(('if', a, yes, no))
                else:
                    assert ident in ('repeat.each', 'repeat.count'), ident
                    body, index = parse(index + 1, g)
                    result.append(('each' if ident.endswith('each') else 'repeat', a, body))
                index += 1
            else:
                assert mode is None, (index, a)
                result.append(('action', a))
                index += 1
        assert stop_group is None, stop_group
        return result, index
    return parse(0)[0]


class Simulator:
    def __init__(self, workflow, files=None, choices=None, answers=None, photos=None, camera=None,
                 now=None, installed=None, names_include_extension=True, shortcut_input=None):
        self.workflow = workflow
        self.nodes = graph(workflow['WFWorkflowActions'])
        self.files = copy.deepcopy(files or {})
        self.vars, self.outputs = {}, {}
        self.choices = list(choices or [])
        self.answers = list(answers or [])
        self.photos = photos or [File('photos/screenshot.png', width=1170, height=2532, image_format='PNG')]
        self.camera = camera or File('camera/signature.heic', width=3024, height=4032, image_format='HEIF')
        self.now = now or datetime(2026, 11, 11, 23, 0, tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
        self.installed = ['Quick Call Image'] if installed is None else installed
        self.names_include_extension = names_include_extension
        self.alerts, self.previews, self.shares, self.calls = [], [], [], []
        self.clipboard = ''
        self.last_ui = None
        self.executed = 0
        self.loop_depth = 0
        self.shortcut_input = shortcut_input or []
        self.random = random.Random(0)
        self.file_reads=[];self.folder_reads=[];self.network=[];self.opens=[];self.file_picks=[];self.network_handler=None;self.before_save=None;self.asks=[]

    def resolve(self, x):
        if not isinstance(x, dict):
            if isinstance(x, list):
                return [self.resolve(v) for v in x]
            return x
        kind = x.get('WFSerializationType')
        if kind == 'WFTextTokenAttachment':
            v = x['Value']
            if v['Type'] == 'Variable':
                name = v['VariableName']
                if name not in self.vars:
                    raise AssertionError(f'Undefined variable: {name}; route={self.vars.get("Route")}')
                result = self.vars[name]
            elif v['Type'] == 'ActionOutput':
                if v['OutputUUID'] not in self.outputs:
                    raise AssertionError(f'Action output was skipped: {v}')
                result = self.outputs[v['OutputUUID']]
            elif v['Type'] == 'ExtensionInput':
                result = self.shortcut_input
            else:
                raise AssertionError(v)
            for prop in v.get('Aggrandizements', []):
                if prop['Type'] == 'WFCoercionVariableAggrandizement':
                    target = prop['CoercionItemClass']
                    if target == 'WFStringContentItem':
                        result = text(result)
                    elif target == 'WFNumberContentItem':
                        result = float(text(result))
                elif prop['Type'] == 'WFDictionaryValueVariableAggrandizement':
                    result = result.get(prop['DictionaryKey'], '')
                elif prop['Type'] == 'WFPropertyVariableAggrandizement':
                    if prop['PropertyName'] == 'Width':
                        result = result.width
                    elif prop['PropertyName'] == 'Height':
                        result = result.height
                    else:
                        raise AssertionError(prop)
                else:
                    raise AssertionError(prop)
            return result
        if kind == 'WFTextTokenString':
            v = x['Value']
            raw = v['string'].encode('utf-16-le')
            for loc, val in sorted(v.get('attachmentsByRange', {}).items(), key=lambda y: int(y[0].strip('{}').split(',')[0]), reverse=True):
                start, count = map(int, loc.strip('{}').split(','))
                rep = text(self.resolve({'Value': val, 'WFSerializationType': 'WFTextTokenAttachment'})).encode('utf-16-le')
                assert raw[start*2:(start+count)*2] == '\ufffc'.encode('utf-16-le'), (loc, v)
                raw = raw[:start*2] + rep + raw[(start+count)*2:]
            return raw.decode('utf-16-le')
        if kind == 'WFDictionaryFieldValue':
            return {text(self.resolve(i['WFKey'])): self.resolve(i['WFValue']) for i in x['Value']['WFDictionaryFieldValueItems']}
        if 'fileLocation' in x:
            return 'shortcuts' if x['fileLocation'].get('WFFileLocationType') == 'Shortcuts' else 'source'
        return {k: self.resolve(v) for k, v in x.items()}

    def condition(self, p):
        left = self.resolve(p['WFInput']['Variable'])
        code = p['WFCondition']
        if code == 100:
            return bool(flatten(left))
        if code == 101:
            return not bool(flatten(left))
        right = self.resolve(p.get('WFNumberValue', p.get('WFConditionalActionString')))
        if code in (0, 1, 2, 3):
            left, right = float(text(left)), float(text(right))
            return {0: left < right, 1: left <= right, 2: left > right, 3: left >= right}[code]
        if code == 4:
            return text(left) == text(right)
        if code == 5:
            return text(left) != text(right)
        if code == 99:
            return text(right) in text(left)
        raise AssertionError(code)

    def pick(self, prompt, options):
        self.last_ui = (prompt, options)
        if not self.choices:
            raise Pause()
        choice = self.choices.pop(0)
        if choice is None:
            raise Stop()
        if callable(choice):
            choice = choice(prompt, options)
        if isinstance(choice, list):
            assert all(v in options for v in choice), (choice, options)
            return choice
        if isinstance(choice, int):
            return options[choice]
        assert choice in options, (choice, prompt, options)
        return choice

    def run(self):
        try:
            self.sequence(self.nodes)
        except (Pause, Stop):
            pass
        return self

    def sequence(self, nodes):
        for node in nodes:
            self.executed += 1
            assert self.executed < 500000, self.vars.get('Route')
            kind, a = node[:2]
            p = a['WFWorkflowActionParameters']
            if kind == 'if':
                self.sequence(node[2] if self.condition(p) else node[3])
            elif kind == 'menu':
                prompt = text(self.resolve(p.get('WFMenuPrompt', '')))
                pick = self.pick(prompt, [title for title, _ in node[2]])
                self.sequence(next(body for title, body in node[2] if title == pick))
            elif kind in ('each', 'repeat'):
                values = flatten(self.resolve(p['WFInput'])) if kind == 'each' else range(int(self.resolve(p['WFRepeatCount'])))
                self.loop_depth += 1
                suffix = '' if self.loop_depth == 1 else f' {self.loop_depth}'
                item_name, index_name = 'Repeat Item'+suffix, 'Repeat Index'+suffix
                old_item = self.vars.get(item_name, None)
                old_index = self.vars.get(index_name, None)
                for index, value in enumerate(values, 1):
                    self.vars[item_name] = value
                    self.vars[index_name] = index
                    self.sequence(node[2])
                if old_item is not None:
                    self.vars[item_name] = old_item
                else:
                    self.vars.pop(item_name, None)
                if old_index is not None:
                    self.vars[index_name] = old_index
                else:
                    self.vars.pop(index_name, None)
                self.loop_depth -= 1
            else:
                result = self.action(a)
                self.outputs[p['UUID']] = result

    def action(self, a):
        p = a['WFWorkflowActionParameters']
        ident = a['WFWorkflowActionIdentifier'].removeprefix('is.workflow.actions.')
        get = lambda k, d=None: self.resolve(p.get(k, d))
        if ident == 'comment':
            return None
        if ident == 'gettext':
            return text(get('WFTextActionText', ''))
        if ident == 'number':
            return get('WFNumberActionNumber')
        if ident == 'number.random':
            return self.random.randint(int(get('WFRandomNumberMinimum')), int(get('WFRandomNumberMaximum')))
        if ident == 'setvariable':
            v = copy.deepcopy(get('WFInput'))
            self.vars[p['WFVariableName']] = v
            return v
        if ident == 'appendvariable':
            v = flatten(copy.deepcopy(get('WFInput')))
            self.vars.setdefault(p['WFVariableName'], []).extend(v)
            return self.vars[p['WFVariableName']]
        if ident == 'dictionary':
            return get('WFItems')
        if ident == 'getvalueforkey':
            d = get('WFInput')
            assert isinstance(d, dict), ('Expected dictionary', d)
            t = get('WFGetDictionaryValueType', 'Value')
            return list(d) if t == 'All Keys' else list(d.values()) if t == 'All Values' else d.get(text(get('WFDictionaryKey')), '')
        if ident == 'setvalueforkey':
            d = copy.deepcopy(get('WFDictionary'))
            d[text(get('WFDictionaryKey'))] = get('WFDictionaryValue')
            return d
        if ident == 'detect.dictionary':
            return json.loads(text(get('WFInput')))
        if ident == 'calculateexpression':
            expr = text(get('Input'))
            assert regex.fullmatch(r'[0-9+*/().\- ]+', expr), expr
            tree = ast.parse(expr, mode='eval')
            result = eval(compile(tree, '<native arithmetic>', 'eval'), {'__builtins__': {}}, {})
            return int(result) if isinstance(result, float) and result.is_integer() else result
        if ident == 'count':
            value = get('Input')
            return len(text(value)) if get('WFCountType') == 'Characters' else len(flatten(value))
        if ident == 'text.match':
            return list(regex.finditer(get('WFMatchTextPattern'), text(get('text'))))
        if ident == 'text.match.getgroup':
            m = get('matches')
            if isinstance(m, list):
                m = m[0]
            return m.group(int(get('WFGroupIndex')))
        if ident == 'text.replace':
            s, find, rep = text(get('WFInput')), get('WFReplaceTextFind'), text(get('WFReplaceTextReplace', ''))
            rep = regex.sub(r'\$([0-9]+)', r'\\g<\1>', rep)
            return regex.sub(find, rep, s) if get('WFReplaceTextRegularExpression') else s.replace(find, rep)
        if ident == 'text.changecase':
            s = text(get('text'))
            return s.lower() if get('WFCaseType').lower() == 'lowercase' else s.upper()
        if ident == 'list':
            return get('WFItems')
        if ident == 'getitemfromlist':
            x = flatten(get('WFInput'))
            spec = get('WFItemSpecifier')
            if spec == 'Items in Range':
                return x[int(float(text(get('WFItemRangeStart'))))-1:int(float(text(get('WFItemRangeEnd'))))]
            i = 1 if spec == 'First Item' else len(x) if spec == 'Last Item' else int(float(text(get('WFItemIndex'))))
            assert 1 <= i <= len(x), (i, len(x))
            return x[i-1]
        if ident == 'text.combine':
            return get('WFTextCustomSeparator', '\n').join(text(v) for v in flatten(get('text')))
        if ident == 'text.split':
            return text(get('text')).split(get('WFTextCustomSeparator', '\n'))
        if ident == 'hash':
            raw=get('WFInput')
            while isinstance(raw,(File,Named)):raw=raw.data
            return hashlib.sha256(raw if isinstance(raw,bytes) else text(raw).encode()).hexdigest()
        if ident == 'date':
            return self.now
        if ident == 'format.date':
            d = get('WFDate')
            if isinstance(d, str):
                d = datetime.fromisoformat(d)
            if get('WFDateFormatStyle') == 'ISO 8601':
                return d.isoformat(timespec='seconds')
            formats = {'MM-yyyy':'%m-%Y','yyyy-MM-dd':'%Y-%m-%d', 'yyyy-MM': '%Y-%m', 'dd': '%d', "yyyy-MM-dd'T'HH:mm:ssXXX": '%Y-%m-%dT%H:%M:%S%z',
                       'yyyyMMdd-HHmmssSSS': '%Y%m%d-%H%M%S%f', 'yyyyMMddHHmmssSSS': '%Y%m%d%H%M%S%f'}
            s = d.strftime(formats[get('WFDateFormat')])
            if get('WFDateFormat').endswith('SSS'):
                s = s[:-3]
            if get('WFDateFormat').endswith('XXX'):
                s = s[:-2] + ':' + s[-2:]
            return s
        if ident == 'file':
            # Model the source-folder import question as configured by its user.
            if self.workflow['WFWorkflowImportQuestions']:
                source_index = self.workflow['WFWorkflowImportQuestions'][0]['ActionIndex']
                if p['UUID'] == self.workflow['WFWorkflowActions'][source_index]['WFWorkflowActionParameters']['UUID']:
                    return 'source'
            return get('WFFile')
        if ident == 'file.createfolder':
            return str(PurePosixPath(get('WFFolder')) / text(get('WFFilePath')))
        if ident == 'file.getfoldercontents':
            folder = get('WFFolder')
            self.folder_reads.append(folder)
            return [v for k, v in self.files.items() if str(PurePosixPath(k).parent) == folder]
        if ident == 'filter.files':
            items=flatten(get('WFContentItemInputParameter'))
            if get('WFContentItemSortProperty')=='Name':
                return sorted(items,key=lambda f: f.name if isinstance(f,File) else text(f),reverse=get('WFContentItemSortOrder')=='Z to A')
            return sorted(items,key=lambda f:f.created or self.now,reverse=True)
        if ident == 'filter.images':
            return [f for f in flatten(get('WFContentItemInputParameter')) if isinstance(f, File) and f.width > 0 and f.height > 0]
        if ident == 'getitemname':
            f = get('WFInput')
            if isinstance(f, File):
                return f.name if self.names_include_extension else PurePosixPath(f.name).stem
            return f
        if ident == 'properties.files':
            f = get('WFInput')
            prop = get('WFContentItemPropertyName')
            return {'File Extension': PurePosixPath(f.name).suffix[1:], 'Creation Date': f.created or self.now, 'Name': f.name}[prop]
        if ident == 'setitemname':
            return Named(get('WFInput'), text(get('WFName')))
        if ident == 'documentpicker.save':
            value = get('WFInput')
            if self.before_save:self.before_save(self,p)
            assert isinstance(value, Named)
            path = str(PurePosixPath(get('WFFolder')) / text(get('WFFileDestinationPath', value.name)))
            assert get('WFSaveFileOverwrite') or path not in self.files, ('Unexpected overwrite', path)
            data = value.data
            if isinstance(data, File):
                saved = copy.deepcopy(data)
                saved.path = path
            else:
                saved = File(path, text(data), self.now)
            self.files[path] = saved
            return saved
        if ident == 'documentpicker.open':
            if get('WFAskWhereToGetFile'):
                if not self.file_picks:raise Pause()
                return self.file_picks.pop(0)
            path = str(PurePosixPath(get('WFFile')) / text(get('WFGetFilePath')))
            self.file_reads.append(path)
            return copy.deepcopy(self.files.get(path, ''))
        if ident == 'choosefromlist':
            return self.pick(text(get('WFChooseFromListActionPrompt', '')), flatten(get('WFInput')))
        if ident == 'ask':
            self.asks.append((text(get('WFAskActionPrompt')),get('WFAskActionDefaultAnswer'),get('WFInputType')))
            self.last_ui = (text(get('WFAskActionPrompt')), [])
            if not self.answers:
                raise Pause()
            value = self.answers.pop(0)
            if value=='__DEFAULT__':value=get('WFAskActionDefaultAnswer')
            if value is None:
                raise Stop()
            return value
        if ident == 'alert':
            self.alerts.append((text(get('WFAlertActionTitle')), text(get('WFAlertActionMessage'))))
            return None
        if ident == 'exit':
            raise Stop()
        if ident == 'setclipboard':
            self.clipboard = text(get('WFInput'))
            return get('WFInput')
        if ident == 'previewdocument':
            self.previews.append(get('WFInput'))
            return None
        if ident == 'getmyworkflows':
            return self.installed
        if ident == 'runworkflow':
            workflow = get('WFWorkflowName', get('WFWorkflow'))
            if workflow not in self.installed:
                self.alerts.append(('Không tìm thấy phím tắt', workflow))
                raise Stop()
            self.calls.append((workflow, get('WFInput')))
            return None
        if ident == 'selectphoto':
            return self.photos
        if ident == 'takephoto':
            return self.camera
        if ident == 'image.rotate':
            f = copy.deepcopy(get('WFImage'))
            f.width, f.height = f.height, f.width
            return f
        if ident == 'round':
            return math.floor(float(text(get('WFInput'))) + .5)
        if ident == 'image.resize':
            f = copy.deepcopy(get('WFImage'))
            f.width, f.height = int(float(text(get('WFImageResizeWidth')))), int(float(text(get('WFImageResizeHeight'))))
            return f
        if ident == 'image.convert':
            f = copy.deepcopy(get('WFInput'))
            if isinstance(f, list):
                assert len(f) == 1
                f = f[0]
            f.image_format, f.quality = get('WFImageFormat'), get('WFImageCompressionQuality')
            return f
        if ident == 'detect.images':
            return [f for f in flatten(get('WFInput')) if isinstance(f, File) and f.width > 0 and f.height > 0]
        if ident == 'extracttextfromimage':
            images = flatten(get('WFImage'))
            assert len(images) == 1
            return text(images[0].data)
        if ident == 'base64encode':
            import base64,io
            if get('WFEncodeMode')=='Decode':
                from PIL import Image
                data=base64.b64decode(text(get('WFInput')),validate=False)
                try:
                    image=Image.open(io.BytesIO(data));w,h=image.size
                    return File('decoded/qr.png',data,w and self.now,w,h,image.format)
                except Exception:return File('decoded/data',data)
            raw=get('WFInput')
            while isinstance(raw,(File,Named)):raw=raw.data
            if not isinstance(raw,bytes):raw=text(raw).encode()
            return base64.b64encode(raw).decode()
        if ident == 'urlencode':
            from urllib.parse import quote
            return quote(text(get('WFInput')),safe='')
        if ident == 'url': return get('WFURLActionURL')
        if ident == 'openurl':
            self.opens.append(text(get('WFInput')));return None
        if ident == 'downloadurl':
            url=text(get('WFURL'));self.network.append(url)
            if self.network_handler:return self.network_handler(url)
            return File('network/qr.svg',width=540,height=640,image_format='SVG',data='<svg xmlns="http://www.w3.org/2000/svg" width="540" height="640"><rect width="540" height="640" fill="white"/><path d="M0 0h1v1h-1z"/></svg>')
        if ident == 'share':
            self.shares.append(get('WFInput'))
            return None
        if ident == 'file.delete':
            for f in flatten(get('WFInput')):
                self.files.pop(f.path, None)
            return None
        raise AssertionError(f'Unsupported action: {ident}')


def validate(workflow):
    actions = workflow['WFWorkflowActions']
    all_ids = [a['WFWorkflowActionParameters']['UUID'] for a in actions]
    assert len(set(all_ids)) == len(all_ids), 'Duplicate action UUID'
    seen = set()
    used_outputs = set()
    def walk(x):
        if isinstance(x, dict):
            if x.get('Type') == 'ActionOutput':
                assert x['OutputUUID'] in seen, ('Forward or missing action reference', x)
                used_outputs.add(x['OutputUUID'])
            if x.get('WFSerializationType') == 'WFTextTokenString':
                v = x['Value']
                raw = v['string'].encode('utf-16-le')
                assert len(v.get('attachmentsByRange', {})) == v['string'].count('\ufffc')
                for loc, attachment in v.get('attachmentsByRange', {}).items():
                    start, length = map(int, loc.strip('{}').split(','))
                    assert raw[start*2:(start+length)*2] == '\ufffc'.encode('utf-16-le'), (loc, v)
                    assert attachment['Type'] in ('Variable', 'ActionOutput')
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for a in actions:
        walk(a['WFWorkflowActionParameters'])
        seen.add(a['WFWorkflowActionParameters']['UUID'])
    graph(actions)
    for q in workflow['WFWorkflowImportQuestions']:
        assert q['ParameterKey'] in actions[q['ActionIndex']]['WFWorkflowActionParameters']
    forbidden = ['runjavascript', 'runshellscript', 'runsshscript','sendmessage','sendemail']
    assert not any(any(f in a['WFWorkflowActionIdentifier'] for f in forbidden) for a in actions)
    return {'actions': len(actions), 'references': len(used_outputs), 'native_only': True}
