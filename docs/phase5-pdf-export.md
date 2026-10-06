# Phase 5 鑑定書PDF出力

2026-10-06：本番配備完了。Ubuntuは `FORTUNE_PDF_CONVERTER=disabled` を正式仕様とし、UI「PDF（現在利用できません）」、認証済み直接API503 / converter_unavailableを本番で確認済み。Excelは利用可能。現在状態は [配備完了記録](vps-deployment.md#15-phase-7a本番配備完了の最終記録2026-10-06) を参照。

## 出力経路

結果画面と履歴詳細の「鑑定書を出力」でExcel／PDFを選択する。
`POST /api/export/pdf` の入力は既存Excel APIと同じ `export_token` または `reading_id` の一方だけ。

`report_pdf.export_pdf_reading` → 既存 `report_export_service.export_reading` → 完成XLSX → `PdfConverter.convert` → PDF。
顧客向けデータ選択、命名、テンプレート、セル／図形／グラフ配置は既存Excel処理を使用する。
PDF側には鑑定データの再計算や配置定義を持たない。

未保存結果はサーバー側の正式結果コピー、保存済み結果はownerスコープの当時のsnapshotを使う。
メモ、privateコメント、内部ID／version等は既存Excelデータ層で除外した後に変換する。
レスポンスは `application/pdf`、attachmentのUTF-8ファイル名、`no-store`、`nosniff`。

## 変換エンジン

`pdf_converter.PdfConverter` は完成XLSXのbytesを受け取りPDFのbytesを返す共通interface。
`WindowsExcelPdfConverter` と `UnavailablePdfConverter` を分離し、module import時にはWindows APIやCOMを必要としない。
将来Linux用adapterを追加する際はこのinterfaceとfactoryの選択肢を拡張する。UI／API／Excel配置はそのまま使用できる。

Windowsの `FORTUNE_ENV=development` では既定値が `windows_excel`。
`FORTUNE_PDF_CONVERTER=disabled` で無効化、`windows_excel` で明示選択できる。
それ以外の環境では既定で無効。非WindowsでWindows adapterを選んでも制御された503を返す。
Excel出力とサーバー起動には影響しない。

## Windows adapterと一時ファイル

既にインストール済みのMicrosoft ExcelをレジストリのApp Pathsで特定する。
PowerShell workerが `/x /r` で別のExcel instanceを起動し、読み取り専用の完成XLSXを開く。
起動PIDに属するウィンドウからCOMを取得し、原本シートの既存印刷設定で `ExportAsFixedFormat` を実行する。
XLSXは上書き保存しない。追加Python依存やOfficeのインストールは不要。

OS tempの `TemporaryDirectory` に衝突しないディレクトリを作り、汎用名 `report.xlsx`／`report.pdf` とプロセス識別情報だけを置く。
APIプロセス内のlockでExcel変換を直列化し、待機90秒、worker90秒、終了処理15秒を上限とする。
成功／変換失敗／timeoutとも `finally` で今回のExcelを終了し、ディレクトリを削除する。
PID・起動時刻・実行ファイルを照合する専用cleanupを使い、利用者が開いているExcelをprocess名で一括終了しない。
APIプロセス自体の強制終了やOS障害は通常のfinally保証外。常駐本番方式では監視・回収の設計が必要。

## エラー

Excel生成拒否、利用不能、起動失敗、COM接続失敗、変換失敗、timeout、ファイル不存在、不正PDF、cleanup失敗を区別する。
timeoutは504、利用不能／起動・cleanup失敗等は503、変換失敗等は500。
owner分離、削除済み拒否、入力の限定はExcelと共通。
利用者には日本語の固定エラーとcodeを返し、内部パスやtracebackは返さない。サーバーログに診断を残す。

## 検証

- `python -B tests/report_pdf_cases.py`：PDF API、名前／内容一致、owner／削除済み、当時snapshot、内部情報除外、変換成功・失敗・timeout・cleanup、非Windows。
- `python -B tests/report_export_cases.py`、`tests/history_cases.py`、`tests/check.py`：既存回帰。
- `tests/report_export_ui.cjs`：専用一時履歴DBとWindows converterを設定したAPI／UIで実行。PC 1280px／スマホ375pxで、未保存・保存済みのExcel／PDFダウンロード、再計算なし、各形式の失敗復帰、横幅を検証。
- 実API経由のExcel／PDFの同一内容、Excel本体の読み取り専用検証と同解像度PDF比較、A4縦2ページ・全コメント・5グラフ・下枠を確認する。

## 本番Linuxで残る作業

今回のWindows adapterは開発環境用。本番Linux用adapterの実装は未実施。
LibreOffice等の再現性、フォント、timeout、同時実行上限、temp領域、プロセス監視、配備方式を確定する。
Gotenbergは変換エンジンそのものではなくLibreOffice等を呼ぶサービスとして検討する。
本番認証はPhase 7Aで実装・配備済み。複数worker時の未保存トークン共有保持先は未実装の後続工程で、当面1 worker。開発owner設定は本番認証の代用にしない。
Phase 5 PDF実装当時はVPS変更を行わなかったが、その後2026-10-06に正式配備済み。Linux converterは未構築であり、disabled運用は配備失敗・blockerではない。
