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
