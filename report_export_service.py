"""Owner-scoped, short-lived references to server-calculated readings."""
from collections import OrderedDict
from copy import deepcopy
import secrets
import threading
import time
from report_data import build_reading_report, ReportError
from report_xlsx import render_xlsx
from reading_snapshot import public_result_snapshot


class ExportTokens:
    def __init__(self, ttl=3600, capacity=256, clock=time.monotonic):
        self.ttl,self.capacity,self.clock=ttl,capacity,clock
        self.entries=OrderedDict()
        self.lock=threading.Lock()

    def _expire(self):
        now=self.clock()
        for token,entry in list(self.entries.items()):
            if entry[0]<=now:self.entries.pop(token)

    def issue(self, owner, form, result, session_id=None):
        with self.lock:
            self._expire()
            token=secrets.token_urlsafe(32)
            self.entries[token]=(self.clock()+self.ttl,owner,deepcopy(form),public_result_snapshot(result),session_id)
            while len(self.entries)>self.capacity:self.entries.popitem(last=False)
            return token

    def get(self, owner, token, session_id=None):
        with self.lock:
            self._expire()
            entry=self.entries.get(token)
            if not entry or entry[1]!=owner or entry[4]!=session_id:
                raise ReportError("出力元の鑑定結果を取得できません。保存済み履歴から出力するか、再度鑑定してください。",404)
            return deepcopy(entry[2]),deepcopy(entry[3])


export_tokens=ExportTokens()


def export_reading(owner, payload, repository=None, tokens=export_tokens, session_id=None):
    if not owner or not isinstance(payload,dict) or set(payload) not in ({"reading_id"},{"export_token"}):
        raise ReportError("出力元の鑑定を指定してください。")
    key=next(iter(payload));value=payload[key]
    if not isinstance(value,str) or not value or len(value)>200:
        raise ReportError("出力元の指定が不正です。")
    if key=="reading_id":
        if repository is None:raise ReportError("履歴の保存先を利用できません。",503)
        # Repository detail excludes deleted readings and enforces owner in its SQL query.
        reading=repository.detail(owner,value)
        form,result=reading["input_snapshot"]["form"],reading["result_snapshot"]
    else:
        form,result=tokens.get(owner,value,session_id)
    report=build_reading_report(form,result)
    return report.filename,render_xlsx(report)
