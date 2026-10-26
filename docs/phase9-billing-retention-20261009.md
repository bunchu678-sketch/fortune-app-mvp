# Phase 9 月額・休止・正式解約（2026-10-09 JST）

## 1. 開始・適用範囲
正本 fortune-app-public / W（Next.js + Python API）。
開始 phase9-confirmed-20261008 / 17a6e7ea44df1abac6885c20e76906d108fa30b0。
staged/untracked 0、tracked164/164をindex/filter適用Git blobで直接照合。通常status/diffの環境異常は再調査しない。
新branch phase9-billing-retention-20261009。既存branch/mainを更新しない。
共通AGENTS v1.3確認、正本に個別AGENTSなし。最新明示指示によるローカル実装・tests・commit・当該branch pushだけ。
Notion関連検索と判断ログ「fortune-app 商品版の認証・データ保持・将来展開の基本仕様を確定する」を読み取り。
古い停止30日削除の記載は、その後の明示指示（休止1年+30日／正式解約後30日）に更新されているため最新指示を適用。Notion更新なし。未解決の指示衝突なし。

## 2. 再利用と変更
既存OperationsRepositoryのsingleton運営認可・atomic audit・手動未納/全額精算、ProductRepositoryのOrg/Membership、Auth/初回設定/PasswordResetRepository、HistoryRepositoryのowner認可、既存管理UIを再利用。
追加migration product-billing-retention-004は service_contract_terms / service_suspensions とindexだけ。既存User/契約/履歴の行を初期化・推測backfillしない。
SQL・SQLiteはrepository層に局所化。新規service_contract_repository.pyと既存billing_policy.pyで日時/stateを計算し、backend/product_api.py経由で操作。占術計算/説明/承認template/S/Dは変更しない。

## 3. 確定仕様との対応

| 指示 | 実装 |
|---|---|
| 初月購入代金に含む／翌月1日起算／2000円 | JST初月末を初期支払済み期間とし、翌月1日がfirst billing。以後毎月1日。日割り計算なし。契約別monthly_feeを維持し、新規未設定時だけ2000円を既定値にする |
| 実際の有効化日／旧利用者推測禁止 | 新規発行した対象だけ本人の初回設定完了時に同一transactionで記録。既存ready Userへの新規API利用権付与も実イベント日時を記録。既存所属の再保存/通常password変更では補完しない。日付未設定の旧契約は運営の明示確認だけで現在日時を登録し、過去日付を入力するAPIなし |
| 二重請求防止／休止月の追加料金なし | first month・支払済み月・将来期日を未納として記録する操作を拒否。next billingは初回/現在/支払済み末日/再開後の有効anchorを照合。保存した休止区間の起算日を再開後にさかのぼって未納登録することも拒否 |
| 未納猶予2暦月／14日督促 | 既存manual_duesの未精算・手動確認日時だけでpreview。11/1→1/1が判定境界。未確認/未来期日を未払いとみなさない。last_reminded_atを受け取る既存pure policyを再利用。定期処理・送信なし |
| 休止1年+pending30日／精算・2か月継続 | OrganizationとUserの利用契約単位でsuspend/resume。全額未精算が1件でも当該契約の再開拒否。別Orgの債務でこの契約を自動停止しない。1暦年はJSTで計算、経過後pending相当と30日期限を算定。再開は1年未満のみ、最低2暦月を記録。休止日時は重複操作で延長しない |
| 正式解約受付 | 本人申請/運営受付をaudit。同じ申請はidempotent。支払済み期間不明なら受付だけ・終了日未確定。確認済み期間末日の翌日JST00:00をexclusive終了日時にする。既に過ぎた支払末日は受付時点より前へ終了・削除期限をさかのぼらせない |
| 30日保持／本人復旧／利用再開と分離 | 終了時点から30日、deadline直前まで復旧可能、deadlineちょうどは不可。終了後の通常履歴/検索/メモ/再鑑定/保存履歴exportを隠す。本人のdata-recoveryで内容を復旧できるが、終了日時・利用権・未納・resumed_atは変更しない |
| 複数Org・B2C保護 | session Userを維持し、対象Orgだけの状態を認可。新規B2B計算/保存も期限を検査。B2C/unscoped/別Org履歴は維持。先生との提携契約を生徒の利用権に依存させない |
| 削除対象・整合性・dry run | 運営専用で対象reading ID/外部source参照/期限を列挙。共有Person/Groupは他のreadingが残るなら保持。外部readingが削除対象をsourceに持つ場合は削除block。FK整合性を検査。会計/入金/契約/Membership/管理audit/User本体は保持 |
| 画面と権限 | マイページに本人契約/解約/復旧、運営User詳細に契約ごとの開始/次回請求/支払済み末日/休止/終了/削除予定/未納preview/dry runを追加。先生には従来の氏名・最小状態・Org合計だけ。金融/解約詳細を返さない。重要変更は同一transactionでaudit |

next billingは将来の起算日previewであり、請求書生成・料金徴収・過去分invoice生成を行わない。再開時に過ぎている休止月の1日分を後から請求しない。再開手数料なし。原則2か月・原則日割り返金なしの例外は自動判断しない。

## 4. 物理削除の安全境界と保留
物理削除UI/API/CLI/schedulerなし。purge_memory_fixtureは実DB fileやattached file、foreign_keys無効を拒否し、in-memory fixtureでだけ実際の削除順とFKを検証する。
これにより今回、永続DBから利用者の鑑定データを削除できる実行経路は追加していない。
対象readingとscope、対象だけが使うPerson/Group、当該Orgの個人execution ledgerを削除する試験。共有データ、別Org、B2C、User、契約/入金/未納/監査は保持する。
外部source参照がある場合、参照元を勝手に変更・削除しない。保全して人間確認へ送る。

人間確認が必要な事項：
1. 正式解約後の再契約条件・購入費の再徴収。自動利用再開なし。
2. 本人がデータ復旧した後、利用再開しない場合の次の保持期限。未確定なので明示deletion_holdを置き、自動再削除しない。元の期限も表示してholdを併記する。
3. 単独契約Userのemail/profile等グローバル個人情報の削除と、会計/監査ID保持の法令・運用方針。User本体は常に削除対象外。複数Org/B2Cがないと推測して削除しない。
4. 外部source/shared Person/Groupを含む削除対象レビュー、バックアップ内データ保持/消去、復旧期限、監査・会計保存期間、本番migration/rollback。
5. 原則2か月の例外解約・返金。最低期間より前の終了は確認が必要として拒否。請求/決済の複雑なUIなし。

従来のアカウント全体の停止・再開はセキュリティ管理操作として維持し、全所属/B2Cへ影響することを画面で明示。通常のB2B休止は新しい「この契約を休止/再開」を使用する。旧global suspensionの日付を新しいOrg契約に推測コピーしない。

## 5. 検証記録
baseline: isolated323/323、正式Tier A524/524・Tier B38/38、Node13/13。Tier C既知6件と、別途1975啓蟄の採用済み例外を変更しない。
追加billing_retention42件（policy10+repository32）、billing API11件。追加UI18項目（PC1280/スマホ375）。
関連targeted: Operations22、Product foundation19、Execution15、Password reset22、Auth44、History32、Recovery12、既存Product API24すべてPASS。
検証中に初回設定待ちの運営有効化を拒否する不足を検出し、修正して再試験PASS。時刻mockと認可clockの接続差も修正して実APIテストPASS。テスト名product_cases.pyは存在せず0件となったため、その結果はPASS計数に含めず、正しいproduct_foundation_cases.py19件を実行済み。
最終PC/スマホ: 追加18+既存管理/B2B50+reset20+history recovery16=104/104 PASS。全API mock。サーバー側securityは実ASGI+一時SQLiteで別に検証。スクリーンショット目視で欠落/横はみ出しなし。
TypeScript --noEmit --incremental false / Next.js production build PASS。Node13件PASS。最終isolated376/376（既存323+追加53）、Tier A524/524・Tier B38/38、harness16/16、Python計954/954 PASS。実行中source hash123files/変更0。Node13+UI104を合わせて1071件/項目PASS。
SMTP/本番smoke/本物Excel COM/native PDF E2E/任意S比較は実施していない。PDFは既存fake converter回帰で検証。

## 6. 保存・本番不変
実装単位でbackend / UI / 記録を別commit。

```text
d1d891fd03c1b96dcb82ac2c2764f033323b805a Add scoped billing suspension and cancellation retention policies
10d09a47132204d863c96be6e51a6635bfc5ee9c Add student cancellation and operator contract controls
```

この記録は Record billing retention verification and deployment gates として別commitする。自己hash/push結果は最終チャット報告参照。
tracked変更9ファイル+新規6ファイル（docs含む）=15ファイル。対象外の正式計算/説明/Excel template/S/Dは開始blobと一致。テスト用port3109/3110/3112/3113の待受0をGet-NetTCPConnectionで確認。
main mergeなし、既存branch変更なし、production VPS/DB migration/停止/削除/請求/SMTP/credential/DNS/設定/Notion変更なし。
DBテストは一時SQLiteまたはmemory。ブラウザはlocalhost/mock。追跡外build cacheとOS一時screenshotsのみ生成。next-env.d.tsは前後bytes復元。
本番の請求・自動休止・督促・物理削除scheduler、Xserver SMTP接続はすべて無効。

## 7. Phase 10前とPhase 11
Phase10前：上記未確定の再契約/復旧後保持/例外運用を確認し、実Organization別の契約・支払末日・既存利用資格日を人間が照合する。旧履歴をOrgへ一括割当しない。
本番前：dry-run対象レビュー、複数Org/B2C保護、backupの保持・削除・復旧、会計/監査法令保持、本番追加migration+restore手順を確認。
Phase11：承認後のmain統合/配備、SMTP credential・trusted origin・送信確認、請求/手動入金運用とscheduler、自動休止、日次30日backup/VPS外backup、physical purgeの実行方式。
