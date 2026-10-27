# Phase 11開始・バックアップ基盤の先行実装（2026-10-27）

## 現在地と承認

Phase 10は2026-10-27に「ローカルの主要機能開発・総合検証・本人受入」の範囲で正式完了した。帳票3件・画面6件の再受入は要求しない。本番運用・実環境確認・未確定仕様はPhase 11へ移管済み。本書はB2B本番公開完了の宣言ではない。

- 最新承認：[Notion Phase10正式完了・Phase11移行](https://app.notion.com/p/406f414e63af81939a6df18cb907ed10)。
- 前工程：[Notion 10/26夜間統合検証](https://app.notion.com/p/405f414e63af8100a351d9cca7c0a2a3)。
- 正規repository：`C:\Users\bunch\Documents\Codex\fortune-app-public`、origin=`https://github.com/bunchu678-sketch/fortune-app-mvp.git`。
- 新規branch：`phase11-backup-foundation-20261027`。基準：統合検証済み`a46fb7340b2bd27becd0f963b099e8ea10dabbb6`。
- 新規worktree：開発元`outputs/phase11-backup-foundation-20261027/worktree`。既存4worktreeは切替・上書きしていない。
- 開始時のGitHub実照合：main=`241dd57e39e451ad1c626414d93290b875d027fc`、B2B=`578b429c03694a6d85d47fbb677fb9fd0c1cbab5`、統合branch=`a46fb7340b2bd27becd0f963b099e8ea10dabbb6`。指定と一致。ローカルmainの旧`e8b5308`は意図した保全状態なので変更しない。

参照順：共通`~/.codex/AGENTS.md` v1.3、親`Codex/AGENTS.md`と`WORKSPACE_RULES.md`、開発元`AGENTS.md`。公開repositoryには固有AGENTSなし。今回の専用worktree・commit/pushは最新の明示指示で許可済み。現在の指示との未解決競合なし。Notionの有効かつ本人確認済み原則（W正本、占術文創作禁止、既存実装再利用、Gitで戻せるコードの重複バックアップ不要）、関連Lessons、判断ログを参照した。古い受入待ち・旧フォルダ説明を現在地と混同しない。

必須6資料（phase11-overnight、phase10-completion-readiness、phase11-predeployment、backup-retention-restore、phase11-handoff、phase10-test-plan）と、10/23のsecurity VPS実測記録を確認した。

## 実装範囲

すべて研究用labと試験。アプリ本体・schema・認証・課金・正式占術文・画面・帳票・依存ファイルは変更しない。アプリから新しいlabをimportしない。

|責務|実装・試験|本番との境界|
|---|---|---|
|取得|既存SyntheticBackupLabを再利用。SQLite backup API、WALのcommit取得・未commit除外、ページ単位期限監視。新規snapshot側だけDELETE journalへ整え単独画像化|DBパス引数なし、環境DB設定を参照しない。新しく作った合成DBのみ|
|暗号化|既存隔離Node24.22.1のnode:crypto AES-256-GCM。256bit合成鍵、ランダム96bit nonce、128bit認証tag、AADに世代/日時/ID/schema/hash。誤鍵・改変・切詰め・AAD違いを拒否|候補方式の実暗号試験。本番の鍵保管/回復方式や暗号フォーマットを採用したわけではない|
|保存|ObjectStore境界、memory-onlyのimmutable put、version/replica inventory、保存後read-backと復号検査|外部サービスadapterやローカル永続storageは未接続。DB/key/ciphertextをGit/Notionへ保存しない|
|日次予定|JSTの明示時刻が必須。同日成功済みは再取得せず、失敗時は同一ID/暗号文で上限3回。ack不明の再試行も重複しない|試験の03:00はfixture値。本番時刻の決定ではない。timer・永続ジョブ台帳・プロセス間leaseは未導入|
|検証|SHA-256、integrity、FK、schema/migration/origin、世代を照合。復号データはメモリにdeserializeして検査|hashは削除台帳の最新性や真正性の証明ではない|
|30日保持|元の取得日時+30×24時間を境界とし、全version/replicaを列挙・削除・残存再確認。取得不明/一覧不完全/削除拒否は失敗。途中削除の再試行に対応|メモリ内の模擬削除のみ。本番のobject/version/replica消去は無効。journal/C/Dを自動消去しない|
|監査|取得/保存/検証/期限削除/復元の固定code・ID・記録時刻。生例外/鍵/鑑定文/メール内容を記録しない。監査書込不能時は成功にしない|監査はRAM内。通知先・監視サービス・耐障害永続監査は未設定|
|復元判定|独立最新台帳mockのchange watermark・revision・完全性・日時と再適用前後を照合。既存retention処理で削除再適用、B2C/他Org保護、session/reset失効、全User停止|戻り先は`:memory:`だけ。外部台帳の認証・最新性保証は本番未実装。再開API・file DB復元/purgeは無効|

標準暗号はNodeの実装を呼び出し、自作暗号や簡易暗号は実装していない。Python環境にcryptographyがないことを確認後、既に存在する隔離Nodeの標準APIを評価した。鍵はプロセス引数・環境・ファイル・ログに置かず、専用stdin pipeだけで子へ渡す。これは鍵の安全な永続保管・プロセスメモリの完全消去を保証する実装ではない。起動中アプリのNodeやPATH設定は変更していない。

取得元DBのWAL設定は変更しない。WAL画像をそのままdeserializeした初回試験では`unable to open database file`となったため、snapshotの新規コピー側だけをstandalone形式に整えた。実本番DBへの修正ではない。

## 最新台帳の停止条件

LatestLedgerMockは独立系統を模擬する試験部品。公開済みの古いexportを新しい時刻に言い換えること、hashだけ渡すこと、未公開の最新変更を無視することを拒否する。取得不能・不完全・未反映変更・世代差・復元中の新変更では復元結果を返さない。

これを本番の信頼できるproviderと見なしてはいけない。認証された外部取得、変更連動保存、欠番/完全性と独立high watermark、鍵回復、最新契約・入金・本人照合が必要。復元試験成功後も全Userはdisabledであり利用再開を自動化しない。

## 合成DB移行

`research/migration_scale_lab.py`と`tests/migration_scale_cases.py`を追加。旧B2C六表fixtureから新規所有copyを作り、現行の実migrationを適用する。任意の実DBパスを受け取らない。

- 25,000履歴・約24.6MiBの合成DBで旧六表の全行不変、8 migration key、B2Cの所属/scope自動作成なしを照合。
- 初回測定：移行約0.0792秒、working DB 25,792,512 bytes。所有lab2個の元DB・移行前snapshot・working DB等の観測合計76,787,712 bytes（約73.2MiB）。5msサンプリングによる観測値で真の一時容量上限ではない。最終回測定は検証ログを正本とする。
- 子プロセスを未commitのDDL/行更新中に実際にexit73で異常終了させる。再接続でDDL/marker/行更新がrollbackされ、その後の移行が成功。
- Auth部分までcommit済みの中断状態からB2B初期化を再開し、再実行後もfingerprint一致。
- schema不一致はDDL前に停止。rollbackは移行前snapshotからメモリに戻して照合するだけ。
- 別Org認可/owner不一致を拒否。追加のWAL旧版writer継続試験では、移行と同時にack済みcommitの保持を検査する。

本番copy未取得・実schema/件数/ディスク/同時負荷は未検証。本番のcopy作成・接続・移行・復元は実施していない。実環境での所要時間や無停止をこの値から保証しない。

## 検証・証跡

最終件数・Git/Notion参照は末尾を参照。旧514/69/556/38/536/移行8を今回の新しい成果数として転記しない。

ローカル証跡：開発元`outputs/phase11-backup-foundation-20261027/`。DB/ログ/鍵/依存/帳票はcommit対象外。

初回の環境問題・不具合は区別して保全する。

1. default Tempの制限で26試験がsetUp段階に失敗（準備26＋cleanup26のerror52）。`backup-foundation-first.log`。作業専用TEMP/TMPへ修正。
2. 2回目25成功/1失敗は新規labのWAL画像deserialize不具合。`backup-foundation-second.log`。新規snapshotだけ単独形式化して修正。
3. SMTPのsandbox試行は内部socketpairのaccept待ちで停止。30秒診断は`initial-setup-diagnostic.log`。今回の試験プロセスだけ終了し、通常権限のmemory mail試験へ切替。親launcher終了で子も終了したため、子PID終了要求は「process identifierが見つからない」となった。既存確認プロセスに影響なし。
4. Git状態確認の`must be run in a work tree`は各コマンドへの`-c core.bare=false`で対応。Git設定ファイルは変更なし。sandboxのorigin DNS制限/CIM制限も通常権限の対象を限定した照合で補完。

意図的な容量不足・権限拒否・中断・破損・失効・exit73は異常系試験の合格条件であり、最終の未解決不具合数には加算しない。

## 公式参照と次の資料

- [SQLite Online Backup API](https://www.sqlite.org/backup.html)：ページ単位copy・busy/lockと中断の扱い。
- [Node24 crypto](https://nodejs.org/docs/latest-v24.x/api/crypto.html)：AES-GCM、AAD、nonce、認証tag。採用判断とは別のAPI確認。
- [運用準備と停止条件](phase11-operations-readiness-20261027.md)
- [本人判断資料](phase11-decisions-20261027.md)

## 最終検証・Git・Notion

|今回の最終検証|成功|失敗|
|---|---:|---:|
|新規backup foundation|29|0|
|新規migration条件（大規模/中断/並行writer等）|6|0|
|初回配送/再送（既存2＋追加5）|7|0|
|既存backup lab|17|0|
|既存mail / password reset|9 / 22|0|
|既存final retention / final API|34 / 8|0|
|既存predeploy / deploy blocker|7 / 20|0|
|合計|159|0|

今回新規40件・既存119件。中間の26件/5件や再試行を重複加算しない。Python6ファイルのAST構文、Node probe構文、git diff whitespace検査も成功。既存アプリ・schema・依存の変更がないため、変更範囲に直接関係する回帰へ限定した。既存の総合514件/Node69/build/ブラウザー536の全再実行やWindows帳票再受入は今回していない。

最終移行観測は約0.0806秒、working DB25,792,512 bytes、サンプル最大合計76,812,848 bytes。WAL旧版writerの30回のack済みcommitも保持。ログ中のPDF converter_unavailable/503は期待する安全な拒否を検証したもので、最終失敗ではない。

実装commit：`e0405cbf867ca3d3335200a79870e65a7145f2e0`。専用branchへ通常push済み。文書3件を追加のdocs commitで保存する。mainへのmerge/push・force/resetは行わない。最終HEAD/remote一致/clean/既存refsとlistenerの保全はローカル`final-audit.json`およびNotion最終追記を参照する。

[今回のNotion Sessions記録](https://app.notion.com/p/406f414e63af819e9eb2ff2eb0fadeaf)。新規作業だけを記録し、Phase10正式完了承認ページ・旧Sessions・DB schema・原則は変更しない。最終commitと照合結果を同じ新規ページへ追記する。

追加/変更ファイル：researchのbackup_restore_lab（小修正）、backup_foundation_lab、backup_crypto_probe、migration_scale_lab、testsのbackup_foundation_cases、migration_scale_cases、initial_setup_delivery_cases（5件追加）、本書・operations-readiness・decisionsの計10件。開発元researchの最終監査補助scriptとoutputsのログは公開commitに含めない。

残る本番ゲート：実storage/全copy消去の確認、鍵保管と回復、日次timer/永続job/監査/監視、認証された独立最新台帳、実DB copy移行、本番SMTP/URL/DNS/TLS/運営発行/請求、Linux PDFの採否。本番fileDB executorは無効。これらは本番未検証/本人承認待ちで、今回のローカル実装・合成試験の成功とは区別する。
