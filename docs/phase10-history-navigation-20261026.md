# Phase10 履歴の遷移先・先生フッター修正

2026-10-26。対象はアプリW。今回2件の本人受入は未完了。Phase10正式完了・main統合・本番配備は実施していない。

## 開始状態とルール

正規repositoryは`C:\Users\bunch\Documents\Codex\fortune-app-public`。開始branchは`phase10-b2b-overnight-20261023`、HEAD `639be8b2b45444a9b77356c6ff9ceedba8a79c86`、working tree clean。origin追跡branchと一致し、`git ls-remote`でも同HEAD。既存未commit変更なし。

専用branch `phase10-history-navigation-20261026`を639be8bから作成。共通AGENTS v1.3を上位として開発元AGENTSを確認。正規repository内にAGENTSなし。同chatで確認済みのNotion有効原則（W正本・正式占術文の独自改変禁止）を維持し、今回はNotionの追加参照/書込みなし。明示された編集・検証・専用branch commit/push許可を適用し、未解決のルール競合なし。

## 変更ファイルと内容

|ファイル（repository相対）|変更|
|---|---|
|fortune-next-app/app/history/page.tsx|固定`/`リンクを権限確認後のコンポーネントに置換。認証読込中の「通常鑑定へ戻る」も非表示にして誤誘導を防止|
|fortune-next-app/app/history-new-reading.tsx（新規）|本人の認証状態に紐付けて行き先を取得。読込中/取得失敗/運営は開始リンクを出さない。unmount後・logout後の遅延応答を無効化。クリック時の`setDraft(null)`/`setSaved(null)`を維持|
|fortune-next-app/app/member-navigation.ts|既存ルーティングmoduleに鑑定開始専用の行き先判定を追加。ログイン後・ヘッダー用`memberDestination`の挙動は不変|
|fortune-next-app/app/teacher/[organizationId]/page.tsx|末尾の「マイページへ」とそのnavだけを削除。ヘッダー、本人履歴、回数/アカウント、B2B入口、集計、生徒一覧、Powered by等は維持|
|tests/new_reading_navigation.test.mjs（新規）|行き先判定18件。役割、複数所属、停止/未入金/権限外/取得失敗、不正ID、不正応答を検証|
|tests/member_navigation_ui.cjs|既存186確認に履歴遷移と待機/失敗/logout安全性を追加し216確認。先生フッター不在と残す導線も検証。保存画像の認証表示をmask|
|tests/history_ui_smoke.cjs|既存候補選択APIの反映を待つ2行だけ追加。検索/保存/削除等の期待値は変更しない|
|docs/phase10-history-navigation-20261026.md|本記録|

履歴詳細と削除済み履歴も調査した。いずれも戻り先は`/history`で、新規鑑定への固定`/`リンクは存在せず、変更不要と判断。検索・一覧・詳細・memo・削除・復旧・再鑑定の本体処理は変更していない。

## 役割別の動作

正規API `/api/account/summary`を使い、単一所属ではさらに`/api/b2b/organizations/{id}/me`のOrganization一致とteacher/student権限を確認する。IDを固定せず、同じ本人のサーバー応答から決める。

|状態|履歴の「新しく鑑定する」|
|---|---|
|単一所属の生徒|`/b2b/{organizationId}`の先生版鑑定入力へ|
|単一所属の先生|同じく`/b2b/{organizationId}`。`/teacher/{id}`管理画面へは送らない|
|複数所属|`/mypage`の既存所属先選択へ。勝手に一方を選ばない|
|B2C専用|従来の`/`へ|
|運営|開始リンク非表示。既存ヘッダーから運営管理へ|
|休止/未入金/所属権限なし|`/mypage`の安全な既存入口へ。所属先の権限エラーを表示し、B2Cへのfallbackなし|
|本人情報の読込中|開始リンク非表示|
|本人情報取得失敗/不完全|開始リンク非表示。既存ヘッダーのマイページから安全な初期画面へ戻れる|

サーバー側の認可は不変。リンク判定を通った後に権限が変わった場合も、既存B2B APIの認可で保護する。先生による生徒の個別本文・日時・回数非開示、Org分離は維持。

## 検証結果

|検証|最終結果|
|---|---|
|production build（Next16.4.2、通常Turbopack）|成功|
|TypeScript `tsc --noEmit`|成功|
|lock固定offline install|成功、lock変更なし。専用Node24.22.1/pnpm11.7.0のみ使用|
|Node全既存＋追加テスト|69/69 PASS（新規判定18、既存51）|
|実ブラウザー・役割遷移|216/216 PASS。PC1280/スマホ390/320で8状態、ヘッダー、先生フッター/維持リンク、履歴新規遷移、待機/取得失敗/遅延応答を検証|
|Python関連unittest|192/192 PASS（auth44、history32、recovery12、productAPI25、Excel58、PDF21）|
|baseline|Tier A556/556、Tier B38/38一致。source hash149件 changes0。既知Tier C6件は維持|
|既存履歴の実ブラウザー|28シナリオ PASS（PC/スマホ各14）、別途境界1シナリオ PASS|
|帳票実出力/エラー回復|12確認 PASS。Excel実出力4、PDF実出力4（全HTTP200）、意図的503からの回復4|

既存の履歴ブラウザー回帰では、候補の選択API完了前に次の計算を押してtimeoutした。診断時も候補一覧が表示されたままで、非同期選択の反映待ちが不足していた。テストだけに候補欄の非表示待ちを追加し、元の期待値を保って再実行。アプリの候補選択ロジックは変更していない。初回失敗ログは`history-smoke-first-failure.log`に保持。

通常sandboxではPython baselineが無出力のまま300秒timeoutとなった。残存する同検証workerがないことを確認し、同じ専用合成DB条件のまま実行権限を限定して再実行するとbaselineと関連192件は成功した。実行環境Cとして記録し、アプリ不具合や検証成功として初回を数えていない。Nodeの既存MODULE_TYPELESS_PACKAGE_JSON警告はテストを失敗させておらず、無関係なpackage設定変更は行わない。

帳票3件（特殊命式4列表・キーワード本文・五行対称配置）、占術計算/正式文、Python認可・DB schemaには差分なし。総合Phase10全領域の再実行はせず、今回の経路と関連回帰に限定した。

## 本人確認環境

**修正版： http://127.0.0.1:13335/**

旧 `http://127.0.0.1:13325/` は旧buildのまま維持。修正版と取り違えないこと。旧環境や3000/8765を停止・上書きせず、修正版はアプリ13333/API18796/資料13335に分離した。全て127.0.0.1、専用の新規合成DB、mail/PDF converter disabled。実利用者・本番DB不使用。

1. 「生徒の履歴を開く」→「新しく鑑定する」→教室Aの先生版鑑定入力を確認。
2. 「先生の履歴を開く」→同じく鑑定入力へ進むことを確認。
3. 「先生管理画面を開く」→最下部の「マイページへ」がなく、残すべき導線があることを確認。ヘッダーは役割初期画面へ戻る。
4. 必要ならB2C・複数所属・運営の履歴ボタンで、それぞれ通常入力/所属先選択/開始リンク非表示を確認。

パスワード入力は不要。helperがメモリ内の合成認証情報で通常のAPIログインを行い、実アプリを同じ名前の別タブへ開く。password/cookie等をHTML・ログ・Git・スクリーンショットへ保存しない。HTML/画像・合成DB・環境情報は開発元`outputs/phase10-history-navigation-20261026/review/`以下。API/Web停止は本人から終了依頼があった場合に所有PID等を照合して行う。

実際の保存先は`C:\Users\bunch\Documents\Codex\fortune-app\outputs\phase10-history-navigation-20261026\review\session-657ebf2787`。`本人受入確認.html`、`確認資料プレビュー.jpg`、`screenshots/student-history.jpg`、`screenshots/teacher-home.jpg`を保存。Chromeで役割ボタン全6種類の画面表示、生徒/先生の鑑定入力への遷移、ヘッダーからの役割別復帰、複数所属のA/B選択肢2件、B2Cの`/`、運営の開始リンク非表示を確認。運営の見出しは実装どおり「しぜんとらぼ 運営管理」で、名称の変更はしていない。保存画像に認証情報が含まれないことと、確認HTMLの画像2枚が正常に表示されることも目視確認した。

最終待受確認：新環境helper24060/アプリ10404/API22496は全て127.0.0.1。旧13325/13323/18786はPID22024/21240/26212、既存3000/8765はPID7288/12888のまま。環境は本人確認用に起動維持している。

ログ/検証用コピーは開発元`outputs/phase10-history-navigation-20261026/`。補助script/stagingは`research/run_history_navigation_*_20261026.*`と`research/history_navigation_staging`、変更前控えは`_backups/public/history-navigation-20261026`。確認ファイル・DB・依存・ログはGitに追加していない。

## Git・残る事項

- branch：`phase10-history-navigation-20261026`
- 実装修正commit：`ce708be1cbee8bbd07db9441aaa8a3c429b97ad8`
- 本記録は別commitで保存し、専用branchのみoriginへpushする。最終commit・push後の実測は開発元側の本記録に追記する。
- 旧本人確認環境・既存3000/8765は維持。main merge、main push、本番配備/再起動、実DB操作なし。
- 実装修正・関連検証・本人確認環境の未解決事項なし。今回2件の本人最終受入は未実施。Phase10正式完了と扱わない。
