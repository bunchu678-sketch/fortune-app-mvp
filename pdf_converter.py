"""Replaceable completed-XLSX -> PDF adapter. No Windows dependencies at import time."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from typing import Protocol

logger = logging.getLogger(__name__)
RESOURCES = Path(__file__).parent / "adapters"
_excel_gate = threading.Lock()


class PdfConversionError(Exception):
    def __init__(self, code, message, status=500):
        super().__init__(message)
        self.code, self.status = code, status


class PdfConverter(Protocol):
    def convert(self, xlsx: bytes) -> bytes: ...


class UnavailablePdfConverter:
    def convert(self, xlsx: bytes) -> bytes:
        raise PdfConversionError("converter_unavailable", "PDF変換を利用できません。Excelで出力してください。", 503)


class WindowsExcelPdfConverter:
    """A bounded, isolated Excel instance; only its recorded PID can be terminated."""
    def __init__(self, timeout=90):
        self.timeout = timeout

    def convert(self, xlsx: bytes) -> bytes:
        if sys.platform != "win32":
            return UnavailablePdfConverter().convert(xlsx)
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        worker, cleanup = RESOURCES / "windows_excel_pdf.ps1", RESOURCES / "stop_owned_excel.ps1"
        if not powershell.is_file() or not worker.is_file() or not cleanup.is_file():
            return UnavailablePdfConverter().convert(xlsx)
        if not _excel_gate.acquire(timeout=self.timeout):
            raise PdfConversionError("converter_busy", "PDF出力が混み合っています。しばらくしてから再度お試しください。", 503)
        try:
            # A unique OS-temp directory is removed after success AND every exception.
            with tempfile.TemporaryDirectory(prefix="fortune-pdf-") as directory:
                root = Path(directory)
                source, target, owner = root / "report.xlsx", root / "report.pdf", root / "owner.json"
                source.write_bytes(xlsx)
                command = [str(powershell), "-NoProfile", "-NonInteractive", "-File", str(worker),
                           "-InputPath", str(source), "-OutputPath", str(target), "-OwnerPath", str(owner)]
                try:
                    try:
                        result = subprocess.run(command, capture_output=True, timeout=self.timeout,
                                                creationflags=subprocess.CREATE_NO_WINDOW)
                    except subprocess.TimeoutExpired as exc:
                        # subprocess.run terminates/reaps only the PowerShell worker; finally reaps its Excel.
                        raise PdfConversionError("conversion_timeout", "PDF出力が時間内に完了しませんでした。再度お試しください。", 504) from exc
                    except OSError as exc:
                        raise PdfConversionError("converter_unavailable", "PDF変換を起動できません。Excelで出力してください。", 503) from exc
                    lines = result.stdout.decode("utf-8", errors="replace").splitlines()
                    records = [line[len("PDF_RESULT="):] for line in lines if line.startswith("PDF_RESULT=")]
                    try:
                        info = json.loads(records[-1]) if records else {}
                    except (ValueError, TypeError):
                        info = {}
                    code = info.get("code", "pdf_generation_failed")
                    if result.returncode != 0 or info.get("ok") is not True:
                        logger.error("Excel PDF worker failed: code=%s exit=%s diagnostics=%s", code,
                                     result.returncode, result.stderr.decode("utf-8", errors="replace")[:2000])
                        messages = {
                            "converter_unavailable": ("PDF変換を利用できません。Excelで出力してください。", 503),
                            "excel_launch_failed": ("PDF変換用のExcelを起動できませんでした。", 503),
                            "com_start_failed": ("PDF変換用のExcelへ接続できませんでした。", 503),
                            "excel_open_failed": ("PDF変換用の鑑定書を開けませんでした。", 500),
                            "output_missing": ("PDFファイルが生成されませんでした。", 500),
                        }
                        message, status = messages.get(code, ("PDFの変換に失敗しました。", 500))
                        raise PdfConversionError(code if code in messages else "pdf_generation_failed", message, status)
                    if not target.is_file():
                        raise PdfConversionError("output_missing", "PDFファイルが生成されませんでした。")
                    pdf = target.read_bytes()
                    if not pdf.startswith(b"%PDF-") or b"%%EOF" not in pdf[-4096:]:
                        raise PdfConversionError("output_invalid", "生成されたPDFを確認できませんでした。")
                    return pdf
                finally:
                    # PID + start time + executable must all match. Never kill Excel by process name.
                    try:
                        subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-File", str(cleanup),
                                        "-OwnerPath", str(owner)], capture_output=True, timeout=15,
                                       creationflags=subprocess.CREATE_NO_WINDOW, check=True)
                    except (OSError, subprocess.SubprocessError) as exc:
                        logger.exception("Owned Excel cleanup failed")
                        raise PdfConversionError("cleanup_failed", "PDF変換の終了処理に失敗しました。", 503) from exc
        except OSError as exc:
            logger.exception("PDF temporary-file operation failed")
            raise PdfConversionError("temporary_file_failed", "PDF出力用の一時領域を利用できません。", 503) from exc
        finally:
            _excel_gate.release()


def get_pdf_converter() -> PdfConverter:
    default = "windows_excel" if sys.platform == "win32" and os.environ.get("FORTUNE_ENV") == "development" else "disabled"
    name = os.environ.get("FORTUNE_PDF_CONVERTER", default)
    if name == "windows_excel": return WindowsExcelPdfConverter()
    if name != "disabled": logger.error("Unsupported PDF converter configuration")
    return UnavailablePdfConverter()
