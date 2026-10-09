# 本番バックアップ・削除整合性の導入手順（Phase 11承認前）

## 確定方針と調査範囲

2026-10-09のユーザー指示：1日1回、VPS外保存、30日保持、暗号化、アクセス制限、期限経過後自動削除。削除済みデータを復元によって復活させない。
今回はrepository内の`docs/vps-deployment.md`、認証・契約・履歴schemaのみを調査した。VPSへの接続、backup作成、保存先契約、設定変更は行っていない。
既存資料の構成はUbuntu / nginx / API / Next.js、DB `/var/lib/fortune-app/history.sqlite3`、DB directory0700/file0600。これは資料に記録された状態であり、現在の本番を再確認した結果ではない。
2026-10-06配備前のSQLite backup APIによる整合コピーとrollback記録はある。日次VPS外30日運用の配備記録はない。

## 本番前に決める設定

- 保存先、契約主体・管理者、アクセス権（運営のみ）、通信・保存時暗号化、鍵の保管・復旧責任者。鍵はbackupと別管理、Gitには保存しない。
- 1日1回のJST実行時間、監視・失敗通知、30日経過オブジェクトの削除設定。versioning、削除マーカー、複製先にも30日ルールが適用されることを確認する。
- 削除・契約変更に合わせて最新の削除整合性情報とC/D保管記録をVPS外へ保全する手順。日次の古いDBコピーだけでは足りない。
- 購入証明・法令上保持するC/Dは、鑑定backupの30日rotationとは別の保持方針を持つ。種類・根拠・見直し日を確認する。法定年数は未確認のままコードへ固定しない。
- 物理削除の本番executor、認可・dry-run承認・監査・再実行対策。今回はmemory-only fixture以外のexecutorは存在しない。

## 整合した取得と30日rotation

1. 本番導入承認後に対象HEAD・DB絶対path・復旧地点を固定。バックアップ担当の権限を最小化する。
2. 既存配備手順のSQLite backup APIを使用。WAL環境で本体だけをcpしない。`integrity_check` / `foreign_key_check` / サイズ・hashを確認。
3. 暗号化してVPS外へ送る。認証情報、reset token、平文passwordをmanifestやログへ出さない。原本DB自体は個人情報・認証情報を含むため必ず保護する。
4. 外部保存先から検証し、取得日時・checksum・復元テスト結果だけを運営記録へ残す。
5. 30日を過ぎたbackupを自動削除する設定を本番で検証する。期限前のcopy・snapshot・versionも一覧確認する。production timerやcredentialは今回設定していない。

## 削除要求を復元後に再適用する仕組み

`RetentionRepository.restore_manifest`は1つのDB読み取りsnapshotから、契約の保持期限・cycle_id、削除済みReading/UserのUUID、独立購入証明、保管C/Dをexportする。鑑定本文、対象者、password、tokenを含めない。購入者のemail digestや旧User UUIDは匿名情報ではなく、これらの情報も暗号化・アクセス制限する。

- `deletion_journal`は削除が成立したUUIDを保存する。再契約時も成立済み物理削除を取り消さない。
- 正式解約・休止の期限は最新契約snapshotから再計算する。復旧のみでは期限が変わらない。
- 再契約はcycle_idが変わる。古いDBと最新契約の世代が異なる場合は復旧を停止し、最新の契約/アカウント記録と照合する。古いpasswordや利用権を自動で復活させない。
- `restore_preview`はread-only。外部で独立保管した**最新**manifestのSHA256を渡し、origin・内容を照合する。同じ古いbackupに入っていたhashを「最新」として使ってはいけない。hash自体は署名や最新性の証明ではない。外部の認証された保管・取得記録・最終変更との照合を必須にする。
- 最新manifest/信頼できるcheckpointが欠落、不明、古い場合はサービスを再開しない。最新の契約/購入/C/Dの完全性も確認する。
- `apply_restore_memory_fixture`はin-memory DBに限定。全session・reset token失効、契約state復元、期限満了scope処理、Reading削除情報→User削除情報の順で適用し、必要なC/Dは認証データと独立して保持する。依存関係・FK異常なら全transactionをrollback。処理後は全Userをdisabledにして旧認証での再loginも停止する。最新identity/契約を人間が照合するまでは利用再開しない。
- 削除履歴には`review_after=削除成立+30日`を保存する。これは無条件消去日ではない。古いbackup・version・一時copyの消去と必要な契約/会計保持を確認後に最小化/消去する。自動journal消去は未実装。

## 隔離復元の検証手順

1. Web/APIを公開しない隔離場所でbackupを復号。hash/integrity/FK確認。現行本番DBへ上書きしない。
2. 最新の外部保管manifest・checkpointを独立取得。origin、最終取得日、最後の契約/削除操作以降の完全性を運営が確認。
3. 最新C/Dと購入証明を照合。manifestが含むC/DはUser削除/再契約で独立保管された記録であり、まだUserに紐付いている全ての請求・契約変更を自動再構築する台帳ではない。現行契約・入金情報の最新copyも別途照合する。追加Organization・再契約・新Userは最新DB記録により解決する。UUID世代違いを推測で補完しない。
4. 削除ドライランで対象UUID、scope、source依存、B2C、別Orgを検査。人間の承認後の本番用実行方式は別工程で設計・検証する。
5. 期限/削除情報適用後、全sessionを失効させる。旧reset tokenも無効化する本番適用手順を検証し、再認証して権限を確認する。
6. 削除済みReading/Userが見えないこと、他Org/B2C/購入証明/C/Dが保持されること、recontractを古いbackupで巻き戻していないことを確認。
7. 台帳の確認、操作記録、PC/スマホ、Excel、SMTPなどPhase10項目を実行してから復帰承認。

## 未実装の本番工程

外部保存adapter、暗号化鍵、日次timer、30日削除設定、最新manifestの変更連動保存、認証されたcheckpoint取得、file DBへのpurge/replay、journal期限消去、C/Dの不要PII消去は未実装・未有効化。backupがあるだけで「削除後にも鑑定履歴を復旧できる」と表示しない。
