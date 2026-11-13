"""Move Text constants and UI copy into a native dictionary at the top.

Dynamic values remain runtime tokens; never evaluate order-specific data while
building the startup dictionary. Menu branch labels stay native literal routing
labels so editing copy cannot accidentally disconnect a branch.
"""
from __future__ import annotations
import copy
import hashlib
import re
from shortcut_builder import Builder, ref, token, uid

CATALOG_NAME = 'Nội dung giao diện'


def centralize(workflow):
    workflow = copy.deepcopy(workflow)
    strings = {'Trống': ''}
    reverse = {'': 'Trống'}

    def key_for(text):
        if text not in reverse:
            label = re.sub(r'[^\w]+', '_', text, flags=re.UNICODE).strip('_')[:40] or 'Nội_dung'
            key = label + '_' + hashlib.sha256(text.encode()).hexdigest()[:8]
            strings[key] = text
            reverse[text] = key
        return reverse[text]

    def lookup(text):
        return ref(CATALOG_NAME, props=[{'Type': 'WFDictionaryValueVariableAggrandizement',
                                        'DictionaryKey': key_for(text)}])

    def localized(value):
        if isinstance(value, str):
            return token(lookup(value))
        if not isinstance(value, dict) or value.get('WFSerializationType') != 'WFTextTokenString':
            return value
        state = value['Value']
        raw = state['string'].encode('utf-16-le')
        parts, offset = [], 0
        for loc, attachment in sorted(state.get('attachmentsByRange', {}).items(), key=lambda item: int(item[0].strip('{}').split(',')[0])):
            start, length = map(int, loc.strip('{}').split(','))
            literal = raw[offset:start*2].decode('utf-16-le')
            if literal:
                parts.append(lookup(literal))
            parts.append({'Value': copy.deepcopy(attachment), 'WFSerializationType': 'WFTextTokenAttachment'})
            offset = (start+length)*2
        tail = raw[offset:].decode('utf-16-le')
        if tail or not parts:
            parts.append(lookup(tail))
        return token(*parts)

    ui_fields = {'WFAlertActionTitle', 'WFAlertActionMessage', 'WFAskActionPrompt',
                 'WFChooseFromListActionPrompt', 'WFMenuPrompt', 'WFNotificationActionBody',
                 'WFNotificationActionTitle'}
    for action in workflow['WFWorkflowActions']:
        params = action['WFWorkflowActionParameters']
        if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.gettext':
            value = params.get('WFTextActionText', '')
            if isinstance(value, str):
                action['WFWorkflowActionIdentifier'] = 'is.workflow.actions.getvalueforkey'
                params.pop('WFTextActionText', None)
                params.update(WFInput=ref(CATALOG_NAME), WFGetDictionaryValueType='Value',
                              WFDictionaryKey=key_for(value))
            else:
                params['WFTextActionText'] = localized(value)
        for key in ui_fields & params.keys():
            params[key] = localized(params[key])

    prefix = Builder()
    prefix.add('comment', WFCommentActionText='© Sentechtipsvn · Nội dung giao diện\nSửa nội dung tại Từ điển bên dưới. Không đổi tên khoá. Tên nhánh menu là nhãn điều hướng cố định. Trống là chuỗi rỗng dùng để khởi tạo biến.')
    prefix.dictionary(strings, CATALOG_NAME)
    # Separate namespace avoids colliding with UUIDs emitted by the main builder.
    ids = {a['WFWorkflowActionParameters']['UUID']: uid('ui-prefix:' + str(i)) for i,a in enumerate(prefix.actions)}
    def remap(obj):
        if isinstance(obj, dict):
            for k,v in obj.items():
                if k in {'UUID','OutputUUID'} and v in ids:
                    obj[k] = ids[v]
                else:
                    remap(v)
        elif isinstance(obj, list):
            for v in obj:
                remap(v)
    remap(prefix.actions)
    workflow['WFWorkflowActions'] = prefix.actions + workflow['WFWorkflowActions']
    for question in workflow.get('WFWorkflowImportQuestions', []):
        question['ActionIndex'] += len(prefix.actions)
    return workflow
