# fortune-app 夜間作業総合報告（2026-10-23指示）

検証開始は2026-10-24 JST、作業再開・最終整理は2026-10-26 JST。対象はアプリW。**Phase 10の正式完了・main統合・本番B2B配備は本人承認待ち**であり、自動テスト成功だけで完了にしていない。

## A. 全体概要・開始状態

正規Git repositoryは`C:\Users\bunch\Documents\Codex\fortune-app-public`、開発元は`C:\Users\bunch\Documents\Codex\fortune-app`。originは`https://github.com/bunchu678-sketch/fortune-app-mvp.git`。

開始時は`phase10-gogyo-symmetry-20261023`、HEAD `81d1cef6cfc0ebcd07a48267031108443d8f940f`、working tree clean、originの同branchと一致。`03ac311`を祖先として、受入済みの特殊命式4列表`95d6430`、キーワード本文配置`3aed9c2`、五行図対称配置`81d1cef`を継承することを確認して専用branchを作成した。

再開時も`phase10-b2b-overnight-20261023`／81d1cef上に前回の作業差分だけが残っていた。破棄・強制更新・main切替なし。

完了した作業：

- B2B管理画面の4件修正、APIと実ブラウザーの認可回帰。
- Phase10計画の13領域の合成テスト、Windows実Excel/PDF出力、画面・帳票の目視確認。
- K01〜K06の現状監査、Phase11の読み取り監査。
- 公開セキュリティ版の隔離install/build/回帰、main統合手順の作成。B2Bとは別branchへ資料だけcommit/push。

未実施：本人の今回B2B画面受入、実スマートフォン操作、実SMTP、実請求・課金、本番copyによるmigration/restore、本番設定・deploy・再起動、main merge/update。Linux PDF disabledは維持。

確認した主な既存資料は`handoff_notes.md`、`docs/phase10-test-plan.md`、`docs/backup-retention-restore.md`、`docs/vps-deployment.md`、各帳票修正記録、開発元`docs/security-vps-retry-20261023.md`と既存テスト。`C:\Users\bunch\.codex\AGENTS.md` v1.3を上位に開発元AGENTSを適用。正規repository側にAGENTSは存在しない。今回明示されたbranch/worktree/commit/push許可を適用し、未解決のルール競合なし。

Notionは読み取りのみ。次を参照した：

- [占術文言はユーザー資料なしに作らない](https://app.notion.com/p/38bf414e63af81e68bb4d238e742c13c)（有効・本人確認済み）。
- [Wを正規版とする原則](https://app.notion.com/p/3d6f414e63af817eaf03f851e2780f48)（有効・本人確認済み）。S/W常時同期の旧原則は採用しない。
- [Phase10既存Sessions](https://app.notion.com/p/402f414e63af8131bd44d2cb2d3bfc41)、[Phase7A本番構成の採用判断](https://app.notion.com/p/3f1f414e63af81b29681de71d364a43a)、関連ロードマップ・引継ぎ。

Notionの古いSessionsにある「最大6件・2列3段」「鑑定書受入未完了」は過去時点の記録。今回は現在の明示指示（4列表と直前3件は受入済み）とGit実体を優先した。原則内容の競合ではなく進捗の更新差として扱い、Notionの受入状態を独断更新していない。AGENTS/CLAUDEへの変更なし。

## B. B2B管理画面の変更・本人確認

|依頼|実装と維持した動作|
|---|---|
|① B2C専用導線除去|所属のある利用者のMemberStartでは通常鑑定入口を表示しない。B2B鑑定・本人履歴は維持。所属なしのB2Cは従来の通常鑑定を維持。休止・未入金でもB2Cへ誘導しない|
|② ヘッダーのマイページ|`/member`で既存のログイン後遷移関数を共用。生徒/B2Cは`/mypage`、先生単一所属は権限確認後`/teacher/{org}`、運営は`/operations`。複数所属は安全な選択入口。取得失敗・停止は安全な入口へ。logout後の遅延応答は遷移させない|
|③ 運営専用化|個人鑑定入口・個人履歴・個人回数の表示と不要なsummary取得を運営画面から除去。Organization/User/Membership/契約/請求/集計/発行・停止・監査は維持。別リンクのアカウント設定とpassword再設定を維持|
|④ 権限外エラー日本語化|所属なし・存在しないOrganizationを同じ「この情報にアクセスする権限がありません。」へ。既存404/403と認可SQLを維持し、内部ID・他Org情報を追加しない|

変更ファイル（repository相対）：

```text
fortune-next-app/app/auth.tsx
fortune-next-app/app/member-start.tsx
fortune-next-app/app/member/page.tsx       新規・役割別入口
fortune-next-app/app/mypage/page.tsx
fortune-next-app/app/operations/operations-view.tsx
product_repository.py                    エラー文字列2箇所だけ
tests/member_navigation_ui.cjs
tests/product_api_cases.py
tests/history_ui_smoke.cjs                再鑑定フォーム反映待ちだけ
docs/phase10-overnight-20261023.md         本報告
```

鑑定計算、判定、正式解説文、report_data.py、report_xlsx.py、承認テンプレート、S/D本体、DB schema、依存versionには変更なし。運営・先生の権限を緩めるAPI変更なし。先生は自教室の生徒名・状態とOrg合計のみ、個別回数・個別日時・他人の本文は非開示。運営の他人の本文通常閲覧不可も維持。

本人受入は次の3役を一括で確認すればよい。受入済み帳票3件のやり直しは求めない。

1. 生徒：ログイン→所属先鑑定入口だけ表示→本人履歴/設定→ヘッダーマイページで初期画面へ。
2. 先生：ログイン→先生管理→自教室の合計・生徒名/状態のみ→B2B本人鑑定/本人履歴/設定→ヘッダーで先生管理へ。複数所属では所属選択を確認。
3. 運営：業務一覧・教室/User管理を確認→個人鑑定入口/個人回数/本人履歴導線がない→アカウント設定→ヘッダーで運営へ。別Org拒否画面は日本語。

保存済みスクリーンショットは開発元`outputs/phase10-overnight-20261023/ui-temp-b2b-native-member_navigation_ui/fortune-member-navigation-QZOLAG/`。1280/390/320px、B2C/生徒/先生/運営/複数所属/休止/未入金を保存。PC運営・390先生・320生徒をCodexが目視し、横はみ出しなし・目的の入口・業務情報を確認。実機とは区別する。

## C. Phase10総合テスト

全て専用localhostポート、新規合成SQLite、mockまたはin-memoryコピー。3000/8765の既存環境を使用・停止していない。mail disabled/MemoryMailTransportのみ。外部の実SMTP・実課金・実ユーザーデータ・本番DB不使用。

|領域|今回の確認と結果|残る外部/本人工程|
|---|---|---|
|1 baseline/計算|Tier A 556/556、Tier B 38/38一致、harness16、五行A/B/C・境界・再鑑定。source hash147件 changes0|Tier C 6件はDへ。S比較は任意・未実施|
|2 認証/B2C|認証44、履歴32、recovery12、production設定7。B2C入口・owner/token/session・CSRF・偽装を実API/画面で確認|本番実アカウント操作は未実施|
|3 Org分離|foundation19、product API25、連携6。別Org/host/body偽装拒否、本人scope・部分解約保護|実契約/実利用者は未操作|
|4 3画面/権限|実役割遷移186、管理mock50、API exact whitelist・日本語404/403。運営個人UI非表示、先生個別情報非開示|本人のまとめ受入|
|5 Org管理/発行|operations22、product API/連携。singleton、入金確認、初期token・本人password・audit|本番operator/初回発行は未実施|
|6 reset/メール|reset22、mail9、reset UI20。30分/hash/single-use、enumeration対策、旧session失効、disabled表示|SMTP実送信は未実施|
|7 回数|execution15、usage9、管理/連携。成功新規実行のみ・再送冪等・未保存加算・memo/再表示非加算・JST月|業務受入|
|8 請求/休止|billing42、billing API11、UI18。月末/閏年/JST、猶予・督促preview、未納停止・入金復帰|実送信/実請求schedulerは未実施|
|9 解約/復旧/削除|final retention34、API8、recovery12/UI16、連携。期限固定・再契約取消、fileDB/API purge拒否|本番物理削除executorは未実装|
|10 User/購入/C/D|lifecycle12、final retention34/UI12、連携。B2C/別Org保護、購入証明独立、同商品免除、未知依存拒否|B2C終了保持・法的保持根拠は本人判断|
|11 Excel/PDF|Excel58、PDF21、実出力UI12。特殊命式0〜8/13/16/25件・全日干・幾何回帰、Windows実PDF4件・目視|Linux PDFはdisabled。実端末/今回画面の本人受入のみ別|
|12 migration/backup/rollback|既存migration/保持/K01-K03テスト、追加の隔離DBコピー8確認。旧データfingerprint・DDL失敗rollback・旧schema復元、session/reset失効・削除再適用|本番copy・外部backup・fileDB削除/復元は別承認|
|13 build/PC/スマホ|通常Turbopack production build、TS、Node51成功。PC1280/スマホ375・390・320、五行UI81、K01/K03 UI48、runtime/幅確認|実スマートフォンは未実施|

件数は同じsuiteが複数領域を覆うため、上表を足し算しない。

### 実行件数・証跡

- Python unittest **23スイート495/495 PASS、失敗0**（`python-results.json`）。内訳：harness16、auth44、history32、recovery12、foundation19、operations22、productAPI25、reset22、mail9、execution15、usage9、billing42、billingAPI11、final34、finalAPI8、lifecycle12、Excel58、PDF21、K01/K03 42、integration6、predeploy7、deployblocker20、productUI9。
- 別枠で`tests/check.py`：Tier A556/556、B38/38、参照値196件中通常許容内195・既知例外1。gogyou_daiun_effectsはTier A内の19ケースで実行済み。同moduleの直接起動は終了0だが単独テスト数へ追加しない。
- Node：51/51 PASS。TypeScript・buildは終了0。
- ブラウザー確認単位：member navigation186、history smoke28（14×2端末）、boundary1シナリオ、report export12、K01/K0348、五行81、管理50、billing18、final retention12、reset20、recovery16、auth 34/34（再開後の再実行成功）。件数はsuiteのシナリオ/確認定義であり、全assert総数ではない。
- ブラウザー最終実行は上記合計506確認単位で成功、最終失敗0。初回失敗を消さず、`browser-final-results.json`と`final-verification.json`に最終結果を分けて保存。認証再試験の出力は`ui-temp-b2b-native-auth_ui-resume-20261026/auth-screenshots/`。
- 追加のDBコピー検証8/8。旧schema/data fingerprint `4465e001cd8164ff1c6d16b0391cd972d5f736954ea6dc2d27829fdd4609360e` とrollback先が一致。既存合成元DB byte hash不変、integrity=ok、FK0、繰返し適用不変。
- 公開セキュリティ候補の別検証：Tier A524/B38、Python unittest186、Node5、auth UI34、TS/build成功（B2B件数には加算しない）。

### 失敗と対応（成功で上書きせず記録）

|分類|事象|対応・最終状態|
|---|---|---|
|C 環境|外部node_modulesへのjunctionをTurbopackがworkspace外として拒否|依存を隔離先へoffline frozen install。lock変更なし、通常build成功|
|C 環境|通常sandboxの検証サーバー起動/待受で9 UIスイートのready待ち失敗|専用ポート・新規合成DBの範囲で権限を限定して再実行。初回結果は`browser-sandbox-failures.json`と`sandbox-failures/`へ保存|
|C テスト条件|history smokeがルート遷移直後の初期空欄を読んだ|診断で反映後の氏名/かな/生年月日は正しいと確認。期待値は維持し実際の引継ぎ値を待機するテストだけ修正。再実行で28シナリオとboundary成功。アプリ履歴処理変更なし|
|未確定・Cの可能性|B2B auth E2Eの最初のPDF要求でproxy ECONNRESET→HTTP500、download待ちtimeout|別の実出力UIではPDF4件成功。2026-10-26の再実行はPC/mobile全34確認と実PDF4件が成功し、同じ切断は再現しなかった。初回失敗ログは保持。正確な切断原因はログだけでは確定できず、帳票ロジックを推測変更していない|
|C 検証補助|新規DBコピーscriptのfixture属性名誤り、PDF検査用Pythonにライブラリなし|fixtureに専用pathを明示して8/8成功。PDF検査はbundled Pythonへ切替。app依存追加なし|

今回の実装による確定したA回帰は0、確定した既存B不具合は0。前記PDF通信の原因未確定という制限を残す。Windows実PDFの一過性失敗は、本番LinuxのPDF有効化を認める根拠にはしない。PDF21テストの出力には意図的な変換失敗ログがあり、例外処理の合格ケースと予期しない失敗を区別した。

### 帳票の実ファイル確認

今回の変更後ソースからブラウザーで保存/未保存・PC/mobileのExcel4件＋PDF4件を実ダウンロード。確認先：開発元

`outputs/phase10-overnight-20261023/ui-temp-b2b-native-phase10_local_ui/fortune-export-ui-EdzR9e/`

代表は`PC_saved.xlsx`、`PC_saved.pdf`。4 PDFともA4縦2ページ、メモ非出力。PDFのベクター測定では外枠中心と円の中心軸の差は丸め誤差相当（<0.001pt）、左右ラベルの高さ差0pt、円から文字までの左右距離差最大0.195pt。`report-inspection.json`へ保存。`report-pages/PC_saved-1.png`と`-2.png`を目視し、4列表・説明→キーワード・五行図・後続本文に重なり/見切れなし。ExcelはOOXML構造と完成Excelからの実PDF変換で確認し、Excelアプリの操作画面を新たに目視したとは扱わない。

検証用ファイルは全て開発元`outputs/phase10-overnight-20261023/`。個人情報は合成名/example.testのみ。依存コピー・DB・ログ・screenshots・PDF/XLSX・backupはGitに追加しない。サンプルや認証fixtureは本番利用不可。

## D. K01〜K06監査

|ID|実装・テスト・解決済み|未解決/人間判断|本番導入への影響|
|---|---|---|---|
|K01|登録年2026のみ正式文。2027等は`interpretation_status=unregistered`、theme/comment空、「この年の正式解説は未登録です」。2026流用防止、旧snapshot/保存/Excel/PDFも42テスト・連携・UI48で保護|2027正式原稿の提供・採用判断。創作/流用しない|2027正式解説を含む商品として提供する場合は未登録が残件。計算自体の対応とは分ける|
|K02|B2C UI1〜3/API4を維持。B2Bの特定日時UIは非表示、APIも422拒否。productAPI・管理UI/Tier Cで保護|B2B採否・候補上限の正式整合方針|現行の無効状態を維持するB2Bには新たな機能追加条件。採用するなら判断が必要|
|K03|public_result_snapshotがprivate文言/項目を除外。新規・保存・旧履歴読取り・exportのprojection、owner/Org認可を42テスト・連携・UI48で保護|実DBの旧snapshot物理書換えは未実施。既存migration scriptは合成DBだけ検証|顧客応答の制御は維持。本番の物理書換えを必要とするなら別承認/backupが必要|
|K04|対応上限2050を維持。2050月運の翌2051年1月は現行範囲外。Tier Cで検知|正式対応年・上限端の表示/計算方針|2050年末を保証範囲へ含めるなら未解決。無断の範囲拡張なし|
|K05|Wを正本。S/Dを更新せず、今回PC/mobile幅と帳票回帰。直前の帳票3修正は今回の明示指示で受入済み|今回B2B画面の実端末本人受入、残るW商品仕様の最終受入|Sとの完全同一化は条件ではない。Phase10正式完了承認は残る|
|K06|採用engine/baselineを維持。2021資料23:58/engine23:59、1975啓蟄資料14:08/採用14:06を既知として参照検査。195/196が通常60秒内・既知例外120秒1件、変更時はreview|資料の正式基準/採用値の確認。独断変更禁止|既知差を許容する現基準の維持。正式基準変更を伴う場合は先生/本人判断|

K07 OFF隔離はTier A guardで解決済み、変更なし。テスト計画のK01/K03欄は古い問題説明のため、実装・最新の既存記録と突合した。計画自体を独断で完了へ書換えていない。

## E. 公開版セキュリティmain統合準備（別branch）

- main/origin/main `e8b53082775744a74f66502e8fb8f3cef72974c1`、候補`241dd57e39e451ad1c626414d93290b875d027fc`。merge-base=main、fast-forward可能。
- mainとの差分はsecurity依存/config/版指定/test adapter/docsの10ファイルのみ。公開版tree/buildにB2B/teacher/operationsなし。
- 本番配備コードbdc6de9から候補までの差はdocs2ファイルだけ。package/lock/workspaceはLF/CRLF正規化後同一、frozen install中lock不変。
- 専用Node24.22.1/pnpm11.7.0、Next16.4.2、React/ReactDOM19.3.1、TypeScript6.0.3。隔離TS/build/自動検証成功。現在の稼働版をVPS接続で再測定した結果ではない。
- 完全手順・停止条件・rollback注意は専用branchの`docs/security-main-integration-prep-20261023.md`。本人承認後、新worktreeでremoteの固定HEADを再確認し、ff-only→dry-run→通常push→remote確認。mainや候補が変化していれば停止し再監査、force/resetしない。
- GitHub履歴の統合と本番切替は別承認。旧repository HEAD569d149や共通Nodeリンクだけで稼働版を決めない。最新記録ではWeb releaseは別cwdのbdc6de9・専用Node24.22.1。旧Node24.17/Next16.2.9へ戻すとセキュリティ問題が再導入される。Git統合の問題を理由に本番DB/Webを直ちに巻戻さない。

準備資料branch `phase10-security-main-prep-20261023`、commit `5294878e25008efe3c97ba7c94f3245738910b8c`、push済み。241dd57から分岐し資料1ファイルだけ追加、B2B成果の混入なし。worktreeは開発元`outputs/phase10-overnight-20261023/security-git`に保持。

## F. Phase11 読み取り監査

|項目|準備済み/確認したこと|配備前の必須条件・不足|
|---|---|---|
|B2B配備|W正本・分岐履歴・local13領域確認、既存VPS runbookあり|対象HEAD/稼働cwd/実効systemd/公開範囲を固定。B2B配備の本人承認。mainのセキュリティ統合とは別|
|DB migration|B2Bは追加schemaをconstructorで適用。8 migration key（auth lifecycle/reset/setup、product foundation/operations/executions/billing-retention/final-retention）。合成旧DBコピー・失敗rollback・復元成功|本番pathと現行schemaを承認下で読み取り比較し、backup後に隔離本番copyで検証。未承認で実DBへOperationsRepositoryを作らない|
|backup/restore|日次・VPS外・暗号化・30日方針、SQLite backup APIと復元runbook、削除manifest/最新性/世代差の安全guardあり|外部保存先/鍵/責任者/時刻/監視/30日rotation未設定。最新削除情報の独立保存と信頼できるcheckpointが必須。古いbackupのhashだけを最新性の証拠にしない|
|削除と復元|memory-only purge/replay、fileDB/API拒否、session/reset失効、全User停止後の本人/契約照合、削除済み情報再適用を検証|本番fileDB executor、承認・dry-run・監査・最新台帳照合の実装と検証。削除journal自動消去は未実装|
|SMTP|mock/disabled、token30分single-use/hash、初回設定とresetの連携成功|送信元/credential/trusted origin/DNS・SSL・到達性・運用責任者を確定し別承認で実送信。secretをGit/報告へ記載しない|
|Linux PDF|既存disabled表示/直接API503、Windows完成Excel→PDFを検証|Linux converter未実装。採否と再現性/ページ検証なしで有効化・PDF提供を約束しない|
|B2B URL|既存`/b2b/{org}`と先生/運営route。Org IDと認証APIを権限の正本にする|利用するドメイン/URL、DNS/SSL、trusted origin、誤ったhostでの表示方針は本番導入前に確定。host/body値を認可根拠にしない|
|初回アカウント|運営singleton、手動入金確認後発行、本人設定link・audit、平文passwordを運営へ渡さない|実operator/教室/入金台帳・送付先の確認、SMTP完備後に個別承認で発行。本番発行なし|
|請求/休止/解約|承認済み境界・preview・未納停止/入金/復帰/解約保持を合成で確認|実請求・督促・scheduler・決済は未稼働。担当者、入金照合、誤操作時の手順と本人受入が必要|
|保持/C/D|B2C/未知依存保護、購入証明独立、法令/契約記録を分離|B2C終了保持、本人確認証跡、C/D種類別根拠・見直し日・不要PII最小化は人間判断。法定年数を推測で固定しない|
|切替/rollback|local schema/data fingerprint、backup/旧schema復元、権限/削除整合の検査あり|maintenance/最新backup・checkpoint・監視・復旧責任者・停止条件を確定。コードだけ戻して旧認証/削除済み履歴を復活させない。本番操作は全て別承認|

## G. Git・保存先・終了状態

|対象|branch / commit / 状態|
|---|---|
|継承基準|phase10-gogyo-symmetry-20261023 / 81d1cef6cfc0ebcd07a48267031108443d8f940f（受入済み）|
|B2B 4件修正|phase10-b2b-overnight-20261023 / 249d9e54b030bf31b31de17146dc96a053895211|
|再鑑定待機テスト|同branch / 0b9d305245e9f568c4ed2a97ac1f2d2664759bad|
|総合記録|同branch / 本書を含む最終HEAD（具体hashは開発元の最終Git実測・チャット報告へ記載）|
|公開セキュリティ準備|phase10-security-main-prep-20261023 / 5294878e25008efe3c97ba7c94f3245738910b8c、origin push済み|
|main|e8b53082775744a74f66502e8fb8f3cef72974c1を維持、merge/push/deployなし|

B2B最終push/working tree：本書commit後に専用branchだけをpushし、origin一致・cleanを確認する。実測値は開発元の本書末尾「最終Git実測」へ追記する。公開準備worktreeは5294878・origin一致・cleanを確認済み。main/origin/mainは2026-10-26の再fetchでもe8b5308のまま。

ローカル補助scriptは開発元`research/run_overnight_*_20261023.py`と`run_overnight_*_20261023.ps1`、stagingは`research/overnight_20261023/staging`、変更前控えは`_backups/public/overnight-20261023`。Git対象は上記コード/テスト/資料のみ。既存ファイル・フォルダ削除、履歴破壊、実DB変更なし。

## H. 次に行うこと（本人とCodexを分離）

1. **本人**：B節の生徒/先生/運営3役の画面をまとめて受入。必要ならCodexが同じ合成データで確認環境を起動する。実スマートフォンでの操作感も一度に確認する。
2. **本人**：E節の公開セキュリティmain統合だけを独立して承認するか決定。本番deployやB2B混入を含む承認ではない。承認後のGit操作・照合はCodexが実行可能。
3. **本人**：Phase10の正式完了、K01/K02/K04/K06の採用範囲と残件、B2C/C/D保持、backup保存先/鍵/担当、SMTP/Linux PDF/本番URLの判断を必要な単位でまとめる。
4. **Codexのみで続行可能**：指摘された小規模な画面調整、合成の再現確認、runbookの具体化、PDF通信切断の追加観測。ただし新しい占術判断・実データ操作・本番設定を含めない。
5. **別の明示承認後にCodexが行う工程**：公開main統合、本番copyの取得/移行検証、外部backup設定、SMTP実送信、本番operator/利用者発行、B2B配備・再起動。今回の「再開して」をこれらの承認と解釈しない。

今回必要な本人判断と受入はこの一覧に集約した。自動検証済みと本人受入済み、本番での実測済みを混同しない。
