"use client";
import { useState } from "react";
import type { FortuneSaved } from "./fortune-state";
import "./report-export.css";

const API_BASE = (process.env.NEXT_PUBLIC_FORTUNE_API_URL ?? "").replace(/\/+$/, "");

export function ReportExport({ saved }: { saved: FortuneSaved }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function downloadExcel() {
    setBusy(true); setError("");
    try {
      const source = saved.history ? { reading_id: saved.history.id } : { export_token: saved.result.excel_export_token };
      if (!saved.history && !saved.result.excel_export_token) {
        throw new Error("出力元の鑑定結果を取得できません。保存済み履歴から出力するか、再度鑑定してください。");
      }
      const response = await fetch(API_BASE + "/api/export/excel", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(source), cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.error || "Excelの出力に失敗しました。");
      }
      const header = response.headers.get("Content-Disposition") ?? "";
      const name = header.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = name ? decodeURIComponent(name) : "鑑定書.xlsx";
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setOpen(false);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Excelの出力に失敗しました。"); }
    finally { setBusy(false); }
  }
  return <div className="reportExport">
    <button type="button" disabled={busy} aria-expanded={open} onClick={() => setOpen(!open)}>鑑定書を出力</button>
    {open ? <div className="reportExportOptions" role="group" aria-label="鑑定書の出力形式">
      <button type="button" disabled={busy} onClick={downloadExcel}>{busy ? "出力中…" : "Excelで出力"}</button>
    </div> : null}
    {error ? <p role="alert">{error}</p> : null}
  </div>;
}
