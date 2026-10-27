# Phase11｜実環境監査・本番バックアップ接続基盤・統合検証

指示日2026-10-27、実作業2026-10-27夜〜10-28。基準 `8c73db3fa24da46d1000ae9bca7096c3560c2993`。
本書は現在の統合状態。過去の日次/4回合成基盤の資料は履歴として保存する。
ホスト・アカウント・鍵の参照先・ボリュームGUID・実保存先等の固有情報は公開せず、ローカル非公開設定へ分離した。

## A. 今回の到達点

読み取り監査、本番用の設定/許可付きアダプター、SSH pull、別プロセス統合、
**実VPS＋実USB外付けHDDでの合成データ統合試験**まで実施した。本番運用開始/Phase11全体完了ではない。
既存のBackup API、gzip、Node標準AES-256-GCM、枠識別、受信記録、排他、30日整理を再利用した。
研究コードのジョブ本体を共通クラスへ切り出し、従来のSyntheticラッパーは実用設定を受け付けない境界を維持した。

共通/親/開発元AGENTS、WORKSPACE_RULES、関連Notionの有効かつ本人/反復確認済み原則・判断ログ・前段Sessionsを確認。
今回の明示指示で監査と条件付き合成接続試験が許可された。過去の接続禁止を包括的な本番操作許可に置き換えていない。
合成データ試験/Git/専用worktreeは明示許可の範囲で、未解決のルール競合はない。既存判断DBは変更しない。

本番DBはVPS内SQLite、Windows原則24時間/HDD常時接続、1日4回、gzip/AES-256-GCM、SSH pull、
原則30日。外部有料クラウド・増分・15分独立台帳同期は追加しない。

## B. VPS監査結果

既存の正規接続記録とknown_hostsを照合し、未知鍵の承認なしで既存認証による接続に成功。
DBは**存在・lstatメタデータ・容量・権限だけ**を確認し、SQL/実DB接続/実DBコピーは行っていない。

| 項目 | 確認結果 |
|---|---|
| OS/時刻 | Ubuntu24.04.4 LTS、Asia/Tokyo |
| DB | 過去資料の既知パスと一致、307,200 bytes（300KiB）、所有者は接続ユーザー、0600、通常ファイル |
| WAL/SHM | 監査時点では両方なし。将来も不要という意味ではない |
| ディスク空き | 約142.79GB（約133GiB）、今回候補の512MiBステージ/1GiB作業余裕を確保できる規模 |
| Web/API/nginx | すべてactive/running、作業前後のMainPID等が一致 |
| 公開コード | Web releaseはbdc6de9系、API側repositoryはmain/569d149系。新しい開発branchとは別。両方clean/HEAD不変 |
| 実行環境 | Python3.12.3、稼働Webの既存専用Node24.22.1を確認。更新/共通リンク変更なし |
| ジョブ | 接続ユーザーのcrontabは空。読取可能なsystem cron/timerにはOS保守/sysstat等あり。アプリ定期backupは確認範囲では見当たらない |
| 既存backup | 既知の保管ディレクトリの存在は確認。一覧は権限不足で未確認、権限を広げていない |
| 未確認 | nginxの/proc実行パス/cwdは権限不足。状態/MainPIDは確認。root専用情報をsudoで取得していない |

実接続による新規書込みは、接続ユーザーのホーム配下に新規作成したマーカー付き合成試験領域だけ。
アプリ配置/本番ステージ/本番DB/本番設定に試験コードやデータを置いていない。

## C. Windows・HDD監査結果

- Windows11 Home、build26200、Tokyo Standard Time。既存Python3.12.14と隔離Node24.22.1を使用。
- AC接続時の自動スリープ0（なし）、DC接続時1,800秒。自動休止はAC/DCとも0。解除タイマーは無効。
  原則常時稼働ならAC無スリープで動くが、手動スリープからの復帰は未保証。電源設定は変更しない。
- USB接続の非システムディスク1台と対応するNTFSボリュームを、ディスク/パーティション/Volume GUIDで照合した。
  容量約1TB、空き836,272,504,832 bytes（約836GB/779GiB）。個人ファイルは列挙/読取りしていない。
- ドライブ文字だけを信用せず、OSのVolume GUIDと専用マーカーの両方を確認する。
  再接続で文字が変わった場合は失敗させ、設定を再監査して更新する。別ディスクへ自動退避しない。
- 既存SSHクライアント9.5、既存ssh-agentの稼働を確認。既存のキー/設定/agent状態を変更していない。
- 既存タスク204件、候補取得時刻との明示開始時刻一致は0件。実タスク登録/変更は0件。
  前後で追加/削除なし、実行ユーザー方式も一致。ただし3件の開始境界が観測中に変化した。
  OSによる自己更新と推定するが原因は断定しない。差分を非公開証跡へ残し、既存タスクを変更しない。

実行IDは現在ユーザーを候補にする。無ログオンでも取得する本番案はPassword方式を第一候補とし、
本人がWindowsへ直接資格情報を入力する登録手順が必要。PINをpasswordと推測しない。
S4UでDPAPI/SSHの無人実行ができると仮定しない。InteractiveTokenはログオン中だけという条件を承認する場合の代替。
今回はPassword方式の**無効なXML案**をローカルに保存しただけで、資格情報取得/保存・登録はしていない。

## D. 本番接続アダプター

| ファイル | 責務 |
|---|---|
| adapters/backup_runtime.py | 設定と実行許可の照合、所有マーカー、別領域/リンク防止、OSボリューム識別、空き/ACL、既存暗号呼出し、Backup APIの実パス接続部分 |
| adapters/backup_ssh.py | pinned SSH、固定entry、上限/期限付き転送、catalog/prefix/get/ACKの限定サーバー、VPS生成CLI |
| adapters/backup_client.py | 明示設定からのWindows取得CLI。注意/失敗を終了codeで区別 |
| adapters/backup_notifications.py | 既存MailTransport/SMTP部品に接続可能なVPS/PCの通知アダプター。既定は送信無効 |
| research/home_backup_jobs.py | 共通VPS/Homeジョブと、元の合成専用ラッパー。枠/受領/保持処理は再利用 |
| research/home_backup_task_draft.py | 4回XMLを再利用し、実アダプター向けの無効XMLを生成。登録APIなし |
| research/backup_connection_probe.py | audited private profileを受ける合成専用実接続試験。実DB入力なし |

本番用設定がない/無効、許可なし/期限切れ/別設定/別modeなら実行を拒否する。
実行許可はkind、mode、設定全体のSHA-256、許可action、expires_atを持つローカル管理ファイル。
`initialize/generate/transfer/receive/notify`を区別する。勝手な既定パス/自動ホスト選定/環境DB設定の読み込みはない。
設定/許可は人の承認を代行する仕組みではなく、取り違えと無効状態からの誤起動を防ぐ条件。
本番用の有効化許可は今回作っていない。

初期化は既存ディレクトリを拒否し、別々の新規制御領域とデータ領域へmode/role/namespaceマーカーを作る。
本番時は所有者限定ACLを要求し、鍵を暗号文領域の中に置かない。
Linuxの鍵は所有者のみ、WindowsのAES鍵は現在ユーザーのDPAPIを使う設計。
HDDを識別してからマーカーを読み、未接続でもC側の独立制御領域へ失敗を残す。
sourceは明示された通常ファイル/単一リンクだけ。合成modeでは必ず合成制御ルート内に限定する。

VPSのtransfer用設定はsource_path/key_path/nodeを持たず、サーバーはsource接続・鍵復号機能を使わない。
SSH要求はUUID/offset/SHAだけで、任意パス・削除・生成・シェル式を受け付けない。
本番ではこのentryを専用鍵のforced commandに固定する。現時点の実SSH設定を制限済みとは主張しない。

取得は既存.partのprefix SHAを確認し、残りのoffsetからストリーム転送。
全長/SHA、AES認証、SQLite integrity/FK/schemaを確認してrename、永続成功記録後にACK。
制御DBとOSロックは再利用し、途中失敗でも未検証ファイルを正常扱いしない。
プロセスの出力上限/期限、Linuxの転送中ロック保持期限も設定し、失敗は固定codeだけ記録する。

## E. スケジュール

| VPS生成（JST） | PC取得（JST） |
|---|---|
|07:00|07:10|
|12:00|12:10|
|17:00|17:10|
|23:00|23:10|

第一候補を維持する。確認範囲に重大な固定時刻競合は見当たらないが、OS保守/sysstat等の並行実行はある。
実DBでの生成/転送所要時間と負荷は未測定。初回実取得後に10分差の妥当性を確認する。
生成許容遅延30分/警告猶予15分も設定値。逃した過去枠を生成した扱いにしない。
夜間8時間を含む予定を使って未達/欠落を判定。最大損失8時間を保証する方式ではない。

VPS用cron案とPC用無効XMLは非公開出力として用意しただけ。cron/timer・タスクは未登録。
本番タスクの実行先は既に実装したbackup_clientへ設定でき、従来の合成デモを本番実行先にはしない。

## F. 容量・保持

実DB307,200 bytesはメタデータ値。内容/実圧縮率を読んでいないため、実バックアップ容量の測定値ではない。
仮にraw×1.01+64 bytesの圧縮予算、AES28 bytes/base64/ヘッダー4KiBで見積もると、
1回417,916 bytes、120世代50,149,920 bytes（約50.2MB）、ステージ13世代約5.43MBという**現時点メタデータモデル**。
WALが発生/DBが成長すれば変わる。Backup API時点のcopyサイズも初回で測る。

前段の正式1,000件測定を基礎とする約1.30GB/120世代のモデルも維持する。
512MiBステージ/3日、作業用空き1GiB候補（元DB/WALとは別）、HDD初期5GB以上は監査上十分な規模。
ステージ上限と、DB/WAL/平文copy/処理用空き/メモリの総量を混同しない。
平文64MiB・暗号封筒96MiB、catalog4MiB/4096行の処理上限があり、HDDが大きくても無制限ではない。
成長時は監視結果に基づき上限を検証して変更する。増分や有料クラウドへ変更する提案はしない。

保持は作成日時+30日で、単純な120個制限ではない。取得後に整理し、PC停止後は回収してから後追い整理。
最後の正常世代保護/検証不能/期限超過は注意を記録し、正常削除完了や無期限保存の承認と扱わない。
未知ファイルと別媒体を保護し、管理対象だけを削除する。過去の厳密な30日削除との説明整合は本番前に確認する。
履歴削除/解約猶予/User削除仕様は変えない。台帳/監査等の別根拠記録を一律30日削除しない。

## G. SSH・暗号・回復・通知

信頼済み既存host recordからEd25519鍵を照合し、専用pinファイルへ固定した。
BatchMode/StrictHostKeyChecking、更新/未知鍵自動承認なし、転送/agent forwarding/ローカルコマンド/パスワードfallback無効。
SHA-1のssh-rsa host algorithmは受け付けない。秘密鍵本文・agentの鍵内容は取得/出力していない。

本番案はDB所有者権限で生成するジョブと、専用SSH鍵のrestricted forced-command入口。
既存鍵の許可行を変えず、専用鍵で一覧/取得/ACKだけを受け付ける案を優先し、不要なDB権限変更を避ける。
別OSユーザーが必要なら、そのDB/WAL読取り権限の設計を別承認する。今回は新規鍵/ユーザー/authorized_keys変更なし。

AESは既存Node標準実装を再利用し、自作暗号や外部KMSを追加していない。
実試験では使い捨てAES鍵だけを使い、PC側はDPAPIで保護、HDD上に鍵/平文DBを置かなかった。
本番鍵は未作成。PC故障時はDPAPI blobだけで別PCへ回復できると仮定せず、
HDDと別媒体の保護した回復用コピーと再導入試験を本番前に用意する。

通知待ちはVPS/PCそれぞれのoutbox。生成/通信/取得/媒体/容量/鍵/検証/欠落/未達/期限超過を固定codeで管理。
既存SMTP部品に接続するアダプターは実装/モック試験済みだが、通知先/資格情報/ジョブからの送信呼出し設定は未接続。
`provider_accepted`はメール基盤受付であり受信確認ではない。既定のDisabled transportでは送信しない。
PC停止中にPC自身から通知できないため、VPS側outboxの送信設定も次工程。今回は実メール0件。

## H. 試験

最終の重複を除く成果は **共通62＋接続30＋関連124＝216件成功、失敗0件**。
前回177の範囲を再利用し、新規接続30件と既存SMTP9件の追加確認を含む。
まとめ回帰91件（共通62/当時接続29）は363.441秒、関連124件は85.951秒。
最終の識別/通知補強後に接続30件を36.456秒で確認。最終pin検査2件は再実行で件数へ加算しない。
既存の復元停止・削除再適用・全User停止/session/reset失効・B2C/別Org保護も回帰成功。

実VPS＋実HDDの合成接続試験は新規ID領域で実施、最終確認も成功。
1MiBのランダム合成行から開始し、196,608 bytes受信後のSSH切断→prefix照合→残り取得を検証した。
4枠で異なるSQLite画像、同枠重複防止、改変/誤鍵拒否、メモリ復号/整合、31日目相当の整理を確認。
31日待った試験ではなく、**合成時計**でありOS時刻は変更していない。
ソース実体・鍵・暗号文・制御DB・コードを含む今回の試験領域は、マーカーと全所有一覧を照合し清掃済み。
既存ディレクトリ再利用や推測パスの一括再帰削除はしていない。

初期23件は成功。追加試験時のhardlink作成はsandbox制限でWinError5となったため、
権限設定を変えず新規合成領域の試験として再確認し成功。アダプターの拒否ロジックの失敗ではない。
受信再開完了の件数、HDD不在時の独立outbox、媒体識別を先に行う順序、VPS通知先stateも検証した。
実Windows再起動/物理電源断/実HDD抜差し、実顧客データの復号、実SMTP到達、本番アカウントでの定期タスクは未試験。

## I. 安全性・復元境界

本番DB未接続/未コピー/未更新。元DBの前後メタデータ、サービス/PID、実効repository HEAD/cleanを照合済み。
アプリ/占術/正式文/帳票/UI/認証契約仕様/利用者DB schema/既存設定/依存関係を変更していない。
本番サービス、cron/timer、実Windowsタスク、SSH設定、OS、nginx/DNS/TLS、メールは操作していない。

15分独立台帳同期/変更ごとの外部ACK必須化/新常駐台帳は保留のまま。
本番接続側はバックアップ取得とメモリ整合検査までで、実DB復元や利用再開のコマンドを持たない。
復号・整合性の成功だけで削除/契約の最新性を証明したことにはしない。
既存の安全な合成復元経路の拒否条件は維持し、最新性を確認できなければ本番利用再開は禁止。
通常バックアップの導入準備を、この保留問題の追加研究で延期しない。

## J. Git・Notion・非公開証跡

新規branch `phase11-production-adapter-20261027`、隔離worktreeは開発元
`outputs/phase11-production-adapter-20261027/worktree`。既存7 worktree/refs/確認プロセスを維持する。
検証済みソース・試験・資料だけを通常commit/push。main統合/force/resetはしない。
Sessions DBへ本作業を記録し、既存判断DBを変更しない。

開発元の同outputs直下にだけ保存した非公開証跡：

- `vps-initial-audit.private.json`、`vps-services-audit.private.json`、`vps-final-audit.private.json`、`live-audit-summary.json`
- `windows-audit.private.json`、`windows-tasks-final.private.json`、`windows-task-difference.private.json`、`windows-final-summary.json`
- `live-synthetic-integration-final.private.json`、`backup-final-regression.log`、`adapter-release.log`、`related-final-regression.log`
- `vps-settings.pending.private.json`、`transfer-settings.pending.private.json`、`home-settings.pending.private.json`（全てenabled=false）
- `windows-task.DISABLED.pending.private.xml`、`vps-cron.NOT_REGISTERED.pending.private.txt`、`capacity-from-metadata.json`
- `backup-runtime-source.zip`、`backup-runtime-source.manifest.json`（ソース11ファイルだけ、鍵/接続設定/顧客データなし）

生のホスト/アカウント/鍵参照/volume GUID/固有パスはGit/Notionへ転記しない。
試験用のprivate profileは再現の参照で、本番用許可ではない。使い捨て鍵と試験DBは残していない。

## K. 本番開始までの残件

Codexが追加承認なしでできるのは、今回許可内の資料/コード確認、ローカル合成試験、無効設定案の点検、
今回作成した合成物の所有確認付き整理、Git/Notion記録まで。
本番稼働については次を具体案として本人に承認してもらう。

1. 専用backup runtimeの恒久配置、stage/control/HDD専用領域の作成と必要ACL。既存アプリ領域は上書きしない。
2. 本番AES鍵/DPAPI配置、HDDと別媒体の回復用コピー・回復試験。保管先未指定を推測で埋めない。
3. 専用SSH鍵・最小権限forced commandの追加。既存認証を維持し、必要な権限だけ設定。
4. VPSの4回生成cronとWindowsタスクの登録。Password方式なら資格情報をWindowsへ直接入力する手順を確認。
5. 明示許可した実DBのread-only Backup APIコピー→暗号化→HDD取得→非公開隔離検証。生データをAI/通常ログへ出さない。
6. 通知先/送信元/認証の設定とジョブへの接続、許可宛先での実送達確認（未確定なら送信しない）。
7. 原則30日/停止後整理/最後の正常世代例外の対外説明、復元時の本人/契約照合と再開承認手順。

## L. 次回の単体完結指示

[本番設定・初回取得・隔離復元の次回指示案](phase11-backup-activation-instruction-20261027.md)を用意した。
本人が次回採用して初めて当該操作の許可になる。今回の作業中にその許可を先取りしていない。
実行時は監査とHEAD/固定host key/volume GUIDを再確認し、無効案をそのまま登録しない。

一次資料： [SQLite backup](https://docs.python.org/3.12/library/sqlite3.html)、[OpenSSH](https://man.openbsd.org/ssh.1)、
[Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)、
[Volume GUID](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumenameforvolumemountpointw)。
各APIの存在と用途の確認であり、未実施の本番運用を保証する資料ではない。
