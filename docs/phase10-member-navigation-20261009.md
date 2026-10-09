# Phase 10 会員画面の遷移改善・回帰記録（2026-10-09）

## 実装範囲と開始状態

正規W（Next.js＋Python API）のログイン後の入口、ログアウト後の移動先、既存会員画面の鑑定開始導線を変更した。Phase 10全体の完了・本人受入・本番配備承認とは別工程。

- 正規Repository: C:\Users\bunch\Documents\Codex\fortune-app-public
- 開始branch: phase10-regression-20261009
- 開始HEAD: 29e68528694ab37785bd6aa4537ecc7495e095ee
- 開始working tree: clean。origin同branchと一致し、新branchが未存在であることを確認。
- 新branch: phase10-member-navigation-20261009。main・既存branchを上書きしない。
- global AGENTS.md v1.3を最上位共有規則として、開発元AGENTS、親WORKSPACE_RULES、既存引継ぎ、Phase 10計画/回帰記録、Phase 9最終保持記録、既存API/テストを参照。public固有AGENTSはない。
- Notion商品版ロードマップを読み取り参照。進捗は最新Gitより古く、最新本人指示を実行根拠とした。Notion書込みなし。今回の明示的な実装・新branch・commit/pushの許可により、追加の規則競合はない。
- 以前の本人確認サーバーは停止済み。今回の試験は各runnerが作った新規隔離DBと所有localhostサーバーのみ。

## 変更ファイル

|ファイル|変更内容|
|---|---|
|fortune-next-app/app/auth.tsx|既存session失効を維持し、成功時の状態消去・ログイン画面への移動・ページ退避時の認証済みDOM消去|
|fortune-next-app/app/login/page.tsx|認可確認済みの役割別入口/nextへ移動、遅延した遷移の本人ID確認|
|fortune-next-app/app/member-navigation.ts|既存認証済みAPIによる入口選択・内部route許可リスト・個別認可確認|
|fortune-next-app/app/member-start.tsx|本人の所属と既存me APIに基づく鑑定開始導線|
|fortune-next-app/app/mypage/page.tsx|上部に開始導線、既存件数・履歴・契約・設定を再利用|
|fortune-next-app/app/teacher/[organizationId]/page.tsx|認可確認できた教室の開始導線を上部へ追加|
|fortune-next-app/app/operations/operations-view.tsx|本人用導線/件数を追加、Org一覧からB2B権限を付与しない|
|fortune-next-app/app/management.css|既存色を使う開始パネル/44px以上の操作領域/キーボードfocus|
|tests/member_navigation.test.mjs|新規38件: 役割・曖昧所属・情報不足・許可/拒否next|
|tests/member_navigation_ui.cjs|新規の実API・合成User・隔離DBによるPC/スマホ幅の遷移試験|
|tests/auth_ui.cjs|今回確定したmypage/loginの期待遷移へ更新、既存認証/所有者隔離/出力判定を維持|
|tests/final_retention_ui.cjs|追加された本人summary取得用の正規形mockを補う|
|tests/phase10_local_ui.cjs|準備する合成履歴に通常画面保存時のmanualChoices/boundarySelectionsを含める|
|tests/README.md|追加試験の実行方法と隔離範囲|
|本記録|実装・検証・本人再確認・残事項|

## ログイン後の仕様

|条件|通常ログイン先|
|---|---|
|B2C利用者・生徒|/mypage|
|所属が1つで先生、既存teacher APIで利用権限確認成功|/teacher/[organizationId]|
|複数所属（先生複数、先生と別Org生徒等）|/mypage、名称付きで本人が選択|
|運営管理者（authenticated summaryのis_operator=true）|/operations|
|役割情報不足、取得失敗、先生利用権限確認失敗|/mypage|

既存User/sessionを使用。役割は /api/account/summary、所属利用権限は既存 /api/b2b/organizations/[id]/me または /teacher から取得する。URLだけで役割を判断しない。

nextは既存の内部routeを許可する。/、/mypage、本人履歴一覧/復旧一覧は認証成功後の本人用/public画面。履歴詳細は /api/history/[id]、B2Bは /me、先生は /teacher、運営一覧/Org詳細/User詳細は対応する既存運営APIで200取得できた場合だけ移動。拒否時は認可済みの通常入口へ戻る。外部URL、//、逆斜線、encoded slash、path traversal、未許可route/query/hashを拒否。既存server-side認可が最終判定を維持する。

認証状態の切替後はwindow.location.replaceで認可確認済みの画面を読み込む。成功した本人IDが現在も一致する場合だけ遷移する。ログイン失敗はフォームに留まり、エラー表示・password消去を維持する。

## ログアウト後の仕様

- /api/auth/logout成功後だけ、認証・保存結果・再鑑定draft・入力画面状態を消去し、/loginへ移動する。
- flushSyncで認証済みDOMの消去を反映してから新しいdocumentを読み込み、Next.jsのクライアント保持状態を破棄する。
- pagehideで未完了の認証再確認応答を無効化し、認証済みDOM/React状態を消去してからブラウザの戻る/進むキャッシュへ退避。pageshow/focusの既存認証再確認、保護画面の既存guard、遅延応答の既存無効化を維持。
- failure時はエラー表示し、成功扱いの移動や先行session/入力消去はしない。server-side session失効処理は変更していない。

## 開始ボタンの条件と画面

- マイページ上部: 本人の所属名＋「先生版」と、それぞれの「鑑定を始める」。me API確認中は待機、休止/初期入金未確認/権限不足/取得失敗ではB2B開始操作を表示しない。
- 複数Orgは名称とaria-labelを区別し、選択案内を表示。既存の先生管理/生徒利用契約の画面を再利用。
- 通常B2Cは「通常鑑定（博士の占い）」と区別して既存 / へ案内。B2B契約休止の判定はOrg単位で維持し、既存B2Cの匿名利用や特定日時を占う仕様を変えない。
- 先生画面: 既存teacher APIの認可成功時のみ、当該OrgのB2B開始操作を上部表示。教室全体の件数・生徒氏名/状態だけという既存表示を維持。
- 運営画面: 自分のsummary/所属だけで開始導線と本人件数を表示。運営が管理できるOrg一覧を本人のB2B所属に転用しない。所属なし運営には通常B2C/自分の履歴だけ。
- 320pxの運営一覧で全角空白を含む行の折り返しが326pxのscroll幅を作ることを実測し、管理一覧のline-break:anywhereだけで320pxへ収めた。フォーム幅の変更では解消しないこともブラウザ内で比較した。既存色・幅・フォントを維持。開始リンクは44px以上、focus-visible枠とEnter操作、折り返しを確認。

## 試験と結果

|試験群|最終結果|条件/数え方|
|---|---|---|
|Python全 *cases.py|466/466 PASS|349.632秒、failure/error/skipなし、既存正式期待値は変更なし|
|Tier A|556/556 PASS|32件のK01/K03は全cases側と重複|
|Tier B固有|38/38一致、REVIEW 0|観測総数1138のうち残り1100はS比較|
|S参照比較|14関数・1100入力一致|S読み取りのみ、W/Sの実行中source hash変化0|
|テストharness|16/16 PASS|検査基盤|
|Node|51/51 PASS|既存13＋新規38、skipなし|
|追加実ナビゲーションUI|156/156 PASS|1280/390/320 ×52条件、実認証/認可、pageerror 0|
|既存認証UI/E2E|34/34 PASS|PC/375、session/所有者隔離/実Excel/PDF|
|履歴UI|28シナリオ PASS|PC/375、検索/保存/メモ/再鑑定/削除|
|節入り・再鑑定UI|1 suite PASS|出生選択維持/鑑定年選択消去/新鑑定年|
|実鑑定書UI|12/12 PASS|PC/375、保存前後Excel/PDF・障害回復、実Windows Excel変換|
|K01/K03 UI|48/48 PASS|2026/2027、B2C/B2B/履歴/既存試作画面|
|五行A/B/C UI|81/81 PASS|1280/390/320、通常/不能/境界前後|
|契約・保持UI|18/18 PASS|PC/375、既存ゲート/契約単位の操作|
|先生・運営管理UI|50/50 PASS|PC/375、権限/表示項目/既存管理|
|password再設定UI|20/20 PASS|PC/375、秘密値非露出/エラー/完了|
|履歴復旧UI|16/16 PASS|PC/375|
|最終保持UI|12/12 PASS|PC/375、ドライラン/再契約/運営制限|
|TypeScript|PASS|tsc --noEmit --incremental false|
|production build|PASS|既存Next.js、静的13ページ生成、依存追加なし|

UI総計475項目/シナリオ＋境界1 suite PASS。単位の違うsuiteを項目へ水増ししない。Pythonは32件の重複を除くと1044件（466＋556＋38＋16－32）、S比較1100入力は別枠。失敗注入用のPythonログ、既存Nodeのmodule種別警告は試験成功と区別する。

履歴復旧UIの再実行中に1回、localhost frontend準備待ちのassert(ready)で終了した。同じ検証内容を再実行して16/16 PASSし、最終保持12/12もPASS。期待値の緩和や依存変更は行っていない。最終buildで既存認証・履歴・実出力・追加ナビゲーション・K01/K03・五行を検査した。PCの複数所属/先生、390px複数所属、320px運営の合成スクリーンショットも目視確認した。

API/DB試験は新規tempDBまたはmemory DB、UIは合成User/Orgのみ。APIログ/秘密値・実個人情報を成果物/Git/Notionへ記録しない。実SMTP/課金、既存DB変更、VPS、本番配備/削除/backup操作なし。

追加UI試験は幅1280/390/320で、匿名B2C/保護画面、B2C/生徒/先生/複数先生/先生と別Org生徒/運営/契約休止/初期入金未確認/アカウント停止、正当/不正/権限外next、ログイン失敗、ログアウト成功/失敗、session失効、Back、入力消去、pagehide/pageshow（合成のpersistedイベント）、遅延login判定/所属応答を検査。所属なしは既存ProductRepository.context・正式product_api_casesに従い404、所属内の役割/契約不許可は403で拒否する。新規試験の仮置き403は既存404契約へ訂正した。既存認可や正式期待値を弱めていない。

試験途中の履歴詳細の画面例外は、合成履歴fixtureで通常UI保存に含まれるmanualChoicesを省略したため。認証APIは200で、ResultViewのObject.entriesへundefinedが渡った。準備fixtureへ既存UI保存の補助項目を加えて再試験。読み込み未完了の早期判定とNext.jsの読み上げ用alertとの混同も試験側で修正。通常UI生成履歴の構造・本体計算・正式文章の変更なし。

## 既存機能と保持対象の不変

/、main-fortune、占術Python、正式解釈文、backend認証/認可、履歴schema、Excel/PDF template/converter、依存関係、S/Dは変更していない。保存/再鑑定/メモ、本人件数、先生/運営権限、K01/K03、五行A/B/C、鑑定書は既存正式試験で検査。

既存ローカル data/history.sqlite3 のSHA256は開始/終了とも
9faacb971b429179eba95083a32b81f2c8f7321bb1e538b47665e9b3055d3da1。
migration/補完/削除は実行していない。

## 本人再確認とPhase 10残事項

1. 各役割でログインし、指定入口・所属選択・利用状況が分かりやすいか。
2. 「鑑定を始める」で通常B2C/所属先生版を混同せず進めるか。
3. ログアウトでloginへ戻り、Backしても自分の情報が再表示されないか。
4. PC/実スマホで操作しやすさ、メモ、2026/未登録2027、完成Excel/PDFを本人が確認する。

以前の停止済み受入用tempDB（fortune-phase10-local-oZwhRc）をimmutable/read-onlyで項目有無だけ確認したところ、4履歴すべてmanualChoicesを省略していた。既存DB/4履歴には手を加えていない。この旧合成履歴の直接再表示には既存の表示制約が残る。次の受入準備では修正版の準備スクリプトで新規隔離環境を作るか、別途本人指示で旧テスト履歴の補完を検討する。通常UI保存履歴・権限判定とは切り分ける。

Phase 10全体・本人受入は未完了。実スマホ実機、Linux PDF/本番設定/外部backup等、K02/K04/K05/K06、B2B特定日時の仕様保留、B2C終了保持/購入者メール変更本人確認/会計保持の未確定事項は従来の別工程。今回から新仕様を推測確定しない。本番配備承認も別工程。

## 終了とGit確認

全runner終了後、今回のテストport 3000/8765/3109/3110/3112/3113/3114/3115/3116にlistenerがないことを確認。今回起動したサーバーだけ終了。他のサービスは操作していない。

commit前に今回の15ファイルの差分・diff --checkを確認し、指定branchへ1 commitしてoriginへpushする。開始branchのlocal/originは29e68528694ab37785bd6aa4537ecc7495e095ee、origin/mainはe8b53082775744a74f66502e8fb8f3cef72974c1のままであることを確認。commit後のHEAD・clean・origin一致は最終報告で通知する。main merge・既存branch更新・履歴書換え・本番操作なし。
