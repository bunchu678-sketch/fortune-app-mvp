# Phase 9 最終保持仕様・Phase 10準備（2026-10-09）

## 1. 開始状態・適用指示

- 正本：`C:/Users/bunch/Documents/Codex/fortune-app-public`、W（Next.js＋Python API）。開発元・S/Dは変更しない。
- 開始branch：`phase9-billing-retention-20261009`。開始HEAD：`31d2363de1ca3949cbdb489e245e0456cd889371`。
- staged/untracked0、tracked170/170をindex/blobとpath-filter適用hashで照合、一致。既存未commit変更なし。
- 新規branch：`phase9-final-retention-20261009`。既存branchとmainを直接変更しない。
- 確認資料：global `C:/Users/bunch/.codex/AGENTS.md` v1.3、既存billing実装記録、schema/repository/API/UI/tests、`docs/vps-deployment.md`。正本rootのAGENTS.mdは存在しない。
- Notionは関係する記録のread-only検索のみ。今回の最終保持仕様に該当する確定記録は取得できず、現行ユーザー指示を根拠にした。Notion変更なし。
- 旧実装の「復旧後は削除hold」と今回確定した「復旧だけでは期限を延長しない」は、最新指示に従って変更した。global/project指示との追加の衝突なし。

## 2. 既存実装の再利用

Auth/User UUID・Argon2id・session、Organization/Membership/先生提携contract、生徒利用contract、手動dues、管理audit、JST billing_policy、30日復旧、scope履歴分離、memory-only purgeを再利用した。
新User発行は既存`issue_account`を共有transaction内から呼べるようにした。password/初回設定/reset token/メールadapterは作り直していない。購入証明の登録・再契約ではlive mailを送らない。
既存の販売自動台帳はなく、`initial_payment_confirmed`と月額`manual_dues`がある。追加purchase proofは購入額・販売/報酬計算を重複実装する台帳ではなく、User削除後にも必要な商品の購入済み証明。

## 3. 実装

### User保持・削除ドライラン

`RetentionRepository.user_plan`は運営のみ。全student所属の保持期限とsource参照を確認。activeな他Org、期限未満、未知contract、teacher等非student所属、運営singleton、未知User FKがあれば拒否。
B2C利用はactive/inactiveの明示確認を追加した。未確認は保護。inactive確認だけで既存のunscoped B2C履歴/実行記録を消さない。これらがある場合はB2C側の終了・保持方針の確認が必要なためUser削除を保留する。
全Orgの解約/休止保持期限満了・B2C確認・参照解決後、`purge_user_memory_fixture`でA/Bを削除するテストを実装。scope purgeを既存処理から呼び、全体を1transactionとした。
file DB、attached file DB、FK無効は拒否。内部remove helperにも同じ制限。User purge API/ボタン/schedulerはない。

### 正式解約・休止・復旧・再契約

正式解約は既存の支払済み利用終了+30日、休止は既存1暦年+30日（JST）。復旧のみで原期限を延長しない。復旧データの画面アクセスも元の30日で終了する。
購入証明・手動本人確認・月額入金確認・明示paid-throughを満たした再契約だけ、scopeの解約/休止/削除予定を取り消す。他Org/グローバルUser状態へ波及しない。未納の全額精算、User利用状態も確認する。
現在の契約が終了する前の再契約、active契約の置換は拒否。再契約でcycle_idを更新し、2か月継続を既存policyから算定。現行契約の月額設定を維持、新契約は既存標準月額を使用。再契約の初月料金は推測せず運営が確認した支払期間を使う。
削除前なら既存Userを利用。削除後なら新UUIDのUserを既存初回設定基盤で発行。本人password設定前は既存gateが保護する。初回設定処理は確認済みpaid-throughを上書きしない。メール変更でdigestが一致しない場合は自動照合しない。

### 初期購入証明

加算migration `product-final-retention-005`で次を追加。

|table/column|役割・参照|
|---|---|
|purchase_proofs|購入番号、Organization商品ID、購入日、支払確認、購入者emailのdigest、保持見直し日/根拠。User FKなし|
|purchase_links|現在のUserとproofを結ぶ。User削除でSET NULL、proofは残す|
|b2c_retention_status|運営が確認したB2C利用状態、確認日。未登録はunknown扱い|
|retained_records|User削除前に必要C/Dを独立保管する。同一内容の重複保管を抑制。再契約前のcontractは過去cycleとして保存|
|deletion_journal|成立したscope/User削除のUUID・日時。本文/対象者/認証情報なし|
|retention_origin|復元元DBを識別|
|service_contract_terms.cycle_id|再契約前後を区別する追加column。過去の利用開始日を推測しない|

同じproof/productだけ初期費用不要。異なるOrgの商品、本人digest不一致、他Userに使用中のproofは拒否。email digestの一致だけでは本人確認を完了しない。運営の購入証明・本人確認済み宣言を必須にしてauditする。

保持目的は同一商品の再契約・初期費用再徴収防止。アクセスはsingleton運営専用APIと外部保管担当。先生/生徒のAPIへdigest・購入台帳を返さない。購入者digestは匿名情報ではないため暗号化/access制限対象。
購入登録時に将来の保持見直し日を必須とした。契約/会計archiveは自動法定期間を付けずreview_pending（当日見直し対象）。運営が種類別の法令・再契約証明の必要性・不要PIIを確認し、根拠と次回日をaudited APIで記録する。無条件の永久保持にせず、不要情報の本番消去方式は法令確認後に別途実装する。

### A/B/C/Dと参照関係

- A：scope readings→reading_groups/persons。別Org/B2Cのsurvivorと共有するperson/groupは削除しない。外部source依存は拒否。
- B：users→auth_sessions/reset tokens、lifecycle/activity/initial_setup/profile、該当email digestのauth試行。Aの残存や未知FKはUser削除を止める。
- C/D：service_contract_terms/service_suspensions/manual_dues/user_service_contracts/memberships、および削除User自身がactorのauditを先にretained_recordsへ保存して参照を外す。purchase_proofsは最初からUser FKを持たない。
- 他actorのaudit.target_idはFKではない識別子として保持。契約・月額・入金は元record IDと記録内容を保存、会計報告をarchive行数で二重集計しない。
- 認証password/token、鑑定本文、対象者氏名/誕生日、memoをC/D archiveへコピーしない。

### 運営画面・API

既存Organization/User画面に購入証明登録・再契約・保持見直しとUserドライラン/B2C利用確認を追加。複雑な販売/課金dashboardは作っていない。先生画面には追加していない。
全 `/api/operations/` の既存server-side singleton認可・CSRF・no-storeを利用。購入証明やUser削除候補にも認可を追加。物理削除操作はAPI/画面に存在しない。

### Backup復元

最新snapshotの契約期限/cycle、immutable削除UUID、独立proof/C/Dをmanifestへexport。外部保管済み最新SHA256・originと照合するread-only previewを追加。
再契約/新契約の世代が古いDBと一致しない場合は拒否。scope削除→User削除の順、C/D保全、FK検査、エラー時全rollbackをmemory-onlyで検証。全session/reset token失効、最新scopeの契約state反映、最後に全User disabled。最新のidentity/契約確認が済むまで古い認証で再loginできない。
最新性はhashだけでは証明できない。最新checkpointをVPS外で認証された手順により保管・取得する本番adapterは未実装。古いbackupと同封の古いdigestは採用不可。詳細は`backup-retention-restore.md`。

## 4. テスト

開始baseline：Python isolated376/376、TierA524/524、TierB38/38、Node13/13。重要なbaseline failureなし。
追加final retention repository34件、実ASGI API8件は最終isolated suiteに含む（重複加算しない）。追加browser12件。

|最終確認|結果|
|---|---|
|Python isolated `*cases.py`|418/418成功（245.202秒）|
|Tier A|524/524成功|
|Tier B|38/38一致、review0|
|harness|16/16成功|
|Python合計|996件成功/一致|
|Node JST/reset link/execution request|13/13成功|
|既存browser billing/management/reset/history recovery|18+50+20+16=104件成功|
|追加browser purchase/retention|12/12成功、PC1280・スマホ375、対象画面の横overflowなし|
|TypeScript|`tsc --noEmit --incremental false`成功|
|Next.js production build|成功、13 static pages生成|
|移行rehearsal|合成pre-005 testDBで8既存tableの値が完全一致、integrity/FK正常、推測backfill0|
|backup rollback snapshot|SQLite backup APIでmemory copy、8既存table一致、integrity正常|
|source不変検査|128ファイル、テスト前後changes0|

ブラウザはlocalhost+mock、APIは合成User/tempDB、物理削除はmemory DBのみ。実SMTP、課金、production dataを使っていない。Windows/Ubuntu本番の実配備・実端末・実メール・正式Excel/PDFレイアウト検証とは区別する。
NodeのMODULE_TYPELESS_PACKAGE_JSON警告は既存のもの。依存やpackage設定を変更していない。
追加画面のPC/スマホスクリーンショットはtestの一時領域へ保存し、スマホ購入/再契約・User保持画面を目視確認した。
途中で復元のUser/Reading処理順の失敗を修正して再実行。既存billing browserのAPI待機不足は金額表示を待つよう変更し、判定内容を維持して18件成功。期待されたPDF converter異常のログは既存のfailure-pathテストによるもの。

## 5. Phase 10と保留

`phase10-test-plan.md`に13領域の総合計画、既知K01〜K06の重要度/解消要否、人間/外部設定一覧を記録した。K07と1975既知例外は採用baseline維持。
B2C終了後の保持/削除範囲、本人確認とメール変更時の運営証跡、会計種別法令/保持期間、不要PII消去・journal見直し、最新checkpoint外部保管、本番backup/復元executor/SMTP/本番導入は保留。Linux PDFはdisabledのまま。
main/既存branch変更、production VPS/DB/deploy/purge/実課金/実SMTP/backup設定/Notion変更は一切行っていない。S/Dと占術計算/解釈文言は変更していない。

## 6. commits・終了状態

- `7ac79de44fff576626f6e215eaca2e8542c60c8a` — Implement final user retention and independent purchase proofs
- `e688b4e26c7a8aeed734dfac304344e8af9ec111` — Add operator purchase and retention controls
- 本記録/backup runbook/Phase10計画を別のdocumentation commitで保存する。自身のcommit hashは循環参照となるため最終報告・Git logで確認する。

上記2機能commitの `origin/phase9-final-retention-20261009` への新規push成功。追跡branchを設定した。documentation commit後にも同じbranchだけをpushし、最終HEAD一致/staged0/untracked0/blob一致を確認する。
push直前のorigin main=`e8b53082775744a74f66502e8fb8f3cef72974c1`、旧branch=`31d2363de1ca3949cbdb489e245e0456cd889371`で開始時と一致。force push/main mergeは行っていない。
最終作業状態は最終報告を参照する。
