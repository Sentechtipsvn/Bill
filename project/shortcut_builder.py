"""Native Apple Shortcuts builder for Ảnh đơn hàng, SenTechTipsVN.

No web runtime, injected JavaScript or third-party execution is required.
The generated action graph is the source exercised by the local simulator.
"""
from __future__ import annotations

import copy
import json
import plistlib
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
VERSION = "4.1.1"
NS = uuid.UUID("2714394b-4b0c-4b8c-953d-2578ced9d54a")


def uid(label):
    return str(uuid.uuid5(NS, str(label))).upper()


def ref(name, kind=None, props=None):
    d = {"Type": "Variable", "VariableName": name}
    if kind:
        d["Aggrandizements"] = [{"Type": "WFCoercionVariableAggrandizement", "CoercionItemClass": kind}]
    if props:
        d.setdefault("Aggrandizements", []).extend(props)
    return {"Value": d, "WFSerializationType": "WFTextTokenAttachment"}


def output(action_id, name):
    return {"Value": {"Type": "ActionOutput", "OutputUUID": action_id, "OutputName": name},
            "WFSerializationType": "WFTextTokenAttachment"}


def token(*parts):
    s, positions = "", {}
    for part in parts:
        if isinstance(part, dict):
            pos = len(s.encode("utf-16-le")) // 2
            positions[f"{{{pos}, 1}}"] = copy.deepcopy(part["Value"])
            s += "\ufffc"
        else:
            s += str(part)
    if not positions:
        return s
    return {"Value": {"string": s, "attachmentsByRange": positions},
            "WFSerializationType": "WFTextTokenString"}


def dyn(value):
    if isinstance(value, dict):
        return value if value.get("WFSerializationType") == "WFTextTokenString" else token(value)
    return str(value)


class Builder:
    def __init__(self):
        self.actions = []
        self.blocks = []
        self.sections = {}
        self.loop_depth = 0
        self.variable_types = {}
        self.output_types = {}

    def value_type(self, value):
        if isinstance(value, dict) and value.get("WFSerializationType") == "WFTextTokenAttachment":
            v = value["Value"]
            if v.get("Type") == "Variable":
                return self.variable_types.get(v.get("VariableName"), "text")
            return self.output_types.get(v.get("OutputUUID"), "text")
        return "text"

    def add(self, action, **p):
        action = action if "." in action and not action.startswith("file.") and not action.startswith("text.") and not action.startswith("image.") and not action.startswith("format.") and not action.startswith("documentpicker.") and not action.startswith("properties.") else "is.workflow.actions." + action
        if not action.startswith(("is.workflow.actions.", "com.")):
            action = "is.workflow.actions." + action
        action_id = uid(f"{len(self.actions)}:{action}")
        p = copy.deepcopy(p)
        def scope(value):
            if isinstance(value, dict):
                if value.get("Type") == "Variable" and value.get("VariableName") == "Repeat Index" and self.loop_depth > 1:
                    value["VariableName"] = f"Repeat Index {self.loop_depth}"
                for item in value.values():
                    scope(item)
            elif isinstance(value, list):
                for item in value:
                    scope(item)
        scope(p)
        labels = {"gettext": "Văn bản", "date": "Ngày", "format.date": "Ngày được định dạng",
                  "file": "Tệp hoặc thư mục", "file.createfolder": "Thư mục đã tạo",
                  "file.getfoldercontents": "Nội dung thư mục", "filter.files": "Danh sách tệp",
                  "filter.images": "Danh sách ảnh", "properties.files": "Chi tiết tệp", "getitemname": "Tên tệp",
                  "text.match": "Kết quả khớp", "text.replace": "Văn bản đã thay thế", "text.changecase": "Văn bản đổi kiểu",
                  "count": "Đếm", "getitemfromlist": "Mục trong danh sách", "getvalueforkey": "Giá trị từ điển",
                  "setvalueforkey": "Từ điển cập nhật", "dictionary": "Từ điển", "list": "Danh sách"}
        short = action.removeprefix("is.workflow.actions.")
        p.setdefault("CustomOutputName", labels.get(short, "Kết quả"))
        kind = "text"
        if short in {"date"}:
            kind = "date"
        elif short in {"file", "file.createfolder", "documentpicker.open", "documentpicker.save", "image.convert", "image.rotate", "image.resize", "takephoto"}:
            kind = "file"
        elif short in {"list", "file.getfoldercontents", "filter.files", "filter.images", "text.match", "text.split", "selectphoto", "getmyworkflows"}:
            kind = "list"
        elif short in {"count", "number", "calculateexpression", "round"}:
            kind = "number"
        elif short in {"dictionary", "detect.dictionary", "setvalueforkey"}:
            kind = "dictionary"
        elif short == "getvalueforkey" and p.get("WFGetDictionaryValueType") in {"All Keys", "All Values"}:
            kind = "list"
        self.output_types[action_id] = kind
        p = {"UUID": action_id, **p}
        self.actions.append({"WFWorkflowActionIdentifier": action, "WFWorkflowActionParameters": p})
        return output(action_id, p["CustomOutputName"])

    def text(self, value, var=None):
        r = self.add("gettext", WFTextActionText=dyn(value))
        return self.set(var, r) if var else r

    def set(self, name, value):
        if not isinstance(value, dict) or value.get("WFSerializationType") == "WFTextTokenString":
            value = self.text(value)
        self.variable_types[name] = self.value_type(value)
        self.add("setvariable", WFVariableName=name, WFInput=value)
        return ref(name)

    def empty_list(self, name):
        return self.set(name, self.add("list", WFItems=[]))

    def append(self, name, value):
        self.add("appendvariable", WFVariableName=name, WFInput=value)

    def dictionary(self, fields=None, var=None):
        items = []
        for key, value in (fields or {}).items():
            items.append({"WFKey": {"Value": {"string": key}, "WFSerializationType": "WFTextTokenString"},
                          "WFItemType": 0, "WFValue": self.text_state(value)})
        r = self.add("dictionary", WFItems={"Value": {"WFDictionaryFieldValueItems": items},
                                         "WFSerializationType": "WFDictionaryFieldValue"})
        return self.set(var, r) if var else r

    @staticmethod
    def text_state(value):
        value = dyn(value)
        return value if isinstance(value, dict) else {"Value": {"string": str(value)}, "WFSerializationType": "WFTextTokenString"}

    def get(self, dictionary, key, var=None):
        r = self.add("getvalueforkey", WFInput=dictionary, WFGetDictionaryValueType="Value", WFDictionaryKey=dyn(key))
        return self.set(var, r) if var else r

    def put(self, dictionary, key, value, var):
        r = self.add("setvalueforkey", WFDictionary=dictionary, WFDictionaryKey=dyn(key), WFDictionaryValue=dyn(value))
        return self.set(var, r)

    def keys(self, dictionary, var=None):
        r = self.add("getvalueforkey", WFInput=dictionary, WFGetDictionaryValueType="All Keys")
        return self.set(var, r) if var else r

    def parse(self, text, var=None):
        r = self.add("detect.dictionary", WFInput=text)
        return self.set(var, r) if var else r

    def math(self, *parts, var=None):
        numeric_parts = []
        for part in parts:
            if isinstance(part, dict) and part.get("WFSerializationType") == "WFTextTokenAttachment":
                part = copy.deepcopy(part)
                part["Value"].setdefault("Aggrandizements", []).append(
                    {"Type": "WFCoercionVariableAggrandizement", "CoercionItemClass": "WFNumberContentItem"})
            numeric_parts.append(part)
        r = self.add("calculateexpression", Input=token(*numeric_parts))
        return self.set(var, r) if var else r

    def count(self, value, var=None, kind="Items"):
        r = self.add("count", Input=value, WFInput=value, WFCountType=kind)
        return self.set(var, r) if var else r

    def match(self, value, pattern, var=None):
        r = self.add("text.match", text=dyn(value), WFMatchTextPattern=pattern, WFMatchTextCaseSensitive=True)
        return self.set(var, r) if var else r

    def replace(self, value, pattern, replacement="", var=None, regex=True):
        r = self.add("text.replace", WFInput=dyn(value), WFReplaceTextFind=pattern,
                     WFReplaceTextReplace=dyn(replacement), WFReplaceTextRegularExpression=regex,
                     WFReplaceTextCaseSensitive=True)
        return self.set(var, r) if var else r

    def first(self, value):
        return self.add("getitemfromlist", WFInput=value, WFItemSpecifier="First Item")

    def item(self, value, index):
        return self.add("getitemfromlist", WFInput=value, WFItemSpecifier="Item At Index", WFItemIndex=index)

    def join(self, value, separator="\n", var=None):
        r = self.add("text.combine", text=value, WFTextSeparator="Custom", WFTextCustomSeparator=separator)
        return self.set(var, r) if var else r

    def split(self, value, separator="\n", var=None):
        r = self.add("text.split", text=dyn(value), WFTextSeparator="Custom", WFTextCustomSeparator=separator)
        return self.set(var, r) if var else r

    def hash(self, value, var=None):
        r = self.add("hash", WFInput=value, WFHashType="SHA256")
        return self.set(var, r) if var else r

    def date(self, var="Now"):
        return self.set(var, self.add("date", WFDateActionMode="Current Date"))

    def fmtdate(self, value, pattern, var=None):
        # Match the WFDate token-string input used by the supplied native Bill.
        # A bare WFTextTokenAttachment is not the date parameter's text state.
        native_pattern = pattern.replace("yyyyMMdd-HHmmssSSS", "yyyyMMddHHmmssSSS")
        r = self.add("format.date", WFDate=dyn(value),
                     WFDateFormatStyle="Custom", WFDateFormat=native_pattern)
        return self.set(var, r) if var else r

    def money(self, value, var=None):
        # All stored money is integral VND. Do not depend on the device locale.
        plain = self.replace(value, r"\.0+$", "")
        r = self.replace(plain, r"(?<=[0-9])(?=(?:[0-9]{3})+$)", ".")
        return self.set(var, r) if var else r

    def fold(self, value, var=None):
        r = value
        for group, letter in [("[àáạảãâầấậẩẫăằắặẳẵ]", "a"), ("[èéẹẻẽêềếệểễ]", "e"),
                              ("[ìíịỉĩ]", "i"), ("[òóọỏõôồốộổỗơờớợởỡ]", "o"),
                              ("[ùúụủũưừứựửữ]", "u"), ("[ỳýỵỷỹ]", "y"), ("đ", "d")]:
            r = self.replace(r, "(?i)" + group, letter)
        r = self.replace(r, r"\p{M}", "")
        r = self.add("text.changecase", text=r, WFCaseType="lowercase")
        return self.set(var, r) if var else r

    def alert(self, title, message, cancel=False):
        self.add("alert", WFAlertActionTitle=dyn(title), WFAlertActionMessage=dyn(message),
                 WFAlertActionCancelButtonShown=cancel)

    def stop(self):
        self.add("exit")

    def ask(self, prompt, default="", kind="Text", var=None):
        r = self.add("ask", WFAskActionPrompt=dyn(prompt), WFInputType=kind,
                     WFAskActionDefaultAnswer=dyn(default), WFAllowsMultilineText=False,
                     WFAskActionAllowsNegativeNumbers=False, WFAskActionAllowsDecimalNumbers=False)
        return self.set(var, r) if var else r

    def choose(self, values, prompt, multi=False, var=None):
        r = self.add("choosefromlist", WFInput=values, WFChooseFromListActionPrompt=dyn(prompt),
                     WFChooseFromListActionSelectMultiple=multi, WFChooseFromListActionSelectAll=False)
        return self.set(var, r) if var else r

    @contextmanager
    def if_(self, left, op="has", right=None):
        group = uid(f"if:{len(self.actions)}")
        codes = {"has": 100, "empty": 101, "eq": 4, "ne": 5, "gt": 2, "lt": 0, "ge": 3, "le": 1, "contains": 99}
        p = {"GroupingIdentifier": group, "WFControlFlowMode": 0, "WFCondition": codes[op],
             "WFInput": {"Type": "Variable", "Variable": left}}
        if op in ("gt", "lt", "ge", "le"):
            p["WFInput"]["Variable"] = copy.deepcopy(left)
            p["WFInput"]["Variable"]["Value"].setdefault("Aggrandizements", []).append(
                {"Type": "WFCoercionVariableAggrandizement", "CoercionItemClass": "WFNumberContentItem"})
            p["WFNumberValue"] = right
        elif right is not None:
            # Coerce both Count outputs and dictionary values to text deliberately.
            p["WFInput"]["Variable"] = copy.deepcopy(left)
            p["WFInput"]["Variable"]["Value"].setdefault("Aggrandizements", []).append(
                {"Type": "WFCoercionVariableAggrandizement", "CoercionItemClass": "WFStringContentItem"})
            p["WFConditionalActionString"] = dyn(right)
        self.add("conditional", **p)
        self.blocks.append(("conditional", group))
        yield
        self.blocks.pop()
        self.add("conditional", GroupingIdentifier=group, WFControlFlowMode=2)

    def otherwise(self):
        action, group = self.blocks[-1]
        assert action == "conditional"
        self.add(action, GroupingIdentifier=group, WFControlFlowMode=1)

    @contextmanager
    def each(self, value, var):
        # Use the same indexed iteration pattern as the supplied Quick Call Image.
        # Apple's numbered Repeat Index variables are not lexical "nearest loop" aliases.
        items_name = f"LoopItems_{len(self.actions)}"
        self.set(items_name, value)
        count = self.count(ref(items_name))
        with self.repeat(count):
            self.set(var, self.item(ref(items_name), ref("Repeat Index")))
            yield

    @contextmanager
    def repeat(self, count):
        group = uid(f"repeat:{len(self.actions)}")
        self.add("repeat.count", WFRepeatCount=count, GroupingIdentifier=group, WFControlFlowMode=0)
        self.loop_depth += 1
        self.blocks.append(("repeat.count", group))
        yield
        self.blocks.pop()
        self.loop_depth -= 1
        self.add("repeat.count", GroupingIdentifier=group, WFControlFlowMode=2)

    @contextmanager
    def menu(self, prompt, items):
        group = uid(f"menu:{len(self.actions)}")
        self.add("choosefrommenu", WFControlFlowMode=0, GroupingIdentifier=group,
                 WFMenuPrompt=dyn(prompt), WFMenuItems=items)
        self.blocks.append(("choosefrommenu", group))
        yield
        self.blocks.pop()
        self.add("choosefrommenu", WFControlFlowMode=2, GroupingIdentifier=group)

    def case(self, title):
        action, group = self.blocks[-1]
        assert action == "choosefrommenu"
        self.add(action, GroupingIdentifier=group, WFControlFlowMode=1, WFMenuItemTitle=title)

    @contextmanager
    def route(self, name):
        self.sections[name] = len(self.actions)
        with self.if_(ref("Route"), "eq", name):
            yield

    def go(self, route):
        self.set("Route", route)

    def load(self, folder, path, var=None):
        r = self.add("documentpicker.open", WFFile=folder, WFGetFilePath=dyn(path),
                     WFFileErrorIfNotFound=False, WFGetFolderContents=False)
        return self.set(var, r) if var else r

    def save(self, value, folder, filename, var=None, overwrite=True):
        named = self.add("setitemname", WFInput=value, WFName=dyn(filename), WFDontIncludeFileExtension=False)
        r = self.add("documentpicker.save", WFInput=named, WFFolder=folder,
                     WFFileDestinationPath=dyn(filename), WFAskWhereToSave=False, WFSaveFileOverwrite=overwrite)
        return self.set(var, r) if var else r


def storage(b):
    """Both shortcuts resolve the same portable iCloud container themselves."""
    portable = json.loads((Path(__file__).parent / 'source_folder.json').read_text())
    b.set("StorageRoot", b.add("file", WFFile=portable))
    b.set("AppFolder", b.add("file.createfolder", WFFolder=ref("StorageRoot"), WFFilePath="SenTechTips_AnhDonHang"))
    b.set("ImagesFolder", b.add("file.createfolder", WFFolder=ref("AppFolder"), WFFilePath="Ảnh Đơn Hàng"))
    b.set("IncomingFolder", b.add("file.createfolder", WFFolder=ref("AppFolder"), WFFilePath="Đơn mới"))


def current_time(b):
    b.date()
    b.fmtdate(ref("Now"), "yyyy-MM-dd'T'HH:mm:ssXXX", "NowISO")
    b.fmtdate(ref("Now"), "yyyy-MM", "CurrentMonth")
    b.fmtdate(ref("Now"), "yyyyMMdd-HHmmssSSS", "ReportStamp")


