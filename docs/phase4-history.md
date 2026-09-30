# Phase 4 鑑定履歴（ローカル開発）

## 起動
既存のPython仮想環境を使い、fortune-next-app/backend/start-local.ps1でAPIを起動する。
フロントエンドはfortune-next-appでnpm run dev。アクセスは http://127.0.0.1:3000/ 。

履歴APIはFORTUNE_ENV=developmentとFORTUNE_HISTORY_DEV_USER_IDの両方が明示設定された場合だけ有効。
start-local.ps1はローカル専用（127.0.0.1）。本番ではこのスクリプトを使わない。
設定がない場合／FORTUNE_ENV=productionの場合は履歴APIが503を返す。
鑑定計算APIはその場合も従来どおり利用可能。
Phase 7で本番認証を実装するまで、本番へ履歴機能を配備しない。

## 保存と差し替え境界
- history_repository.py: SQLiteHistoryRepository。SQL、トランザクション、ownerスコープ。
- history_service.py: HistoryService。保存の検証、再鑑定の準備、人物とグループの扱い。
- fortune-next-app/backend/history_api.py: 計算APIとは別の履歴ルート。利用者IDをサーバー側で解決。
- history_versions.py: 保存時のアプリ／計算／スキーマバージョン。
将来はmake_serviceのrepository adapterとdevelopment_ownerを認証側resolverに交換する。
クライアントのuser_id／owner_user_idは認証として使わない。

既定のDBは正本のdata/history.sqlite3。FORTUNE_HISTORY_DB_PATHで変更可能。
data/、SQLiteファイル、journalはGitから除外する。新しい空DBには必要なテーブルを作成する。
既存の本番データ移行・スキーマの破壊的変更・物理削除処理は含まない。

## データとスナップショット
persons: owner、姓・名・せい・めい、NFKC正規化名、生年月日、現在入力JSON、作成・更新日時。
reading_groups: owner、人物ID、グループID、作成日時。
readings: owner、人物・グループ・履歴ID、再鑑定元ID、鑑定日、保存・更新・削除日時、
各回メモ、入力JSON、完全結果JSON、3種類のバージョン。
ownerを含む複合外部キーで異なる利用者の人物・グループへ紐付かないようにする。

入力JSONはform、手動補正の採用判定manualChoices、正式なboundarySelectionsを保持。
結果JSONは計算APIの全返却内容を保存し、コメント・図の点数・順序・年干支等を保持。
画面で組み立てた基本情報表と人生段階名もdisplay_snapshotに保存。
他の表示加工（点数の小数丸め、節入り時刻の表示、季節名、見出し）は保存済み値の表示整形のみであり、
計算APIを呼び出す必要はない。過去の氏名や出生情報もpersonの現在情報から作り直さない。
メモ更新ではmemoとupdated_atだけを更新。input/result/saved_atは固定。

候補は姓と名の両方が入力された場合だけ、正規化姓＋名＋生年月日で検索。
同じ条件でも自動統合せず利用者が人物とグループを選ぶ。未保存の新人物／新グループのIDは初回保存時に発行。
過去メモは同グループから参照し、新しい履歴のmemoへコピーしない。
再鑑定ではpersonの現在情報を使用し、JST当日を鑑定日の初期値とする。
出生日時の補正だけを引き継ぐ。出生条件を編集した場合はその補正を解除して正式フローへ戻る。

## API
GET/POST /api/history: 一覧／保存。keyword、start、endで検索。保存日時の降順。
POST /api/history/candidates: 候補検索。
GET /api/history/groups/{group_id}/memos: 同グループのメモ。
POST /api/history/persons/{person_id}: 現在人物情報更新（専用台帳画面は未実装）。
GET /api/history/{id}: 保存済み詳細。結果の再計算なし。
PATCH /api/history/{id}/memo: メモ明示保存。updated_atが競合する場合は409。
DELETE /api/history/{id}: soft delete。
POST /api/history/{id}/rerun: existing_group / new_groupの再鑑定準備。

## 確認とテスト
Python: .venv/Scripts/python.exe tests/history_cases.py
標準回帰: .venv/Scripts/python.exe tests/check.py
商品化回帰: .venv/Scripts/python.exe tests/product_ui_cases.py
検出器: .venv/Scripts/python.exe tests/test_harness.py
Frontend: node --test tests/jst_default_date.test.mjs
TypeScript: fortune-next-appでnode node_modules/typescript/bin/tsc --noEmit --incremental false
Build: fortune-next-appでnpm run build

tests/history_ui_smoke.cjsはデータを作成・論理削除するため、必ず一時DBに向けたローカルAPIで実行する。
FORTUNE_HISTORY_DB_PATHに本番／利用者のDBを設定して実行しない。
既存PlaywrightとEdgeを使用（新規インストールなし）。PLAYWRIGHT_MODULEに既存モジュールを指定可能。
FORTUNE_UI_URLは既定 http://127.0.0.1:3000 。
PC1280px／スマホ375pxで新規、保存、詳細（計算API呼出なし）、メモ、2種類の再鑑定、
複数人物候補、検索、削除キャンセル／実行、元スナップショット不変を確認。

## 残件
本番認証と本番マルチユーザー分離、クラウドDB選定、バックアップ、30日後の物理削除はPhase 7以降。
VPS配備、Excel/PDF出力、「特定日時を占う」物理削除は今回対象外。

補正・無記名の実画面テスト: tests/history_boundary_ui.cjs（同じ一時DB運用）。
