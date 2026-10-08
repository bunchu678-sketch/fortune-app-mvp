# Phase 9 確定仕様実装（2026-10-08 JST）

## 開始と適用仕様
正本fortune-app-public。開始branch phase8-9-overnight-20261007 / HEAD 76165c328d2f6bcc4ac8062d06419d2b9dad0a2f。
新branch phase9-confirmed-20261008。開始staged/untracked0、tracked142/142 hash一致。
今回のユーザー指示を適用。以前の特定日時全面廃止方針は更新され、B2C維持・B2B採用保留・共通処理維持とする。
運営主体しぜんとらぼ、サービスブランド博士の占いらぼ。先生は販売者/発行者ではない。
共通AGENTS v1.3確認、正本に個別AGENTSなし。関連Notion roadmap/管理機能検索を参照、今回10/8の販売仕様に一致する記録は検索で取得できず、最新の明示指示を根拠とする。Notion更新なし。

## Baseline
Python Tier A524/B38、既存isolated262、harness16 =840 PASS。既知Tier C6件は前回同様。
既存data DB、本番、D/Sの変更なし。テストは一時DBと合成利用者のみ。

## Unit 1 商品運営・契約・入金・初回設定
既存ProductRepository/AuthRepository/PasswordResetRepositoryを再利用。既存メソッドへtransaction connectionを渡せるよう拡張し、重要変更とauditを同一transactionで保存。
追加tables: 運営管理者singleton、最小User氏名、User-Organization利用契約、手動未納記録、内容を含めない操作監査、初回password設定待機。
先生提携契約（既存contracts）と生徒利用契約を分離。先生契約停止/終了は生徒contextに影響しない。
管理者はCLIで既存Userを明示指定する1名のみ。自動付与/一般登録/管理者招待なし。今回CLIは本物DBに実行しない。
発行は入金確認trueが必須。推測不能な内部passwordを生成し、本人の既存30分single-use resetで設定完了するまでloginを拒否。平文password/tokenを管理画面に返さない。
未納記録は全額精算時のみ解消。未納1件でも再開拒否、休止中に新しい月額債務を記録しない。再開後2暦月の最低契約期間を保存（自動請求/解約は未実装）。価格は入力データで、共通ロジックに販売額/報酬率等を固定しない。
猶予2暦月・督促14日間隔のpure previewのみ。起算日/初月料金未確定なので自動実行しない。休止一年+pending30日は既存実装を維持、物理削除なし。
検証: operations21、auth44、lifecycle12、product foundation19、reset22 PASS。

## Unit 2 成功鑑定回数・認可済みAPI
成功した新規API鑑定をledgerへ記録。未保存も1件、失敗/履歴閲覧/memo/復旧は0件。UUID実行IDの同一owner+scope再送は1件、条件違いでIDを使い回すと409。過去の保存履歴を実行回数にbackfillしない。計測開始以後の件数。
ledgerにはowner/org/日時/ID hash/ランダム鍵付き条件照合MACのみ保存、名前/生年月日/相談文/鑑定本文なし。JST月境界集計。B2CとB2B scopeを分け、teacher本人をOrg合計に含める。
既存B2C anonymous経路はDB不要のまま。認証cookie付きは失効/停止を拒否。B2Bは必ずsession+有効Membership+生徒利用契約/入金を照合。Host/header/body自己申告では認可しない。先生契約の状態は利用権限に使わない。
本人summary、先生専用allowlist（生徒氏名/状態とOrg合計のみ）、運営のcontent-free管理APIを分離。運営権限をすべての管理APIの処理前に確認し、mail設定等の処理より先に403で拒否。
Org付き履歴保存はMembershipを再検査し、履歴+scopeを同じtransactionで保存。既存B2C snapshot/ユーザーID/owner認可は維持。
初回設定mailは既存resetサービスを明示設定した場合のみqueue。未設定なら発行済みpending状態とmail disabledを返す。実送信なし。
検証: execution15、実ASGI product API21、auth44/history32/recovery12/Excel46/PDF21/product UI9/deploy20 PASS。
最初の全APIテストでmail設定の処理が認可より先に実行され、先生への拒否が503となる順序問題を発見。管理API共通の先行認可を追加し、全21件を再実行してPASS。

## Unit 3 JST暦月の保持・猶予計算
明示された支払期日/再開日時をJSTの暦月に変換してから2か月を加算。JST1/31 00:00をUTCへ先に変換して1/30基準で計算するずれを防止。月末/うるう年を含めoperations22/22 PASS。previewのみで請求/休止/督促を実行しない。

## Unit 4 マイページ・先生画面・運営3階層・B2BのW再利用
追加routes: /mypage、/teacher/[organizationId]、/operations、/operations/organizations/[organizationId]、/operations/users/[userId]、/b2b/[organizationId]。
生徒は既存/historyと/deletedを再利用し、自分の実行回数・現在の保存件数・mail表示・reset導線を提供。先生は生徒氏名/状態とOrg今月/累計のみ、個別回数・個別日時・生徒履歴リンク・発行/停止操作なし。自分の履歴/回数はマイページへ。
運営はOrganization作成/表示名/logo参照変更、User氏名/所属/手動発行/停止/再開/未納/精算、最終login/最終実行/回数、重要操作auditを表示。本文/鑑定対象者の詳細は取得しない。
B2Bは正規W MainFortuneを再利用し、APIでsession+Membership+利用契約を再検査。保存/詳細/再鑑定でOrgを維持し、別Org source転用を拒否。既存snapshotは変更しない。
B2CのURL/認証/履歴/特定日時計算を維持。B2Bの特定日時は採用保留なので新画面では有効化せず、APIでも要求を拒否する。共通Python/S/Dは削除・変更しない。
UI実行IDはネットワーク再送/同条件の境界確認再送で維持し、成功終了後の新規操作で更新。同じ条件の自動preview再計算は加算しない。前後選択など条件が変わる正常API鑑定は別実行として計上する。
B2C旧clientにはID省略を許容（各成功callは新規扱い）、新WとB2BはIDを送る。匿名B2CはUserがないためUser利用統計に記録しない。過去の未保存実行回数は再構成できず、表示は導入以後のledger件数である。
検証: product API24/history32/recovery12/product UI9、Node実行ID4+既存9 PASS。PC1280/mobile375の管理/B2B50項目、既存reset20/復旧16 PASS。TypeScript/Next production build PASS。合成画面画像を目視し、はみ出し/欠落なし、一時UIサーバー3ports停止確認。
最終回帰でB2C特定日時の既存異常入力500応答が422へ変わる差を検出。B2C calculation例外は既存response contractを保持して再実行し、Tier A524/B38 matched、fixture変更なし。

## 確定仕様との対応・未実装範囲

| 指示 | 対応 | 安全な未実装状態 |
|---|---|---|
| 1 正本/branch | 開始照合、別branchで38ファイル（既存16/新規22） | main/夜間branchを更新しない |
| 2 architecture | しぜんとらぼ運営、ブランド分離、既存User/Membership活用、先生/生徒契約分離 | DNS/ホストrouting/旧data一括Org割当は実施しない |
| 3 生徒mypage | 自分の履歴/復旧、実行回数/保存件数、mail/既存reset/logout | 自由登録・独自account体系なし |
| 4 先生管理 | 所属Orgの生徒氏名/状態と組織合計、自分の履歴/回数導線 | 生徒別数量/日時/本文/発行/停止/他Org不可、販売dashなし |
| 5 運営管理 | 明示設定1名、Org/User管理、手動発行/所属/状態/日時/件数/audit | 複数管理者追加/招待/他人の本文閲覧なし |
| 6 件数 | 成功新規計算ledger、未保存含む、同ID再送dedup、JST、別saved指標 | 過去の未保存成功件数を捏造/backfillしない |
| 7 初回設定 | 入金確認、内部random password、本人reset30分single use、session失効 | 本物SMTP/credentialなし、未設定mail disabled |
| 8 販売条件 | 利用契約/初期入金bool/monthly_feeのみ | 250000/125000/15000等は別台帳、8名discount枠/回収目標/50:50を自動適用しない |
| 9 未納休止 | 手動未納/全額精算/再開拒否/再開2暦月記録、猶予/督促preview、既存一年+30日 | 請求起算/初月/正式解約未確定、請求/自動休止/督促/物理削除schedulerなし |
| 10 security | session owner、Org membership/契約照合、teacher専用projection、operator API権限、audit、B2C回帰 | host/body/URLのみの信用なし、本番data操作なし |
| 11 検証/Git | 全回帰/型/build/UI、機能commit、作業branchだけpush | merge/deploy/本番migration/実mail/課金なし |

## 最終検証

| suite | 結果 |
|---|---|
| 正式Tier A / 観測Tier B | 524/524 + 38/38、REVIEW0 |
| 既存isolated suites | 262/262 |
| 新規operations / execution / product API | 22/22 + 15/15 + 24/24 |
| isolated全体一括run | 323/323 |
| harness | 16/16 |
| Python計 | 901/901（baseline840から61増） |
| Node JST / reset token / execution IDs | 5/5 + 4/4 + 4/4 =13/13 |
| 新管理・B2B PC/mobile / 既存reset / 既存recovery | 50/50 + 20/20 + 16/16 =86/86 |
| TypeScript --noEmit --incremental false | PASS |
| Next.js production build | PASS（新routesを含む） |

計1000件/項目PASS。OS一時領域の画像を目視確認。UIは全API mock、securityは実ASGI+一時SQLiteで別検証。実SMTP/本番smoke/native COM PDF E2E/S任意1325-input比較は実行していない。既知Tier C6件と1975啓蟄の採用済み差は前回同様で、fixture/占術期待値を変更しない。

## 保全と開始方法
全追加DDLはmigration台帳付き、既存users列/CHECK/UUID/履歴snapshot保持。追加keys: auth-initial-setup-003、product-operations-002、product-executions-003。DB accessはrepository/auth_schemaに局所化しUI/占術へSQLを入れない。sqlite3/SQL dialect依存は将来adapter変更が必要。
既存B2C / と /result /history /auth API を保持。B2Bは /b2b/<所属Org UUID> から開始、本人の /mypage から所属先へ移動できる。URLのOrg IDは選択入力だけであり、APIで照合する。サブドメイン割当は別工程。
運営権限は初期empty。レビュー済み既存local DBに対してのみ scripts/bootstrap_operator.py --database <明示DB> --user-id <既存active User UUID> --confirm で1名を指定できる。今回本物DBには実行していない。初期運営User/実Org/実生徒のseedはしない。初回mail接続にはapp.state.password_reset_serviceへ同じDB・trusted origin・承認済みMailTransportを持つ既存serviceを明示設定する必要がある（今回未設定）。
正式fortune_service/core/calendar/gogyou/大運/月運/年運/説明/特定日時Python/承認Excel/template/app.py/S/Dは開始blobと一致。新規feature gatingと計測・authの接続だけ。既存local data DB/本番DB/VPS/secret/環境設定/Notionを変更しない。一時test DB/build cacheのみ生成。一時ports3109/3110/3112は停止確認済み。global/project指示の未解決衝突なし。

## 次の人間判断・Phase 11
1. 請求起算日・初月料金・正式解約後の保持/削除対象と期間を確定する。原則2か月の例外運用/日割り返金の個別判断は自動化しない。
2. 実Org/既存Userの所属・先生role・運営管理者に指定する実Userを確認する。旧履歴をOrgへ一括backfillしない。
3. B2B特定日時の採用/廃止/再設計、テーマHEX/ロゴ等は別判断。本物の販売/入金/紹介料は別台帳。
4. 本番配備前にbackup/rollback/追加migration/既存利用者の回帰をレビュー。main merge/deployは別の明示許可後のみ。
5. Xserver SMTP/trusted reset origin/credential/送信確認、subdomain DNS/SSL/nginx、請求・休止・督促scheduler、日次30日backup/VPS外backup、physical purgeはPhase11以降。設定/判断が整うまで全て無効。

## Commitと終了確認

```text
f1bc409 Add audited operator and independent student contract foundations
58e9ebb Count successful executions and enforce product API permissions
1e9cf63 Preserve JST calendar months in arrears and resume previews
5507dd3 Add scoped B2B workspaces and student teacher operator screens
```

この最終記録は Record confirmed Phase 9 verification and handoff として別commitする。自己hashは最終チャット報告参照。commit後に全trackedをindex/worktreeで直接照合し、origin/phase9-confirmed-20261008だけへ通常pushする。push結果/remote HEAD一致は最終報告で確認する。
