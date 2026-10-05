"use client";
import { useEffect, useState } from "react";
import { useAuth, useActiveView, LoginRequired, API_BASE } from "./auth";
import type { FortuneSaved } from "./fortune-state";
import "./report-export.css";


export function ReportExport({ saved }: { saved: FortuneSaved }) {
  const { user } = useAuth();
  const isActive = useActiveView();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<"excel" | "pdf" | null>(null);
  const [error, setError] = useState("");
  const [pdfAvailable, setPdfAvailable] = useState<boolean | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setPdfAvailable(null);
    if (user) {
      void fetch(API_BASE + "/api/export-capabilities", { credentials: "same-origin", cache: "no-store", signal: controller.signal })
        .then(async response => {
          const body = await response.json();
          if (!controller.signal.aborted) setPdfAvailable(response.ok && body.ok === true && body.data?.pdf_available === true);
        })
        .catch(() => { if (!controller.signal.aborted) setPdfAvailable(false); });
    }
    return () => controller.abort();
  }, [user?.id]);
  async function download(format: "excel" | "pdf") {
    if (format === "pdf" && pdfAvailable !== true) return;
    setBusy(format); setError("");
    const label = format === "excel" ? "Excel" : "PDF";
    try {
      const source = saved.history ? { reading_id: saved.history.id } : { export_token: saved.result.excel_export_token };
      if (!saved.history && !saved.result.excel_export_token) {
        throw new Error("出力元の鑑定結果を取得できません。保存済み履歴から出力するか、再度鑑定してください。");
      }
      const response = await fetch(API_BASE + "/api/export/" + format, {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(source), cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || label + "の出力に失敗しました。");
      }
      const header = response.headers.get("Content-Disposition") ?? "";
      const name = header.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const blob = await response.blob();
      if (!isActive()) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = name ? decodeURIComponent(name) : "鑑定書." + (format === "excel" ? "xlsx" : "pdf");
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setOpen(false);
    } catch (caught) { setError(caught instanceof Error ? caught.message : label + "の出力に失敗しました。"); }
    finally { setBusy(null); }
  }
  if (!user) return <LoginRequired />;
  return <div className="reportExport">
    <button type="button" disabled={busy !== null} aria-expanded={open} onClick={() => setOpen(!open)}>鑑定書を出力</button>
    {open ? <div className="reportExportOptions" role="group" aria-label="鑑定書の出力形式">
      <button type="button" disabled={busy !== null} onClick={() => download("excel")}>{busy === "excel" ? "出力中…" : "Excelで出力"}</button>
      <button type="button" disabled={busy !== null || pdfAvailable !== true} onClick={() => download("pdf")}>{pdfAvailable === null ? "PDF（利用可否を確認中…）" : !pdfAvailable ? "PDF（現在利用できません）" : busy === "pdf" ? "出力中…" : "PDFで出力"}</button>
      {pdfAvailable === false ? <span>現在はExcelで出力してください。</span> : null}
    </div> : null}
    {error ? <p role="alert">{error}</p> : null}
  </div>;
}
