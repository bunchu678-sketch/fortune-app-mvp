"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { HistoryRecord, historyRequest } from "../../history-client";
import { FortuneSaved } from "../../fortune-state";
import { ReadingPage } from "../../main-fortune";

export default function HistoryDetail({ params }: { params: Promise<{ historyId: string }> }) {
  const { historyId } = use(params);
  const [saved, setSaved] = useState<FortuneSaved | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setSaved(null); setError("");
    historyRequest<HistoryRecord>("/" + historyId).then(record => {
      if (!active) return;
      setSaved({ result: record.result_snapshot, form: record.input_snapshot.form,
        manualChoices: record.input_snapshot.manualChoices,
        boundarySelections: record.input_snapshot.boundarySelections,
        memo: record.memo, pastMemos: record.past_memos ?? [], history: record });
    }).catch(caught => { if (active) setError(caught.message); });
    return () => { active = false; };
  }, [historyId]);
  if (error) return <main className="appShell"><p role="alert">{error}</p><Link href="/history">鑑定履歴へ戻る</Link></main>;
  if (!saved) return <main className="appShell"><p role="status">履歴を読み込み中…</p></main>;
  return <ReadingPage saved={saved} onChange={setSaved} />;
}
