# Phase11 管理者ドメイン分離・招待名の自由入力（2026-10-28）

本人の追加希望に基づく変更。実SMTP受信、本人初回設定/Operator/先生Organization、
通常ログイン、HDD暗号化バックアップの完了成果は再利用する。
稼働中アプリのcommitはf44d719、記録保全の基準はd9db448。
新しい専用branchは`phase11-admin-domain-invitations-20261028`。

## 変更内容

招待対象の管理用の名前を、mari/akinaの選択式から空欄の自由入力へ変更した。
64文字以内の必須入力で、ログインIDは引き続きメールアドレス。
名前を変えた場合は前のメール宛先と確認チェックをクリアし、役割は独立して選ぶ。
既存の形式/重複/所属/Operator検査、無料試用、30分・一回限りのtokenは維持する。
新しいDB schemaや課金機能を追加しない。

管理者と先生でAPIプロセスの設定を分け、管理者側で申し込む再設定URLと
管理画面から送る先生・生徒の招待URLを、明示した設定で分ける。
任意のリクエストHost/OriginからメールURLを作らない。従来の単一構成は設定しない限り従来どおり。

## 承認済み本番切替の構成

| 対象 | 具体的な変更・確認 |
| --- | --- |
| 管理者URL | `https://admin.hakase-uranai.jp/operations`。rootは同パスへ誘導 |
| 先生・生徒URL | `https://mari-mutsuro.hakase-uranai.jp/`を維持 |
| DNS | adminホストだけを確認済みVPSへ向ける。既存レコードの有無と値を保存してから変更。B2C・apex・ワイルドカード・メールDNSは変更しない |
| HTTPS | adminだけの新証明書とACME専用領域 `/var/www/fortune-admin-acme`。既存登録・既存certbotを使用 |
| 新release | `/opt/apps/fortune-mari/releases/<承認commit>`へ独立配置。現releaseを保全 |
| Web | 既存の先生版Web 3011を新releaseへ切替。画面buildを両ドメインで共用 |
| 先生API | 既存8771を新releaseへ切替、`FORTUNE_DEPLOYMENT_SURFACE=teacher`。管理APIを404で拒否 |
| 管理者API | 新規`fortune-admin-api.service`を127.0.0.1:8772で起動・OS起動時有効化。`FORTUNE_DEPLOYMENT_SURFACE=admin` |
| 管理者APIの権限 | 既存Operator検査を維持。先生・生徒には管理APIを403で拒否し、鑑定/履歴/先生APIをこのプロセスでは404で拒否 |
| DB | 既存のB2B `/var/lib/fortune-mari/history.sqlite3`を共有。同じ本人User/Operator/Organizationを再利用。B2C DBへ触れず、新DBへのコピー/再発行・追加migrationなし |
| 管理者設定 | 新規 `/var/lib/fortune-admin`の所有者限定領域へenvと再設定メールconfig。SMTP passwordは既存の所有者限定ファイルを参照し、再生成/通常ログ出力なし |
| nginx | admin専用vhostを追加。先生側`/operations`はadminへ誘導、先生側管理APIは404。既存B2C vhostを維持し`nginx -t`後だけreload |
| バックアップ | 切替前のB2B整合コピー・暗号化・HDD取得/隔離検証を追加。既存AESを再利用。自動cron/Windowsタスクは有効化しない |

切替前の読み取り確認で8772と新規候補パスは未使用、既存5サービスは稼働中だった。
当初admin DNS/TLSは未整備だったが、下記の本人承認後にDNSとHTTPSを新設し、公開確認が成功した。

## origin・cookie・招待URL

管理者APIは次のように明示設定する。SMTPの実アドレスや秘密をこの資料へ含めない。

```dotenv
FORTUNE_ENV=production
FORTUNE_DEPLOYMENT_SURFACE=admin
FORTUNE_PUBLIC_ORIGIN=https://admin.hakase-uranai.jp
FORTUNE_HISTORY_DB_PATH=/var/lib/fortune-mari/history.sqlite3
FORTUNE_RESET_MAIL_CONFIG=/var/lib/fortune-admin/mail-reset.json
FORTUNE_INVITATION_MAIL_CONFIG=/var/lib/fortune-mari/mail/config.json
FORTUNE_INVITATION_PUBLIC_ORIGIN=https://mari-mutsuro.hakase-uranai.jp
```

管理者用再設定configの`public_origin`はadmin、招待用configは先生originと一致させる。
いずれも絶対HTTPS・所有者限定・リンク拒否を検査する。不一致/欠落設定では起動を止める。
CSRF検査は各APIの自分のoriginだけを受入れ、先生originからadminへの更新は拒否する。
cookieのSecure/HttpOnly/SameSiteと、Domain属性を使わないhost分離を維持する。
管理者は新URLで一度ログインする。同じ本人メール・設定済みパスワードを使い、新アカウントは作らない。
招待URLは先生側の`/reset-password#token=...`となり、同じB2B DBで初回設定を完了する。

## 確認とrollback

合成環境で、任意の英字/日本語名、宛先と再確認のクリア、Teacher/Student、
管理者/先生プロセスの境界、既存Operator権限、CSRF、別originのメールURLと初回設定を確認する。
本番切替時は本人のadminログインと自由入力欄、先生の管理API拒否、B2C正常性を確認。
先生・生徒の実アドレスは今夜の管理画面入力まで取得せず、先行User/tokenを作らない。
追加の実メール試験を無断で送らず、確認済みのSMTPと本人の初回設定成果を再利用する。

切替前の先生unit/env/vhostとadmin DNS状態、release/設定hashを非公開領域へ保存する。
失敗時は新admin APIだけを停止し、先生のunit/env/vhostを保存した現行設定へ戻し、
先生版だけを元releaseで起動してnginx検査後reloadする。B2C Web/APIは停止・再起動しない。
新admin DNSを変更した場合は保存した状態へ戻す。新DB/設定を削除せず、共有DBへの巻戻しSQLは行わない。
DB schema変更がないため、本人/Org/招待データを保持したまま旧releaseへ戻せる。
既存AES/SSH鍵・回復USB・main・他worktree・確認用プロセスを維持する。

本番変更は、上記の対象・影響・バックアップ・rollbackと新admin APIの起動時有効化を含む
具体的な切替案に対する本人の明示承認を受領してから実施した。

## 実施済みの隔離検証

WindowsのPython関連試験は78件成功：新境界7、メール設定5、既存招待17、再設定22、初回配送2、product API25。
新境界には先生プロセスで管理APIを拒否、管理者プロセスで既存Operator権限を維持、CSRF、
host専用Secure cookie、任意名の形式/重複、管理者からの招待を先生側で設定完了する流れを含む。
模擬メールだけで検証し、実ユーザー・実SMTP・本番DBは使っていない。
PC1280/スマホ375の合成画面18項目、production build、TypeScriptが成功。画像を確認し横方向のはみ出しなし。
既存の固定依存をオフラインでコピーし、lockやバージョンを変更していない。

VPSでも公開nginxを変更せず、新規専用領域の合成TLS証明書でテンプレートの構文検査が成功。
非root検査では低ポートが拒否されたため、検査用のlistenだけを18080/18443へ置換した。
本番テンプレートの80/443や実証明書は変更していない。

最初の境界試験では、既存factoryのappキャッシュ/ASGI参照/模擬メール設定が新設定と一致せず失敗した。
新ケースだけでfactoryキャッシュを分離し、実際のserver設定と合成transportを使って全件成功した。
失敗を隠すためにAPIの拒否条件を緩めたり、本番の設定を変えたりしていない。

Linuxでもアプリ候補commit `7670845af014956cc5790e77e489c66a49969138`の公開ソース束を
新規非公開stagingへ配置し、SHA照合後、新境界7/設定5/招待17の29件とproduction buildが成功した。
既存venv/Node/固定依存を独立コピーして使い、lockは不変。build前の空きメモリは約3.05GBだった。
本番DB・SMTPへ接続せず、既存サービス/DNS/nginxは変更していない。
検証済みの本番切替対象アプリはこのcommitとし、後続の資料commitと区別する。

## 本人承認後の本番実施結果

本人が提示した具体案の本番切替を明示承認。アプリcommit `7670845af014956cc5790e77e489c66a49969138`
へ先生版Web/APIだけを切り替え、新管理者API8772を起動・OS起動時有効化した。
3つのB2Bサービスがactive/enabled。VPS自体の再起動試験は行っていない。
先生版の旧releaseとunit/env/vhostの正確な控えを非公開の専用領域へ保全した。
既存の本人User/Operator/Organization、B2B DB、SMTP資格情報、AES鍵を再利用した。
追加schema migration、先生/生徒の先行作成、追加の実メール送信は行っていない。

切替直前の実時刻2026-10-28 13:09 JSTに手動B2Bバックアップが成功した。
原DB389,120 bytes、gzip8,640 bytes、暗号文12,235 bytes。生成0.132秒、取得/検証/ACK3.677秒。
外付けHDD保存、RAM内隔離復号、SHA/AES/SQLite/FK/schema検証、ACK成功。
既存AESと元DPAPIは不変。これは手動取得で、定期4回枠の成功として数えない。

DNSはadmin専用Aだけを追加。既存の先生/B2C/apex/ワイルドカード/メールDNSを維持した。
admin専用ACME領域と既存登録で証明書を取得し、nginx構文検査後にreloadした。
最初は専用公開ACME領域のumaskによる700権限が403を起こし停止したが、当該領域だけ755へ修正して成功した。
秘密を含む設定/DB/鍵の権限は緩めていない。PCの古いDNSキャッシュによる旧証明書表示は、
権威DNSと実接続先を比較し、PCのDNSキャッシュだけを更新して解消した。TLS検証は回避していない。

13:19 JSTの通常の公開接続で、管理者/先生/B2CすべてTLS検証成功。
admin証明書期限は2027-01-26 03:18:28 UTC。

| 公開対象 | 確認結果 |
| --- | --- |
| admin root | 302で同ドメインoperationsへ |
| admin operations/login/forgot-password/reset-password | 200 |
| adminの未認証招待API | 401、no-store |
| adminの履歴/先生API | 404、no-store |
| 先生operations | 302でadminへ |
| 先生招待管理API | 404 |
| 先生root/login/reset-password、B2C root/login | 200 |

13:20 JSTの読み取り監査で、B2C Web/APIとnginxの状態/PID、既存B2C vhost hashが不変。
本人Operatorと初回設定完了を維持し、DB integrity/FK正常。User1、先生/生徒所属0、招待0を確認した。
管理者再設定originはadmin、管理画面から送る招待originは先生の明示設定で一致し、秘密ファイルは所有者限定。

その後、本人が新しいadmin URLでログインと「招待対象の名前」の自由入力を確認したと回答。
この本人確認を完了証跡とし、別ブラウザーの未ログイン表示を本人のログイン失敗とは扱わない。
今夜は管理画面で名前・役割・所属・実メールを入力し、送信対象を確認して招待する。
受信者は30分以内に初回パスワードを設定する。管理上の名前をログインIDには使わない。

今回のドメイン分離/自由入力は本番反映済み。バックアップcron/Windowsタスクは引き続き保留。
Windows無人実行、バックアップ通知、対外的な保持説明との整合は別の未完了条件であり、
Phase11全体の自動バックアップ運用完了とはしない。今夜の招待による変更後は追加の手動バックアップが推奨される。
