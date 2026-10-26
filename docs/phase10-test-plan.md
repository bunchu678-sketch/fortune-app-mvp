# Phase 10 総合テスト計画

作成日2026-10-09。対象はW（Next.js/Python）、比較元`phase9-billing-retention-20261009` / `31d2363`。本書はテスト計画であり本番配備承認ではない。

## 実施順と判定

|順|対象|方法と合格条件|今回の確認/残る工程|
|---|---|---|---|
|1|baseline/計算|Tier A/B、harness、五行A/B/C・立春・節入り・性別/大運欠落・年間/月間・再鑑定|既存suiteを実行。占術コード/解釈変更なし。Tier Cは別表|
|2|認証/B2C|既存login/session/Argon2id、User spoof、履歴・memo・再鑑定owner認可、B2C所属不要、特定日時維持|実ASGI/tempDBで回帰。実B2C利用者での本番操作は禁止|
|3|B2B/Org分離|Org ID・host・body偽装、他Org鑑定/保存/Excel/PDF禁止。部分解約でも他Org/B2C保持|実ASGIとmemory fixture。先生提携終了が生徒契約へ波及しない|
|4|3種類の画面/権限|生徒は本人だけ、先生は名前/状態とOrg合計だけ、運営も通常鑑定本文不可|API exact key whitelist＋PC1280/スマホ375のmock browser。人間の実端末確認を追加|
|5|Org管理/初回発行|運営singletonのみ、手動入金後発行、passwordは本人設定、重要操作audit|既存基盤再利用。初回token mock、mail disabled。本番SMTPは承認後|
|6|reset/メール|30分single-use/hash、enumeration防止、password更新session失効、初回設定との整合|既存Python/Node/browser。復元時は旧reset token失効も本番方式を検証|
|7|鑑定回数|成功した新規実行のみ、未保存加算、再送idempotency、memo/履歴再表示非加算、JST月|既存execution suite。先生APIから個別回数/日時が漏れない|
|8|請求/休止|初月含む、翌月1日、2か月猶予/3か月目、confirmed未納のみ、2週間督促、停止中課金なし|既存billing suite。月末/2月/閏年/年跨ぎ/JST境界。scheduler/送信無効|
|9|解約/復旧/削除|払済み末日+30日、休止1年+30日、復旧のみ期限維持、再契約だけ予定取消|新final retention＋既存billing。memory-only purge、fileDB/API purge拒否|
|10|User/購入/C/D|全Org期限満了+B2C保護、auth参照整理、購入証明残存、同商品免除/別商品不免除、法定記録保護|UUID/FK/unknown dependency拒否。B2C終了時保持方針は人間確認|
|11|Excel/PDF|承認template・完成Excel共通処理、owner、未保存token、WindowsCOM、disabled Linux503|既存export/PDF suite。実Excel/WindowsPDFレイアウトは人間確認。Linuxconverter未実装|
|12|migration/backup/rollback|実data相当の隔離copyで追加migration、integrity/FK/fingerprint、旧schema復旧、削除再適用|memory fixtures実行。実本番copyによる移行/復旧は承認後。backup runbook参照|
|13|build/PC/スマホ|TS/production build、既存browser＋新画面、入力/エラー/横overflow|localhost mockを実行。実認証と実SMTPを組み合わせるE2Eは別工程|

Phase10完了条件：blockingの全回帰成功、重要既知課題の採用判断/修正、実端末と正式Excelの確認、本番前の人間判断一覧の解消、隔離migration/restoreの証跡。今回は本番環境での確認を実施していない。

## 既知の注意事項6件（Tier C、今回変更なし）

|ID|内容|評価・優先度|解消/確認方針|
|---|---|---|---|
|K01|2027要求でも2026向け解釈文を含む可能性|高：商品表示年と説明不一致|2027商品利用前に先生承認文言/仕様を確定。占術コメントを今回創作しない|
|K02|特定日時のUI候補上限3、APIは4処理可能|中：UI/API仕様差|B2C現行維持。採用/上限の整合方針を決める。B2B採用は引き続き保留|
|K03|非表示の鑑定者向けprivate項目がAPIに含まれる|高：商品公開範囲の確認が必要|他User漏洩とは別問題。誰へ返すべきかを確定し、承認されたprojectionで修正後API検証|
|K04|2050の月運で翌1月2051が対応範囲外|中：対応年上限の端点不整合|対応年範囲/画面表示/計算方針を確定して境界test。無断で暦範囲を拡張しない|
|K05|S/WのSVG・異常干支・節入り・空亡・日時・private表示差|中：表示回帰確認|Wの正式仕様として差分をPC/実スマホで人間確認。S/Dは変更しない|
|K06|2021資料23:58と採用engine23:59の差|参照注意：採用baselineを維持|資料の確度と正式基準を先生/人間が確認。独断で計算を戻さない|

K07は解消済みでTier AのOFF隔離guardを維持。1975啓蟄の資料14:08/採用14:06の2分差は別の既知例外で、今回変更なし。

## 人間判断・外部設定が必要な項目

1. K01/K03を中心とする商品公開範囲と承認文言、K02/K04/K05/K06の正式扱い。
2. B2C利用終了時の保持期限・消去範囲。未知/継続/未処理B2C記録があればUserは保護。
3. 購入者本人確認の証跡、メール変更時の照合、購入証明の保持見直し日/不要PII消去方針。メールdigest一致だけで本人認証を済ませない。
4. 会計/契約記録種類別の適用法令・保持根拠・見直し日。法定期間を推測で固定しない。
5. VPS外保存先、暗号化鍵、30日rotation、最新削除情報の独立保存、復元時の検証責任者/承認、本番purge executor。
6. Xserver SMTP credential/trusted origin/送信元・実送信確認、DNS/SSL等の本番設定、Linux PDF対応の採否。
7. 別承認のmain統合・本番追加migration・backup・rollback・配備。Phase10のlocal成功を本番導入済みと扱わない。
