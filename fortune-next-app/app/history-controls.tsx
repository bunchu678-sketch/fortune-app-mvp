"use client";
import Link from "next/link";
import { useAuth, useActiveView, LoginRequired } from "./auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FortuneSaved, useFortuneState } from "./fortune-state";
import { HistoryRecord, RerunDraft, historyRequest, savedTime } from "./history-client";

export function ReadingControls({ saved, onChange }: {
  saved: FortuneSaved; onChange: (value: FortuneSaved) => void;
}) {
  const router = useRouter();
  const { user } = useAuth();
  const isActive = useActiveView();
  const { setDraft } = useFortuneState();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rerun, setRerun] = useState(false);
  const dirty = Boolean(saved.history && (saved.memo ?? "") !== saved.history.memo);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  async function save() {
    setBusy(true); setError("");
    try {
      const record = saved.history
        ? await historyRequest<HistoryRecord>("/" + saved.history.id + "/memo", {
            method: "PATCH", body: JSON.stringify({ memo: saved.memo ?? "", updated_at: saved.history.updated_at }),
          })
        : await historyRequest<HistoryRecord>("", {
            method: "POST", body: JSON.stringify({
              input_snapshot: { form: saved.form, manualChoices: saved.manualChoices,
                boundarySelections: saved.boundarySelections ?? {} },
              ...(saved.organizationId ? { organization_id: saved.organizationId } : {}),
              result_snapshot: saved.result, memo: saved.memo ?? "", ...(saved.link ? { link: saved.link } : {}),
            }),
          });
      if (!isActive()) return;
      onChange({ ...saved, history: record });
    } catch (caught) { setError(caught instanceof Error ? caught.message : "保存に失敗しました。"); }
    finally { setBusy(false); }
  }
  async function prepare(mode: "existing_group" | "new_group") {
    if (!saved.history) return;
    if (dirty && !window.confirm("未保存のメモ変更を破棄して再鑑定を始めますか？")) return;
    setBusy(true); setError("");
    try {
      const draft = await historyRequest<RerunDraft>("/" + saved.history.id + "/rerun", {
        method: "POST", body: JSON.stringify({ mode }),
      });
      if (!isActive()) return;
      setDraft(draft);
      router.push(draft.organizationId ? "/b2b/" + draft.organizationId : saved.organizationId ? "/b2b/" + saved.organizationId : "/");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "再鑑定の準備に失敗しました。"); }
    finally { setBusy(false); }
  }
  if (!user) return <LoginRequired />;
  return <div className="historyControls">
    <p role="status">{dirty ? "未保存の変更あり" : saved.history ? "保存済み　" + savedTime(saved.history.saved_at) : "未保存"}</p>
    {error ? <p role="alert">{error}</p> : null}
    <div className="historyActions">
      <button type="button" disabled={busy || Boolean(saved.history && !dirty)} onClick={save}>
        {busy ? "処理中…" : saved.history ? "メモの変更を保存" : "鑑定結果を保存"}
      </button>
      <Link href="/history" onClick={event => {
        if (dirty && !window.confirm("未保存のメモ変更を破棄して履歴一覧へ移動しますか？")) event.preventDefault();
      }}>鑑定履歴</Link>
      {saved.history ? <button type="button" disabled={busy} onClick={() => setRerun(!rerun)}>この人を再鑑定</button> : null}
    </div>
    {rerun ? <div className="historyChoice" role="group" aria-label="再鑑定方法">
      <button type="button" disabled={busy} onClick={() => prepare("existing_group")}>過去履歴を引き継いで再鑑定</button>
      <button type="button" disabled={busy} onClick={() => prepare("new_group")}>過去履歴を引き継がず新規鑑定</button>
      <button type="button" onClick={() => setRerun(false)}>キャンセル</button>
    </div> : null}
  </div>;
}
