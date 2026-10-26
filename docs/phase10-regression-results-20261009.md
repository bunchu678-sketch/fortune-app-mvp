# Phase 10 総合回帰テスト記録（2026-10-09）

## 結論・判定範囲

正規Wの全13領域のローカル自動対象を検証した。Phase 10全体は完了扱いにしない。本人による画面/実スマホ/鑑定書確認と未確定仕様・外部環境確認が残る。main統合、本番配備、Phase 11実施の承認ではない。

PASS=今回実行して期待一致、FAIL=今回実行して不一致、BLOCKED=仕様/環境前提が不足、NOT RUN=未実施。以下のPASSは明記した隔離条件の範囲だけ。未実施を成功へ算入しない。

## 開始Git・参照・規則

- 正規Repository: `C:\Users\bunch\Documents\Codex\fortune-app-public`。正規W（Next.js/Python API）、S/D参照専用。
- 開始branch `phase10-k01-k03-fix-20261009`、HEAD `090d5c77aeef008d147e9bcddd4af42063bb5758`。working tree clean、origin同branch同HEADを確認。
- 同名branchが存在しないことを確認し、指定の `phase10-regression-20261009` を作成。旧branch/main/履歴は変更しない。
- global `C:\Users\bunch\.codex\AGENTS.md` v1.3を最上位共有規則として、開発元AGENTS、親WORKSPACE_RULES、既存引継ぎ、Phase 10計画、K01/K03実装記録、Phase 9最終保持記録、backup runbook、正式Tier A/B/節入り資料/既存API/UI試験を参照。正規public固有AGENTSはない。
- Notion「fortune-app 商品版開発ロードマップ（現在地・次作業管理）」を読み取り再参照。最終保持/K01/K03/Phase 10進捗は現在Gitより古い。本作業の実行根拠は最新本人添付 `6818cbc8-466c-4b24-8204-65bfe5fc421f`。古い進捗を新仕様として扱わない。Notion書込みなし。
- 最新指示がテストの追加/修正を明示許可しているため、その範囲で進めた。規則の追加競合なし。PDFスキルは生成済み鑑定書の読み取り・レンダリング確認に使用する。

## 変更したファイル（テスト・記録だけ）

1. `tests/gogyou_ui_smoke.cjs`：旧checkbox/棒グラフを正式A/B/C SVGの試験へ更新。
2. `tests/history_ui_smoke.cjs`：検索日範囲に元鑑定日と再鑑定の今日を含める準備修正。検索件数/履歴/保存値の既存判定を維持。
3. `tests/phase10_integration_cases.py`：不足するA〜Fの連携6試験。
4. `tests/phase10_local_ui.cjs`：新規合成DBによる既存live UI試験・本人確認準備。port占有時は停止、所有childだけ終了。
5. `tests/README.md`：試験の隔離範囲、実行方法、証拠の区別。
6. 本記録。

アプリ本体、正式画面、占術計算、解釈文、fixtureの正式期待値、既存DB、S/D、依存関係は変更していない。

## 更新した五行UI

既存正式画面 `main-fortune.tsx` / `gogyo-figure.tsx` の `gogyo_variants.A/B/C` と `status/gogyo.scores/chart_order/kantei_year/daiun` を参照。各図の五行名＋点数をその段階のAPI値と照合し、3見出し、図の存在/不在、Bの鑑定年、Cの対象大運を検査。

- PC1280/スマホ390/小型320 × 通常/性別未選択でC算出不能/立春待ち/立春前/立春後。
- `available` はSVG、`boundary_pending` は「節入りの確認後に算出します。」、`unavailable` は「大運を取得できないため算出できません。」。
- 2020立春前=己亥、後=庚子の正式期待を検査。Aは境界待ちでも表示。
- 全81項目PASS、skipなし。全幅で横overflowなし、pageerror0。
- 応答fixtureは現行の実計算から生成し、ブラウザへの接続/描画を検査する。実サーバーへの一連の境界選択は別の `history_boundary_ui.cjs` でPASS。mock表示とreal API動作を混同しない。
- 正しい数値の独立期待は既存Tier Aで保護：鑑定年ON/OFF20件、大運A/B/C19件、OFF非干渉K07等。旧checkboxをUIに戻さず、重要計算試験を削除/skipしない。

## 最終自動集計

|群|今回の結果|補足|
|---|---|---|
|Python全 `*cases.py`|PASS 466/466（264.172秒、failure/error/skip0）|既存460＋連携6、合成User/Org/tempDB、物理削除はmemory限定|
|Tier A|PASS 556/556|32 K01/K03は全cases側と重複|
|Tier B|PASS 38/38、review0|正式観測fixture不変|
|S/W pure比較|PASS 1100/1100、review0|14関数、S読み取りのみ|
|test harness|PASS 16/16|失敗検出自体の検査|
|Node日時/reset/実行ID|PASS 13/13|既存MODULE_TYPELESS warning、依存変更なし|
|TypeScript|PASS|tsc --noEmit --incremental false|
|Next production build|PASS|13 static pages生成、配備なし|
|五行A/B/C browser|PASS 81/81|1280/390/320、合成実計算応答|
|管理/請求/reset/復旧/最終保持UI|PASS 116/116|18＋50＋20＋16＋12、localhost mock|
|K01/K03表示UI|PASS 48/48|PC/スマホ、B2C/B2B/旧確認/履歴、2026/2027|
|認証live E2E|PASS 34/34|合成User/tempDB、実Excel/Windows PDFdownload、owner分離|
|履歴live UI|PASS 28シナリオ|PC/スマホ各14、今回OS/API/runner時計変更なし|
|出力live UI|PASS 12/12|保存前/保存後/失敗回復、Excel/Windows PDF実出力|
|境界live UI|PASS 1 suite|出生補正保持・鑑定日補正解除・新年算出|

ブラウザ数は319項目/シナリオ＋境界1suite。suiteを1assertionとは数えない。Pythonは466＋556＋38＋16−32重複＝1044件。S1100、Node13、browserとは合算しない。

Source hash: W132/S7050、changes0。Sの巨大な依存cache `.pnpm-store` だけ検査実行時に除外。テスト変更はhash対象外、別途Git差分で本体無変更を検査。

## 13領域（件数は共有試験を含むため行合計しない）

|領域|ローカル実施/主要証拠|未確認・制限|
|---|---|---|
|1 正式計算/baseline|PASS Tier A556、B38、S1100。命式/蔵干/節入り/時刻不明/未入力/手動補正/五行/年運/既存B2C特定日時|K04/K06既知注意事項、K05の人間による比較は残る|
|2 認証/B2C|PASS auth44＋history32＋account lifecycle12、live認証34。login/logout/期限/CSRF/owner分離/保存/再鑑定|B2C終了後保持仕様BLOCKED|
|3 B2B/Org|PASS product foundation19＋product API24。別Org spoof/所属/利用契約gate、複数Org保護、連携D|B2B特定日時最終仕様BLOCKED、現在の拒否はPASS|
|4 生徒/先生/運営|PASS operations22＋product API24＋usage9＋product UI9、管理UI50。先生は教室集計のみ、他人本文は運営も404|本人による実画面NOT RUN|
|5 Org管理/発行|PASS operations22＋product API24、連携A。入金確認/初回設定/先生契約終了と生徒継続/管理audit|実組織発行はNOT RUN、合成組織のみ|
|6 reset/mail|PASS reset22＋mail9＋browser20＋Node reset4。30分/一回限り/列挙防止/session失効/障害時/MemoryMail|実Xserver SMTP BLOCKED（本タスク禁止）、未送信|
|7 回数/JST|PASS execution15＋usage9＋Node JST5/実行ID4、連携A。保存と実行の区別/replay/失敗/境界/教室集計|本番集計NOT RUN|
|8 請求/未納/休止|PASS billing42＋billing API11＋browser18、連携B。初月含む/翌月/2か月猶予/3か月目休止/精算/再契約|自動実課金/督促/停止は未有効、NOT RUN|
|9 解約/復旧/期限|PASS recovery12＋billing42＋final retention34、browser16、連携C/D。JST満了/30日/復旧で延長なし/再契約取消し|file DB/production物理削除は未実施、memory限定|
|10 User/購入/C/D|PASS final retention34＋API8＋browser12、連携E。User保護/購入証明独立/本人確認宣言/他商品拒否/C/D保持|メール変更本人確認、会計法定保持/消去BLOCKED|
|11 Excel/PDF|PASS report46＋PDF21、live出力12、認証E2E内実download、連携A/F。正式template/同一Excel変換/owner/expiredtoken/503/timeout|Linux converter BLOCKED、本人によるレイアウトNOT RUN|
|12 移行/backup/復元|PASS deploy blocker20＋predeploy7＋K01 snapshot/migration6＋final retention34内の復元等。加算移行/SQLite backup/rollback/FK/削除再出現防止/session-reset失効/世代不一致停止|外部日次暗号化30日backup・最新checkpoint・file restore executor BLOCKED、既存DB接続同定BLOCKED|
|13 build/PC/スマホ|PASS tsc/build、browser319＋境界1suite。PC1280/スマホ375/390/320、overflow/runtime検査|本人・実スマホNOT RUN。localhostはこのPC専用|

全casesのモジュール別件数: account_lifecycle12、auth44、billing_api11、billing_retention42、deploy_blocker20、execution15、final_retention_api8、final_retention34、history32、history_recovery12、k01_k03 42、mail9、operations22、password_reset22、phase10_integration6、predeploy7、product_api24、product_foundation19、product_ui9、report_export46、report_pdf21、usage9。

## 一連の連携A〜F

全6試験PASS。`phase10_integration_cases.py` は既存fixtureのsetUp/tearDownと実Repository/ASGI endpointを再利用。

- A: 運営API発行→MemoryMail初回token→初回設定API→login API→生徒B2B鑑定→成功1回/replay増分0→保存/取得→再鑑定/同group別履歴/成功2回→両履歴Excel/PDF。元snapshot不変、先生の他人出力404。PDFは記録adapterで元完成Excelの全package一致を検査し、実変換はlive E2Eで補う。
- B: 実利用開始→翌月請求起点→期日後の運営未納確認→2か月猶予境界→scope休止→未精算再契約拒否→精算→本人/支払確認済み同商品再契約→元データ再利用。実請求/送信なし。
- C: 正式解約→支払済み期間終了→30日中復旧→削除期限維持→期限直前/直後本文可視性→再契約で予定取消しと再表示。
- D: 同User2Org/B2C→一方だけ解約満了→User削除保留→memory上scope削除→他Org/B2C履歴・User・FK保護。
- E: 同商品購入証明→両Org解約→B2C非利用確認→memory上User削除→証明残存→別商品は拒否→同商品本人/入金確認→新UUID/初回設定待ち/初期費用免除/旧鑑定本文非復活。
- F: 2026原文baseline→2027未登録→APIと正式計算全体一致→保存/取得private0→年別鑑定書→PDFに同じ完成Excel。2027に2026原稿なし。

API/Repository連携・mock表示・real browserdownloadの証拠段階を区別する。A〜Fすべてを実メール/実顧客の実画面で通したとの意味ではない。

## 失敗の切り分け・不具合

新たなアプリ本体の重大な認証/Org分離/漏えい/破損は検出していない。本体修正なし。

- 旧五行UI: 開始HEADからないcheckbox/棒グラフを要求していたテスト前提の不一致。今回A/B/Cへ正式更新、81PASS。
- 履歴UI: 10月1日だけの検索で、今日へ移る再鑑定を4件に含めていた。両日を含む範囲へ修正し、既存4件判定・snapshot不変・削除保護を維持、28シナリオPASS。
- 追加連携試験の初期準備不備: UUID実行ID形式、RecordingConverter.inputs属性、図形内Excel文章の取得、既存helperの日時重複、blocker名称、合成未納確認日時を実コードへ合わせた。正式期待値の緩和ではない。
- 全cases初回466件中1FAIL: 追加AのMemoryMail設定をcached ASGI appへ残し、次の別DBの発行試験で安全な503「メール設定を確認してください。」になった。試験モックをpatch/addCleanupで復元するよう修正。これは新テストの隔離不備であり、本体の安全停止を回避しない。全cases再実行は466/466PASS、failure/error/skip0。
- ローカルUIランナー初回: OperationsRepositoryへの明示DB引数不足。合成DB指定に修正し、3 live suite成功。
- PDFログのconverter_unavailable/timeout/cleanup_error等は既存failure-path試験が意図して注入。最終unittest failures/errorsと区別する。

## K01〜K06と未決仕様

- K01: 回帰PASS。2026正式原稿10種類不変、2027未登録、保存年/version凍結、再鑑定は別履歴。2027以降の先生正式原稿は未受領・未登録。
- K03: 回帰PASS。122文章の削除とpublic不変、通常13不要result paths0、匿名/認証/B2B/保存/旧JSON/メモ/復旧/出力で再露出なし。他人本文は認証・owner・Org認可で保護。private0だけを第三者分離の証拠にしない。
- K02: B2C UI3候補/API4候補の既存挙動を維持。B2Bは仕様保留、暫定拒否PASS。正式仕様判断を独自に追加しない。
- K04: 2050の翌1月2051は対象範囲外。既知状態PRESENT、対象年拡張なし。一般利用時の説明/扱いは判断が残る。
- K05: Wを正本。pure S/W1100一致。表示差の本人確認はNOT RUN、S/D変更なし。
- K06: 2021資料23:58/採用23:59の既知差を維持。196参照 uniqueのexact125/60秒以内195/超過1、最大120秒は1975啓蟄の既知例外−120秒。許容を一般化しない。
- K07 OFF非干渉はblocking正式回帰PASS。

B2C終了後保持/削除、メールアドレス変更時の購入者本人確認/証跡、会計種別ごとの法定期間/消去方式、削除journalの見直し/PII最小化は未決のまま。法令の新判断や実装はしない。

## 既存ローカルDB・復元の制限

既存 `data/history.sqlite3` はshell overrideなし、3履歴table/persons/groups/readings、readings2、integrity=ok/FK0。前回と同じSHA-256 `9faacb971b429179eba95083a32b81f2c8f7321bb1e538b47665e9b3055d3da1` を読み取りURI `mode=ro&immutable=1` で確認。旧schema/privateは物理残存しているが返却投影で保護する既存実装。DB変更、backup作成、移行なし。

今回稼働を確認したAPIの親は今回の `auth_ui.cjs` 等の所有test serverで、接続先は一時DB。既存DBが実稼働先であることは確認できていない。接続先同定を無理に推測せずBLOCKED。確認用環境も別の合成DBを明示する。

移行検証は合成DBだけ。旧2026/2027 snapshot/Org参照/source/削除済み行を含み、dry-run不変、外部backup一致、変更限定、FK/integrity、失敗rollback、再実行0を再検査。メモ/正式計算/owner/ID/参照/保存日/削除状態の保持を検査。

復元はmemory DBだけ。最新manifest/digest/同origin/再契約cycle整合性が必要、不一致・未知依存は安全停止。削除済み本文を戻さずsession/reset token失効、復元Userは再確認までdisabled。file purge/restore executor、外部保管の信頼性・日次/暗号化/鍵管理/30日rotation/実rollbackは未実装/未検証。VPS文書上のDB `/var/lib/fortune-app/history.sqlite3` と混同せず、本番へ接続していない。

## 本人確認の最小手順

`node tests/phase10_local_ui.cjs --review` により別の合成DB・試験アカウント・2026/2027履歴・完成Excel/Windows PDF・詳細URLをOS一時領域へ準備する。login情報、DB、生成ファイル、screenshotsはGitへ登録しない。localhost同PCでのみ利用可能。

1. 確認手順ファイルを開き、B2C/生徒で各login。準備した2026/2027履歴でA/B/C・Bの鑑定年・Cの対象大運・折りたたみメモ・2026原文/2027案内を確認。入力条件は1988-08-12 09:00、東京都、男性、鑑定日2026/2027-09-30。
2. マイページと履歴を確認し、再鑑定で今日へ移ること・元履歴保持を確認。実アプリ認証/認可を使い、画面確認のために本体を改造しない。
3. 準備した2026/2027 Excel/PDFを開き、A4縦2ページ・年/文章・図・見切れ/印刷品質を確認。
4. logoutして先生/運営で各loginし、先生は教室集計のみ、運営は通常本文なしの管理画面を確認。
5. 実スマホは別確認。今回のlocalhostをスマホへ公開するネットワーク設定は行わない。準備の完了を本人確認の完了に数えない。

準備済みlocalhost: `http://127.0.0.1:3000/login`。詳細URL/試験用情報は `C:\Users\bunch\AppData\Local\Temp\fortune-phase10-local-oZwhRc\本人確認手順.md`。

確認用DBは同じ一時folderの `synthetic.sqlite3`。2026/2027鑑定書は `鑑定書-2026.xlsx` / `鑑定書-2026.pdf` / `鑑定書-2027.xlsx` / `鑑定書-2027.pdf`。runnerは所有API8765とNext3000だけを起動中。確認後はCodexへ終了を依頼できる。既存サーバーの停止はしていない。

Codexは生成PDFをpypdfで読取り、各2ページ/A4相当595.2×841.44pt、2026正式原稿全文一致、2027未登録案内/2026本文不在を確認。Popplerで4ページをPNGにし、図/表/文章/総合枠の目立つ見切れ・重なり・文字欠落なしを目視確認。320px通常/PC境界待ちのbrowser screenshotも点検した。これはCodex確認であり、本人確認・実印刷・実スマホ確認はNOT RUN。

PDF確認の初回でbundled Pythonからアプリ計算を呼ぶとアプリ依存の不足でyearly_overallを取得できなかった。再計算をせず、固定された2026承認原稿fixtureと2027確定案内を生成済みPDF全文へ照合してPASS。PDF/appを変更していない。

## Phase 10完了に不足・Phase 11持越し

本人のPC/実スマホ/正式鑑定書確認、K02/K04/K05/K06の残る判断、未確定保持/本人確認/会計方針、未登録年原稿、既存DB接続同定が残る。Phase 10自動範囲成功と総合完了は別判定。

実SMTP、VPS外暗号化日次30日backup・信頼できる最新checkpoint・file復元手順、Linux PDF、商品subdomain/DNS/HTTPS/ブランド仕上げ・本番secret/権限/監視/配備はPhase 11等の別工程。本番自動課金/督促/物理削除を今回有効化しない。

## Git保存・終了

上記テスト・記録6ファイルだけを差分確認後にcommitし、指定新branchだけoriginへpushする。正確なcommit HEAD・remote一致・clean・保護branch不変は最終確認で報告する。DB・秘密・合成login・一時成果物・本番データはGitに入れない。Notion変更なし。
