# Phase11 配備前準備・安全なローカル先行検証

2026-10-26夜間。VPS未接続、実DB/実メール/実請求/実アカウント発行なし。**本番実行手順の承認資料であり、今夜の配備許可ではない。** 対象HEADは夜間総合報告とbranchの実測を使う。

## A 配備と現在の稼働記録

最新の開発元`docs/security-vps-retry-20261023.md`による10/23時点のWebは、release HEAD bdc6de9、cwd `/opt/apps/fortune-security-preflight-20261023/release/fortune-next-app`、専用Node24.22.1/Next16.4.2/React19.3.1。90-security-20261023.confがNodeを絶対pathで選択。旧 `/opt/apps/fortune-app` HEAD569d149は退避資産。共通Nodeリンクの版だけで稼働版を判定しない。

10/26にGitHub mainは241dd57へ統合済み。今回のB2B候補とは別。GitHub main更新がVPSのcwdやsystemdを変えたと扱わない。本書の本番情報は過去の配備記録で、今夜の稼働実測ではない（現在のPID/cwd/設定/schemaは未確認）。

次回の明示承認後は、次の順で進める。どれかの検査が欠落/不一致なら切替しない。

1. 承認されたTARGET commitと既存release/設定のhashを固定。実効WorkingDirectory/ExecStart、現在プロセスの実体、Node/Next/React、API/nginxの設定、DBの絶対pathを読み取り確認。秘密値を出力しない。
2. 別release/専用runtimeでlock固定install/build。Linux上のTS/buildと合成回帰を先に完了。Windowsのnode_modules/.nextを配備しない。
3. 最新削除情報・契約/入金/C/Dと信頼checkpointの完全性、暗号化されたVPS外backup、復元検証、担当と復旧期限を確認。
4. 実DBを触らず隔離本番copyでmigration/復元を検証。本番への適用は対象/停止条件/backupを含め別の明示承認を受ける。
5. SMTP/URL/運営発行/監視/rollback方針が確定してから、公開範囲と停止時間を含めた切替を別承認。生徒/先生/運営・B2Cの最小疎通とOrg分離を確認し、短時間の継続観測を行う。

本番用の変更script/EnvironmentFile/サービス設定は今夜作成・配備していない。

## B DB migration

統合コードの合成旧版DBコピーで8確認を実施：SQLite backup API、旧6表の全行不変、追加25表、8 migration key、繰返し適用不変、integrity/FK、意図的DDL失敗のtransaction rollback、旧schema/dataへの隔離復旧、元ファイルhash不変。生のDBコピーやsidecar除外copyを本番backupとしない。

本番適用前には、現行schema/volume/SQLite版・worker/書込み状態を確認し、旧全行fingerprint・新列値・migration marker・owner/Org・既存B2Cの読取り・旧snapshot projectionを隔離copyで検証する。失敗時は新規書込みを止め、どの世代まで安全に復旧できるかを確認する。本番と同名のDBファイルを安易に作成/上書きしない。

## C backup/restore

確定方針は1日1回/VPS外/暗号化/30日/期限後自動削除/削除済み個人情報の復活防止。保存先・鍵・時刻・担当は未確定であり、本書から補完しない。

追加した`research/backup_restore_lab.py`は、引数でDBパスを受け取らず、新規tempディレクトリの専用合成DBだけを使う。環境のFORTUNE_HISTORY_DB_PATHを参照しない。snapshotは新規名で作り、登録済みの同一lab世代だけをhash/schema/migration/originで照合して`:memory:`へ戻す。既存DB/backupを指定するCLIやファイルへのrestore/purgeは存在しない。

`tests/backup_restore_lab_cases.py`の17件：open writer下のWAL commit取得、未commit除外→commit後再取得、途中失敗後retry、hash破損/別世代/別schema/FK不正拒否、旧schema追加migration、DDL rollback、source/snapshot不変、削除期限/独立tombstone再適用、B2C保持、session/reset失効・全User停止、古いcheckpoint/契約cycle拒否、復元途中rollback、fileDB拒否。二度目の適用は全User停止により運営認可で拒否され、データは不変。ロック解除や再開を自動化しない。

これは本番backup製品ではない。暗号化・外部保管・署名/最新性保証は提供せず、lab snapshotのhashを信頼できる最新checkpointと誤認しない。最新manifest/独立台帳・取得時刻・最終契約/削除操作以降の完全性を別系統で確認できなければサービス再開を禁止する。30日後はDB本体以外にversion/snapshot/一時copy/replicaも対象。C/D保持とjournalのreview_afterは鑑定backup30日rotationとは別で、独断の自動消去を行わない。

本番用に未実装：外部storage adapter、暗号化と鍵回復、日次timer/失敗通知、30日rotation、変更連動の削除情報保全、独立checkpoint取得、fileDB executor、journal/C/Dの最小化。別承認・別実装が必要。

## D SMTP

既存MemoryMailTransport・SMTP factory mockを再実行。初回設定→login、30分期限、single-use、旧session/reset失効、STARTTLS/SSL・証明書検査・header注入拒否・secret repr/例外非開示を確認。追加2ケースでは初回配送失敗時のtoken失効/設定待ち維持、初回link期限切れ時のlogin/課金開始防止を検証する。実メールは送信していない。

初回発行APIのmail_status=queuedはbackground処理に受け付けた状態であり、配送完了の証拠ではない。失敗は一般化ログに残りtokenを失効させる。初回の契約行はactiveでもactivated_atがNULLかつawaiting_initial_setup=1で、設定完了までlogin/課金開始しない。表示名から契約実効状態を推測しない。

本番前の必要項目：送信元の採用、SMTP host/port/TLS方式、認証情報の安全な保管先と責任者、認証されたpublic origin/reset URL、DNS/SPF/DKIM/DMARC、到達性/迷惑メール/失敗通知/再送担当、許可recipientによる実送信試験の個別承認。秘密値はGit/Notionへ保存しない。実接続を可能にする設定変更はしていない。

## E Linux PDF

現行converterはWindows Excel COM方式とdisabled。Linuxではdisabledの503を維持し、Windowsで成功したことをLinux対応済みとしない。既存WSL一覧を確認したが利用可能なLinux実行環境はなく、Docker/LibreOfficeの既存コマンドも確認できない。OS/本番への新規導入やLinux変換試験は未実施。

隔離評価の具体条件：専用Linux環境・採用候補converterの固定版・ライセンス確認済み日本語フォント、ファイル/マクロ実行制限、network無効、入力サイズと実行時間制限、並列profile分離/一時file cleanup、変換失敗時の安全な503。LibreOffice等は候補であり未採用。Microsoft ExcelとのDrawingML円/矢印/画像位置・日本語幅・改行/行高・print area/scale・改ページの差を評価する。

比較fixtureは既存FORMの2026/2027、特殊命式0/1/2/3/6/7/8、長文/改行、奇数末尾空欄、各日干。Windows完成Excel→PDFを基準に、全説明文/キーワードの順序・罫線・見切れ・五行円/label対称・矢印・後続開始位置・ページ数を抽出/画像で比較する。通常A4縦2ページを基準にし、長文fixtureの自然な増ページは一律失敗にしない。差分の許容値は評価結果を示して本人採用判断を受ける。本番disabled解除は独立承認。

## F B2B URL

既存route `/b2b/{organizationId}`を鑑定入力、`/teacher/{organizationId}`を先生管理として維持。複数所属は既存選択画面。Organization/権限は認証済み正規APIが根拠で、Host・bodyのIDは認可根拠にしない。

本番host/domain/DNS/SSL、公開path/サブドメイン方式、trusted origin、proxy header上書き、Secure/HttpOnly/SameSite cookie、誤host時の扱いを確定する。未確定値を実設定へ書かない。現公開B2C URLとB2B公開範囲の扱いも本人判断が必要。

## G 初回アカウント

運営singletonと本人の確認済み担当を固定。教室・先生・生徒の送付先/入金/権限を確認し、auditを保って発行する。平文passwordを運営やCodexが配布しない。初回linkは30分single-use、本人設定後の初期課金開始・旧session失効、期限切れ/配送失敗時の再送を最小ケースで検証してから実発行。教室名やUI上の役割だけで権限を決めない。

## H 請求/休止/解約/保持

初月/翌月1日、未納猶予、督促preview、休止中課金なし、払済末日+30日/休止1年+30日、復旧のみでは期限延長せず再契約でcycle変更を維持。手動入金照合・誤操作連絡・監査・担当/時刻・実請求/通知の採否が本番前の必要事項。実課金/実請求/実督促を実行していない。B2C/他Org/購入証明/C/Dの保護を優先し、未知依存があれば消さない。

## I 障害対応/rollback

症状・原因code・現在の実効設定・期待/実測・操作段階を保存し、secretを除外する。PID/起動時刻/過去ExecStart履歴だけの固定一致を復旧判定に使わない。API/nginx/Webのactive・終了code・実行file/cwd/runtime・HTTP境界・再起動回数・重大log・DB/設定hashを確認。API/DB異常をWebだけの正常応答で成功としない。

切替前に失敗した場合は本番rollbackを実行しない。切替後はあらかじめ承認された復旧手順を一度だけ実行し、復旧失敗なら追加変更を止める。古いNode24.17/Next16.2.9への復帰は既知security問題を再導入する。安全な現行security releaseへの復帰を基準にし、DB schemaや削除情報を古い世代に単純巻戻ししない。session/reset失効・削除情報再適用・本人/契約照合前に利用を再開しない。
