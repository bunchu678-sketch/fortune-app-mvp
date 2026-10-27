# Phase 11 DB・SMTP・Linux PDF・本番公開の準備（2026-10-27）

Phase10は正式完了。本書は保存済み資料・コード・合成試験による準備であり、本番変更の許可書ではない。VPS/実DB/実SMTP/実アカウント/実請求へ接続していない。

## DB copy移行の実施条件

現行labは合成DB専用。本番copy取り扱い機能は未実装。将来の実施承認では、対象ホスト・実効release HEAD・DB絶対path・作業者・読取/書込権限・保護保存先・隔離先・時間枠を先に固定する。

|段階|必要な確認・権限|停止条件|
|---|---|---|
|取得準備|DB読取とbackup APIに必要なWAL/SHMアクセス。最小権限。実DB/sidecarを生copyしない。専用隔離先は所有者限定・十分な容量|現行DBの場所/世代不明、権限不足、backup完了までのtimeout、空き容量不足|
|取得|原本を上書きしないSQLite整合copy。integrity/FK、schema、migration marker、表件数とowner/scope、内容fingerprintを秘密を出さず採取|整合性異常、未認識schema、時点/件数の不整合|
|隔離検証|ネットワーク/メール/公開Webを無効化したcopyに追加migration。旧行全件/件数、B2C、snapshot projection、Org別参照と権限を照合|想定外の列/依存、旧行書換え、別Org混入、B2Cの利用権変更|
|容量/中断|DB本体以外にWAL/journal/元copy/移行前snapshot/検証copy/暗号化中間の容量を評価。強制中断後の再開と再実行を検証|lock時間/容量が承認枠を超過、marker/DDL/行が部分不整合|
|本番適用|暗号化VPS外backupを外部から復号検査済み、最新独立台帳/契約/入金が完全、停止条件とrollback担当が確定した後に別承認|実DB適用の明示承認がない、最新台帳欠落、現行writerと両立未検証|

「無停止」は今回の合成試験だけでは保証しない。既存B2Cのプロセス・nginx経路を維持し、B2Bを別の非公開listener/releaseで先に検証する。新旧APIが同じSQLiteを扱う移行期間は、実copyでschema互換性・writer競合・認証/履歴境界を確認する。許容待機時間内の移行が証明できなければ、本人が停止時間を含む別案を判断するまで切替しない。勝手にB2Cを止めない。

rollbackで現DBを単純に旧snapshotへ戻すと、以降の書込み・削除情報・契約世代が失われる。切替前に新規受付の扱い、書込みjournal照合、最新削除台帳再適用、session/reset失効、identity/契約再確認を含む復旧地点を決める。本番fileDB復元・purge executorは未有効化。

## SMTP・初回発行の運営手順案

現行実装：初回発行でUserと設定待ち行を作成。ランダムな内部passwordは配布せず、本人が30分single-use linkから設定する。設定前はlogin不可、activated_at=NULL・awaiting_initial_setup=1で課金開始しない。再送は同一Userの設定メールを再発行し、前tokenを無効化する。初回送信/再送失敗で新tokenも失効する。

|API状態|意味|運営の対応|
|---|---|---|
|disabled|送信機能未設定|本番設定を勝手に追加しない。設定責任者へ確認|
|unavailable|作成後の配送受付/制限等に問題|重複Userを作らず同じIDの設定待ちを確認し、原因解消後に再送|
|queued|backgroundに受付済み|配送成功と案内しない。一般化失敗ログと送信基盤側の受付/配送/不達を別々に確認|
|setup_pending|本人未設定|課金/利用開始と扱わない。期限切れ・誤宛先・不達を運営が照合|
|完了|本人が有効なlinkで設定済み|login/契約の実効状態を確認。完了済みへ初回設定メール再送は409|

今回追加の5試験：失敗後再送と重複発行防止、再送旧token失効/single-use、30分直前成功/設定後再送拒否、再送失敗時の全link無効化、queuedと配送完了の区別。既存の初回配送失敗・30分期限試験を合わせ7件。SMTP transport/公開reset/認証情報の秘匿は既存mock回帰で確認する。アプリの認証・課金ロジックに修正を要する欠陥は今回見つかっていない。

実障害では、秘密を含まないエラーcode・時刻・受付ID・設定待ち状態を記録し、登録先/入金/本人の照合を運営が行う。登録メールやlink/password/SMTP応答全文はチャット・Git・Notionに載せない。自動再送ループを追加しない。再送で旧linkは使えなくなることを利用者へ知らせる。SMTP受付成功は受信箱到達の保証ではない。

本番未確定：送信元、provider/host/port、TLS方式、認証保管、DNS SPF/DKIM/DMARC、trusted public origin、受信確認先、送信結果監視/不達/再送担当、実送信の独立承認。

## Linux PDF候補比較

今回もWSLに利用可能distributionなし。docker/sofficeコマンドなし。OS・WSL・Docker・LibreOfficeを導入せず、Linux変換未実施。既存Linux converter=disabled、Windows Excel/PDF正式帳票を維持。

以下は候補評価であり採用済みではない。図形/フォント再現性は実測がないため比較上の推定を含む。

|候補|再現性・フォント・DrawingML・五行図・表/keyword・改ページ|安全性・負荷・運用|判断案|
|---|---|---|---|
|LinuxはExcel提供、PDF disabled維持|完成XLSXを維持。Linux側の変換差が発生しない。PDF提供自体はできない|変換基盤の追加運用なし。現在の実装どおり|初期公開の暫定推奨。PDFを約束する商品条件なら本人判断が先|
|隔離LibreOffice headless|日本語フォントを固定・ライセンス確認。DrawingML円/矢印、五行対称、特殊命式4列表、説明→keyword、print area/scaleと改ページはExcel基準との実比較が必要|network/マクロ無効、非root、一意profile/temp、入力上限、timeout、並列上限とcleanup。Linux保守/更新/フォント管理が増える|Linux完結候補の最初の比較対象。ただし同等性未確認のため本番採用推奨ではない|
|別Windows Excel変換worker|既存の完成Excel→Excel PDF経路を再利用しやすいという推定。フォント/Excel版/印刷条件が一致するか確認が必要|追加Windows、認証通信、隔離、Excel license/worker並列/一時fileと障害対応が必要。サービス運用適合性を別途調査|帳票同一性優先の場合の候補。新サービス・費用・データ移動は別承認|
|HTML/Python等で帳票再描画|DrawingMLと別実装になり、円/表/文章配置/改ページを再構築。既存正式レイアウトの維持負担が大きいという推定|Office不要だが二重template保守と全帳票受入が必要|現段階の推奨外。無断実装しない|

比較fixture：2026/2027、特殊命式0/1/2/3/6/7/8、各日干、長文/改行、奇数末尾空欄、通常2pageと自然な増page。2027は既存未登録の扱いを維持し、鑑定文を創作しない。評価対象は日本語欠字、説明/keyword順、罫線/図形の見切れ、円/label/矢印の対称、後続開始位置、ページサイズ/数。Windows完成XLSX/PDFを基準にtext抽出と画像を比較する。許容差は評価結果を提示して本人が決める。

公式資料：[LibreOffice起動引数](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html)、[PDF export parameters](https://help.libreoffice.org/latest/en-GB/text/shared/guide/pdf_params.html)。headless/固有profile/変換フィルターの存在を確認した資料であり、このアプリの帳票同等性を証明する資料ではない。

## 公開準備：保存済み記録からの監査

10/23実測のWebはsecurity release `bdc6de9906557ccc0c0083d53d1fb4a8fb713b9a`、cwd=`/opt/apps/fortune-security-preflight-20261023/release/fortune-next-app`、専用Node24.22.1/Next16.4.2/React19.3.1。旧`/opt/apps/fortune-app`のHEAD569d149は稼働版の根拠にしない。10/26 GitHub main241dd57と本番releaseは別の証跡。今回の現況実測ではない。

実施順：

1. 本人のread-only監査承認後、実効Web/API/nginx、cwd/exe/release/lock/build/DB metadataを秘密非表示で照合。既存B2C経路の正常性を基準にする。
2. security更新を保持した専用B2B releaseを別directory/listenerで準備。既存B2C release・runtime・設定を上書きしない。Linux固定lock buildと合成回帰を行う。
3. バックアップ先/鍵回復/担当/監視と独立最新台帳を確定し、VPS外からの復号/整合/復旧を隔離検証。保存/削除失敗が検出・通知されることを確認。
4. 承認下で保護した実DB copyのmigration/rollback検証。上記の無停止条件を満たすまで実DBへ適用しない。
5. B2B hostとrouteの対応、DNS/TLS/nginx/Host・proxy・trusted origin/Cookie境界を隔離試験。HostやbodyのOrg IDを認可根拠にしない。
6. SMTP/DNS/受信/再送運用を確定。許可宛先だけの実送信、運営singletonの本人確認、初回発行はそれぞれ別承認。
7. 入金照合/請求/未納猶予/休止/解約と保持の担当・運用時刻を確定。現行の確定料金や期限を変えない。
8. 公開対象・切替手順・監視・復旧条件が揃ってからmain統合/本番切替を別承認。B2C継続と各Org/owner権限・logout/session・PDF disabledを確認。

## 将来のread-only本番監査のコマンド案

**今回は一つも実行しない。SSH接続もしていない。** 実行前に対象と承認範囲を再提示する。以下のうちpermission不足・未知のpath・予期しない秘密混入があれば取得を止め、sudo範囲や生出力を自動で広げない。

|目的|許可後のコマンド・取得方法|秘密情報の扱い|
|---|---|---|
|サービス状態|`systemctl show fortune-app-web.service fortune-app-api.service nginx.service -p ActiveState -p SubState -p MainPID -p NRestarts -p ExecMainStatus -p Result`|Environment/EnvironmentFilesの内容を出さない|
|プロセス実体|取得したMainPIDの`readlink /proc/<PID>/exe`、`readlink /proc/<PID>/cwd`|cmdline/environ全文を出さない。必要引数はallowlist抽出器で別承認|
|実効release|確認済みcwdの親repositoryに`git rev-parse HEAD`/`git status --porcelain`。実行exeに`--version`。cwd配下package.jsonのname/versionだけ解析|古いrepo HEADや共通nodeリンクだけで判定しない|
|unit/nginx/設定の同一性|承認済み既知pathのみ`sha256sum`。実効ExecStartは引数allowlistでexe/cwd/安全なportだけ抽出|`systemctl cat`、`nginx -T`、envfile catは生出力しない。必要なDNS/upstream/TLS項目はマスク済み構造化出力に限定|
|HTTP境界|事前指定localhost/公開originへのGET `/health`、未認証`/api/auth/me`と履歴への401確認。B2Cトップ/login、静的asset|credential/cookie/linkを付けない。利用者情報や副作用のあるPOSTを読取監査に含めない|
|DB metadata|DB読取に別の明示承認がある場合のみ、read-only接続でSQLite版/schema/marker/件数/integrity/FKを取得|今回の「実DB接続禁止」を解除したと推測しない。生行/メール/password/token/鑑定文を出さない|
|障害log|承認時間窓だけ、既知error codeの集計・secret scrub後の短い情報|raw journal全文を保存・貼付しない。maskの保証がない行は取得しない|

## 切替・監視・rollbackの停止条件

Web/API/nginxの実効exe/cwd/version・HTTP境界・重大log・再起動回数・DB整合・設定hashを組み合わせて判定する。過去PID/起動日時/ExecStartの履歴との完全一致は要求しない。API異常をWebの200だけで正常としない。

切替前失敗では本番rollbackを実行しない。切替後の失敗は事前承認された安全なsecurity releaseへの一度のrollbackだけとし、復旧失敗は追加変更を止める。脆弱な旧Node/Nextへの単純復帰を採用しない。復元したDBの削除/契約/認証情報が未照合なら利用再開しない。
