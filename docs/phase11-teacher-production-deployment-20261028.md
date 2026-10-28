# Phase11 先生版専用配備の実施記録（2026-10-28）

前の招待準備資料に対する本人の本番変更承認を受け、先生版だけを配備した。
アプリの配備commitは`f44d71942fdcb24e0b6e2edbfb128b95c41d50d3`。
この記録の追加commitと、稼働アプリのcommitを区別する。

## A. 招待画面・B. 初回設定・C. token

受入済みB2Bを基にした招待画面と既存30分・一回限りの初回設定を配備した。
合成環境の69件のPython試験、PC/スマホ18項目、Windows/Linux build、TypeScript検証を再利用。
今回の配備で占術・正式鑑定文・帳票・UIテーマを変更していない。
Operatorだけの招待管理、再送時の旧token失効、取消し、送信失敗の再試行、所属分離は前資料のとおり。

## D. SMTP・E. Operator・F/G. 先生/生徒

SMTPと本人のOperatorメールは、PCの専用マスク入力画面での入力完了待ち。
本人が指定・承認した試験宛先以外へ送らない。受付と受信確認は区別する。
SMTP未設定の公開APIは送信を拒否し、未設定のままUserを作らない。
本人Operator、先生mari、生徒akinaの本番Userはまだ作成していない。
先生・生徒のメールは、今夜の管理画面入力まで不要。架空アドレス・仮パスワード・偽の入金を作成しない。
本人の初回パスワードは、実際のHTTPS画面で本人だけが設定する。

## H. 実際の公開状態

| 対象 | 配備後の確認結果 |
| --- | --- |
| 先生DNS | 先生ホスト専用のAレコードを新設し、確認済みVPSへ接続。以前はワイルドカードによる別サーバーへの接続だった |
| `https://mari-mutsuro.hakase-uranai.jp/` | 正規TLS検証成功・HTTP200 |
| `/login`・`/reset-password`・`/forgot-password` | HTTP200 |
| `/operations` | ページHTTP200。未認証の管理データは取得不可 |
| `/api/auth/me`・`/api/operations/invitations` | 未認証HTTP401・Cache-Control:no-store |
| `https://app.hakase-uranai.jp/`・`/login` | 従来どおり正規TLS・HTTP200 |

先生用証明書の有効期限は2027-01-26（UTC表記）。TLS警告の回避による確認ではない。
先生用nginxだけを新設し、毎回`nginx -t`に成功した後にreloadした。
既存B2C・共通ワイルドカード・apex・MX/TXT/NSレコードは変更していない。

## I. DB・サービス・バックアップ

| 対象 | 実施結果 |
| --- | --- |
| release | `/opt/apps/fortune-mari/releases/f44d71942fdcb24e0b6e2edbfb128b95c41d50d3`に専用配置。既存の検証済みLinux画面buildを再利用 |
| DB | `/var/lib/fortune-mari/history.sqlite3`を新規初期化。B2C原本へmigrationなし。初期User/Operatorは0件 |
| API | `fortune-mari-api.service`、127.0.0.1:8771、health成功 |
| Web | `fortune-mari-web.service`、127.0.0.1:3011、ログイン/初回設定ページ成功 |
| 新サービス起動 | 本人の追加明示承認後、先生版Web/APIの2サービスだけをOS起動時に有効化。active/enabledを確認。VPS自体の再起動試験は未実施 |
| 既存サービス | Web/API/nginxの状態とmaster PIDを維持。B2C Web/APIの停止・再起動なし |
| 設定・秘密 | 所有者限定領域。秘密はGit・Notion・通常ログ・コマンド引数に出力しない |

手動B2Bバックアップを2026-10-28 11:15 JSTの実時刻で生成した。
固定4回スケジュールの成功枠に数えない。既存AES鍵を再利用し、既存B2C設定と元DPAPIを変更していない。
新B2B DB専用の名前空間・設定・期限付き許可で、既存Backup API/gzip/AES/取得検証処理を使用した。
SSHはこの手動作業用の既存ホスト鍵固定管理接続。B2C専用forced commandを新DBへ無断変更していない。

| 実測 | 値 |
| --- | ---: |
| 元DB | 389,120 bytes |
| gzip | 6,473 bytes |
| AES認証付き暗号文・HDD保存 | 9,343 bytes |
| 生成 | 0.125秒 |
| SSH取得・検証・ACK | 5.038秒 |

HDDのOSボリューム識別・所有マーカー・ACLを検査した。
HDD上の暗号文からSHA、AES認証、RAM内の隔離復号、SQLite integrity/FK/schema、受領ACKを確認した。
顧客内容の出力、平文DBファイルへの復元、本番への復元・利用再開は行っていない。
今回の初回世代は空の認証DBであり、今後のOperator/Organization/招待作成後には追加の手動世代が必要。
既存B2C世代をB2B保全済みとは扱わない。保持期限と手動取得の管理は引き続き必要。

## J. 検証・記録

今回は変更のない占術等の大量再試験を繰り返さず、配備後のHTTP/TLS、公開境界、ポート束縛、
実効DB、バックアップ復号、既存サービス不変を確認した。
Windowsの新規フォルダーに付くOWNER RIGHTSをACL検査が拒否したため、コピー前に停止し、
その新規専用領域だけの権限を既存手順へ揃えて成功した。
配備補助の文字列区切り誤りも接続前の構文検査で停止・修正した。失敗を成功として扱っていない。

コード・資料は専用branch `phase11-account-readiness-20261028`。
[Sessions作業記録](https://app.notion.com/p/407f414e63af81c28c57e403ae702468)へ記録。
本番固有の接続情報・資格情報・秘密鍵・実メールアドレスは公開Gitへ含めない。
main統合なし。既存branch/worktree/確認用プロセスを維持する。

## K. 今夜の手順・L. 残件

公開URLは到達可能になったが、**招待送信が利用できる状態の完成とはまだ扱わない**。
SMTP設定・許可された試験1通の受付/本人の受信確認・本人Operatorの初回設定/明示権限付与、
先生Organizationの準備を終えた後に、本人が管理画面でmariとakinaの実メールを入力する。
同じ先生Organization、Teacher/Student、無料試用、宛先をそれぞれ確認して送信する。
本人たちが30分以内にパスワード設定し、ログインする。未受信/失効は宛先確認後に再送する。

Windows無人実行・バックアップ通知・対外的な保持説明は未完了。
バックアップcron/Windowsタスクの登録・有効化は行わない。
アプリのOS起動時有効化と、バックアップ自動運用の有効化は別の操作として管理する。

### SMTP入力の案内

本人から「SMTP設定が分からない」との回答を受け、Xserverの実際のサーバーパネルと
[公式メール設定](https://www.xserver.ne.jp/manual/man_mail_setting.php)を照合した。
SMTP hostにはパネル表示のホスト名、portには465、TLS方式にはsslを用いる。
認証名はメールアドレス全体、パスワードはメールアカウント専用のもの。
契約管理画面へのログインパスワードやWindowsのPINを使うものではない。
本人Operatorの受信用メールと、Xserverの送信アカウントは役割が異なる。
使用する送信元・本人の受信用メール・試験宛先は引き続き本人が指定し、推測しない。
メールアカウントの新設・既存パスワードの変更・セキュリティ制限の解除は行っていない。
