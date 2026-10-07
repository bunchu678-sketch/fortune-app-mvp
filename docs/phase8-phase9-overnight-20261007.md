# Phase 8 / Phase 9 夜間監査・実装記録

作業日: 2026-10-08 JST。依頼・branch名はユーザー指定の20261007を維持。
正本: C:/Users/bunch/Documents/Codex/fortune-app-public
開始: main / e8b53082775744a74f66502e8fb8f3cef72974c1 = origin/main。
作業branch: phase8-9-overnight-20261007。main merge / origin/main push / 本番操作は禁止。

## 根拠・ルール

現セッションの夜間作業指示を最優先。global ~/.codex/AGENTS.md v1.3を確認、正本直下AGENTS.mdは存在しない。開発元AGENTS.mdの安全ルールも参照した。今回のbranch作成、追加実装、ローカルテスト、commit、夜間branchのみpushは明示許可済み。
Notionは参照のみ。ロードマップ 3e7f414e63af81ef96d4dbd4bc0e3c73、結果画面仕様 3e7f414e63af81c6a28cf941b175db41、五行A/B/C判断 3e8f414e63af810babd8de1374cbe9b7、Phase 6ブランド 3f2f414e63af81b0a490c5abce91c49aを確認。古い9/26の「停止後30日保持」は、今回明示の「停止1年間→削除待機30日」に置き換える。Notionは変更しない。
正規Wは / と /result。/product は9/27の参考プレビューであり、商品版の正規開発経路と誤認しない。S app.pyは参照・保険用。

## 開始検証 / baseline

直前の直接照合: tracked 121 / 比較121 / 一致121 / 不一致0 / 欠落0 / 特殊mode0。今回branch/HEAD/origin/main一致、staged/untrackedなしを再確認後、開始HEADから専用branchを作成した。git status / 通常git diffの環境異常は再調査していない。

| suite | baseline |
|---|---|
| tests/check.py Tier A | 524/524 |
| Tier B | 38/38、REVIEW 0 |
| auth_cases.py | 44/44 |
| history_cases.py | 32/32 |
| report_export_cases.py | 46/46 |
| report_pdf_cases.py | 21/21 |
| product_ui_cases.py | 9/9 |
| deploy_blocker_cases.py | 20/20 |
| predeploy_cases.py | 7/7 |
| test_harness.py | 16/16 |
| jst_default_date.test.mjs | 5/5 |
| TypeScript --noEmit --incremental false | PASS |

Python計757件、Node5件。PDFエラー系ログは期待した失敗をテストするもの。実Windows Excel→PDFの画面E2Eは今回baselineでは未実施。Tier C K01〜K06は既知非ブロッキング、K07 OFF隔離は解決済み。主要suiteは一時DB・合成利用者で実行、既存data/history.sqlite3や本番DBは使用しない。

## Phase 8 全体分類（開始時）

A=実装済み B=一部残件 C=未実装 D=確定仕様と競合 E=後工程。

| 確定要件 | 判定 | 現行コード / 残件 |
|---|---|---|
| Phase1任意入力・初期日付/時刻・時刻不明・JST鑑定日 | A | main-fortune.tsx、jst-date.ts、fortune_service.py |
| Phase2出生/鑑定節入り、自動+任意手動、snapshot記録 | A | fortune_service.py、calendar_reference.py、sekki_confirmation_cases.py |
| Phase3結果順序、空亡、縦型大運/月運、memo折りたたみ | A | main-fortune.tsx、globals.css |
| 五行A/B/C、年/大運の外部作用 | A | gogyo_variants.py、gogyou_external_effects.py、daiun_logic.py |
| 考え方help説明 | B | 操作導線あり、説明未設定。ユーザー/先生資料待ち。創作禁止 |
| 鑑定者向け支援文 | B | 未設定placeholderのみ、資料待ち。創作禁止 |
| 特定日時 商品版廃止 | D | 正規WとSに存在。商品専用境界未接続、共用部分は削除できない |
| 鑑定履歴DB/person/group/snapshot/list/search/detail/memo/re-reading | A | history_repository.py、history_service.py、history_api.py、history-controls.tsx |
| 論理削除 | A | deleted_at、通常list/detailから即時除外 |
| 30日復旧と物理削除 | C | restore/purgeなし。再鑑定source FKを考慮したpurgeが必要 |
| app/calculation/schema version snapshot | A | history_versions.py。DB migration台帳とは別 |
| 正式Excel | A | report_template.py、report_export_service.py、承認xlsx、限定XML更新 |
| Windows PDF / 共通完成Excel | A | report_pdf.py、pdf_converter.py、WindowsExcelPdfConverter |
| Linux PDF | B/E | converter未実装。本番disabledは正式既定、Excel利用可能。変換方式決定後実装/配備 |
| email/password、Argon2id、hash session、安全cookie、owner分離 | A | Phase7A auth_service.py、auth_api.py、auth.tsx。作り直し不要 |
| account発行CLI | A | scripts/manage_user.py。Web管理者画面とは別 |
| Organization/Membership/Contract | C | 未実装。既存users UUIDを利用する追加モデル |
| Org+owner scope | C | user ownerのみ。既存dataのOrg割当・routing決定待ち |
| active/suspended/deletion_pending | D | users.statusはactive/disabled、期限情報なし |
| 最終login/利用件数query | C | historyから保存件数算出可。未保存鑑定は永続記録なし |
| reset30分/single-use/hash/session失効 | C | reset機能なし |
| mail abstraction / SMTP adapter | C | 未実装。live送信/credentialはE |
| admin3階層 | C | 権限modelとbootstrap/Org割当が未確定 |
| Org brand/settings/theme/Membership theme保存 | C | 現行は博士の占い表示、Org設定なし |
| 商品subdomain / DNS / TLS / nginx | E | Phase11 |
| SQLite将来移行 | B | SQLはhistory/authに概ね局所化。schema/transaction/PRAGMAはSQLite依存 |
| 日次backup30日rotation/VPS外copy | E | 配備前backup/rollbackは実装docsで確認、定期運用はPhase11 |

## 8-2 特定日時の全依存監査と削除順

正規W: main-fortune.tsxのFortuneForm型32-33、default93-98、specificRows232、結果表示395前後、目次441、candidate state507/527、送信562、入力753-785。fortune_service.pyのimport39、normalize_specific_candidates284、計算517-522、API結果616。APIはserver.py POST /api/fortuneの共用経路で、独立特定日時endpointはない。
専用Python: specific_datetime_logic.pyの候補正規化、通変星コメントdictionary、日/時運組立、エラー組立。専用dataは同ファイル内。共有のcalendar_logic.calculate_day_pillar/calculate_hour_pillar、calendar_reference、fortune_core_logic.get_tsuhenseiは元命式・月運等も使うため残す。
S app.py import70、render1333、入力2418-2455、計算2660-2676、目次/出力2821-2906も参照。history_service.py:90は再鑑定時のOFF正規化、既存snapshotには旧keyが残り得る。
テスト: specific_datetime_guard.py（正式OFF6/観測ON2）、tier_a.py、tier_b.py schema/関数観測、tier_c.py K02、gogyou_year_effects.py非五行不変。textはtests/README.md。fixtureの全体schema観測も参照。
参考/product input/resultに特定日時UIなし。ただし共用API契約は残る。
安全な順: (1)商品contextとDoctor/S維持範囲決定 (2)商品request/type/UIからcandidate削除 (3)商品APIで特定日時拒否/返却除外 (4)旧snapshot表示方針を決定、再鑑定正規化 (5)商品テスト追加、Doctor/SのOFF/ON回帰維持 (6)全consumer廃止が明示された場合のみ専用module/data/専用testsの物理削除。共通暦・通変星関数は削除禁止。
夜間gate: 商品版だけ廃止する境界が未接続であり、共通moduleの物理削除は既存正式互換テスト/Sを壊す。全repoからの削除は保留。独立した商品基盤を進める。

## 8-3 考え方: 全分類・判定・key

fortune_core_logic.py:20-37のTHINKING_CATEGORY_DEFINITIONS/ORDERと181-205 build_thinking_chart_data。

| key | 分類名 | 全判定label / graph項目 |
|---|---|---|
| brain_type | 左脳／右脳 | 左脳、右脳 |
| merit_type | メリット型／デメリット型 | メリット型、デメリット型 |
| goal_type | 目標への向かい方 | 目標直進型、目標変化型 |
| principle_type | 原理原則型／応用拡大型 | 原理原則型、応用拡大型 |
| work_type | 仕事4分類 | 現場型攻め、現場型守り、管理型ムードメーカー、管理型アイデアマン |

fortune_data.py:324 JUUNI_UNSEI_THINKING_TENDENCYは長生/沐浴/冠帯/建禄/帝旺/衰/病/死/墓/絶/胎/養の12星mapping、three_group=地球/月/太陽も含むが現graph集計対象ではない。柱key year15/month30/day50/hour5を加算する。pillar_meanings keyが別途返る。fortune_data.py:430のlabel/title/subtitleは年柱/決断の時の自分/迷い・意思決定、月柱/社交の際の自分/手段・戦術・行動パターン、日柱/本当の自分/目的・戦略、時柱/将来の理想像/イメージ・動機。
main-fortune.tsx:167 ThinkingBarsは4分類の棒グラフPC2×2＋仕事4分類wide tiles、スマホ1列。全判定label横に?のclick/tapあり、説明は未設定。現graph・点数を変更しない。

## 8-4 月運

yearly_flow_logic.py:77 targets=鑑定日Gregorian年の2〜12月+翌1月。各月15日12:00代表日時→暦context→年柱→月柱→日干対月干の通変星→既存YEARLY_FLOW_TSUHENSEI_COMMENTSのkeyword/comment。月支が出生空亡に含まれるかを判定。
API fortune_service.py:506-512 / server.py:61 POST /api/fortune → yearly_flow {ok,base_year,rows,errors}。rowの月/年/月番号/代表日/月干支/天干/地支/通変星/keyword/comment/空亡/errorを監査。productAutoBoundary時include_periods=true、既存sekki_entriesからstart/start_term/end_exclusive/end_termを追加。
main-fortune.tsx:369付近は月名、節入り〜次節入り直前の対象期間、月干支、通変星、全文、keyword、空亡と凡例、2月→翌1月縦表示。現在月専用強調なし。代表日/内部天干地支は重複表示しない。tests/tier_b.py month schema/代表日呼出、product_ui_cases.py期間/順序を確認。2050→2051の翌1月は既知K04、範囲仕様判断待ち。

## 8-5 年総合運勢

yearly_overall_logic.py:5 YEARLY_OVERALL_COMMENTSは通変星別theme/comment。105 build_yearly_overall_fortuneは鑑定日yearの2/15代表日時で年干支、日干対年干の通変星を取得。API yearly_overall {ok,year,year_kanchi,tenkan,chishi,tsuhensei,theme,comment,error}。
main-fortune.tsx:389付近は年/年干支/通変星/theme/commentを月運直後に全文表示。tier_b.py call/schema観測、tier_c.py K01に2027鑑定でも文中2026が残る既知課題。新しい占術文を作る許可はないため書換え保留。

## 8-6 メモ

main-fortune.tsx:410-431 detailsはopenなし＝既定折りたたみ。上部支援情報2項目は未設定、現行点数= result.gogyo.details。sourceはgogyou_logic.calculate_gogyo_scoresの柱別天干/地支内訳（対象/干支/五行/点数/理由）、一般的な別鑑定点数ではない。年作用含む既存gogyoがsourceで、A/B/Cの3表を保存しているわけではない。
自由memoはstate-controlled textarea→history-controls.tsx save→history_service→readings.memo。保存済みmemoはowner限定更新+updated_at楽観lock。pastMemosは同じowner/groupの過去非空memo、再鑑定時だけ既存groupなら表示、別groupへcopyしない。
report_template/report_export側に支援文/memo/内部IDを出力しない契約とtests/report_export_cases.py/PDFで確認。

## 8-7 五行A/B/C

gogyo_variants.py:17は元meishikiを不変にA年作用OFF、B年作用ON、C年+選択大運をgogyou_external_effectsへ渡す。鑑定年/大運自体の直接点は0、命式内部関係の引き金として参加。
daiun_logic.py:418は鑑定日時点の満年齢、開始年齢数値<=age<=終了年齢数値で有効大運を選び既存干支を再利用。性別未入力/大運未取得/出生前/年齢範囲外はC unavailable、A/Bはavailable。立春判定pendingではA available、B/C boundary_pending。productの自動判定/任意上書き経路は既存W確認required経路との後方互換を維持。
main-fortune.tsx:286-299は3図常時、B鑑定年/C対象大運補足、pending/unavailable表示。frontend再計算なし。tests/gogyou_daiun_effects.py、gogyou_year_effects.py、product_ui_cases.py、sekki_confirmation_cases.py、Tier A524を維持。新しい占術競合ルールを決めない。

## 8-8 商品基盤追加の影響とgate

| 項目 | DB/repository/service | API/auth/session/frontend/routing/test/migration |
|---|---|---|
| Organization/Contract | UUID/TEXT PK、別table、contract state/date/plan | 導入先作成はexplicit operation。既存User/履歴Org割当は自動化しない |
| Membership | org/userの複合unique/FK、role、theme key | 複数org所属可。roleは権限付与として解釈しない。管理者権限/初期付与は判断待ち |
| Org context+owner | org+userを両方検証。scope map追加可 | session userだけ信頼、選択orgはMembership検証必須。旧履歴の一括backfill/routingは保留 |
| settings/theme | org display/logo reference/settings、org固有themeとMembership選択 | 白黒defaultだけ。未確定HEX/先生名/実logo/DNSを勝手に設定しない |
| lifecycle | legacy usersを維持する追加side table/期限判定 | authに停止状態検査、既存session revoke。実dataのpurge/schedulerなし |
| metrics | login時刻だけ追加、既存履歴から集計 | 未保存鑑定は永続記録されないので「保存鑑定件数」と明示、全鑑定件数trackingの仕様は保留 |
| reset/mail | hash token、30分、atomic single-use、password更新+session revoke | csrf/入力上限/共通response、fake transport。SMTP live wiringは保留 |
| admin | content-free stats queryは可能 | global admin権限・grant/bootstrapが未確定、通常Web管理API公開は保留 |

## 8-9 DB portability

history_repository.pyとauth_service.pyにSQL局所化、UI/占術logicにsqlite情報なし。歴史dataはUUID/TEXT PK、owner複合FK。auth_login_attemptsのINTEGER PKは内部rate-limit記録のみ、rowid/last_insert_rowidを業務判断に使用しない。
SQLite依存はsqlite3.Row/Error、? placeholders、PRAGMA foreign_keys、BEGIN IMMEDIATE、bootstrap CREATE TABLE/INDEX IF NOT EXISTS。connection helperは共通利用するがauth SQLは別adapter。postgres migrationではconnection/DDL/placeholder/transactionとtimestamp(JSON TEXT)型選定が必要。現在cloud DB移行は不要。新基盤のSQLもrepository/schema moduleへ局所化しmigration台帳を導入する。現snapshot data_schema_versionはDB migration番号とは別。
コード上schemaはhistory3+auth3。本番の6tables確認は配備docsの記録で、本番DBへは今回接続しない。正本local DBがhistory3のみでも本番状態の不一致とは断定しない。

## 8-10 保持・復旧・backup

現状active/disabledだけ、停止の開始時刻・一年判定・deletion_pendingなし。今回仕様はactive→suspended(一年保持)→deletion_pending(30日保持)→physical delete。pendingへ遅れて遷移した場合にも実際の待機開始から30日保持する必要がある。旧disabledに停止時刻を推測backfillしない。
履歴deleted_atで即時非表示は済み、30日復旧endpoint/UI/期限処理は残件。source_reading_id FKにより親履歴の物理削除が子を壊すため、source保持方針を設計してからpurge。application側は期限・復旧・purge候補のmodel/service/tests、Phase11はscheduler/backup/監視/本番migration/restore運用。日次backup+30日rotation+VPS外1系統はinfra後工程。

## 8-11 reset/SMTP

既存authへ追加可能。tokenはsecrets生成、SHA256だけDB保存、30分expiry、1回使用、password hash変更+全session失効をtransaction化。reset requestは存在/不在/停止で共通response、rate-limitはaccount/IPとも同等。mailは独立interface、SMTP AUTH/TLS adapterをfake SMTPで検証。origin/リンクはtrusted configから、Host headerを採用しない。再設定API/UIの接続はlive送信設定が未完でも安全な無効状態から提供可。secret/DNS/Xserver control panelには触れない。

## Phase 9 roadmap 再分類（開始時）

完了・再実装不要: history DB、保存/呼出/検索/詳細/再鑑定/memo/soft delete、正式Excel、WindowsPDF、login/auth/owner分離、app/calculation version保存。
一部残件: deletion復旧/purge、PDF Linux converter、help/支援文、ブランド画面。
今回の安全な実装対象: additive product基盤、lifecycle期限+auth接続、content-free保存件数query、reset token backend、mail interface/adapter、theme保存基盤。
判断保留: 商品専用特定日時廃止範囲、旧dataのOrg割当、管理者grant、全鑑定件数定義、占術文/先生資料、Linux PDF変換方式。
Phase11: production migration/deploy、subdomain DNS/TLS/nginx、SMTP credential/live送信、backup scheduler/offsite、purge scheduler。

## 実装・テスト・commit記録

以下に機能単位で追記する。baseline完了後にPhase9開始。

### Unit 1: account lifecycle / login activity

追加side tableとschema_migrations台帳を導入。既存users.statusのCHECK制約と既存UUIDを維持し、旧利用者やsnapshotを自動書換えしない。disable/enableはsuspended/activeへ明示同期、login/authenticateは追加状態も検査。最終loginだけ保存しlogin回数等は追跡しない。停止は暦の1年（2/29→翌2/28）、実際にdeletion_pendingへ遷移した日時から30日、purge候補IDの取得まで。物理削除/schedulerはなし。旧disabledで停止開始日時がない場合は推測しない。
Targeted account_lifecycle_cases 12/12、related auth44/44、history32/32 PASS。HEADとのauth差分をdifflibで確認、正式占術logicは未変更。

### Unit 2: Organization / Membership / Contract / theme / scoped adapter

追加tablesだけをexplicit ProductRepository初期化で作成。旧users UUID/履歴snapshot不変、旧履歴はunassignedのまま。複数Organization所属、role記録、Contract3状態/date/plan、logo/settings、Org固有theme、Membershipごとの選択保存。標準themeはwhite/blackのみ。Orgと元ownerの二重FKを持つexplicit reading scope mapでsame-orgの他userも別orgの同userも分離、1履歴を別Orgへ自動共有しない。既存history APIへの接続/backfillは未実施。roleは権限として解釈せず、Contract状態のaccess policyもこの基盤では未接続。
Targeted product_foundation_cases16/16、related history32/32、lifecycle12/12 PASS。新adapter全文とFK/query対象を確認。
