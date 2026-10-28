# Phase11 管理画面からの初回招待・今夜の利用準備（2026-10-28）

以下の公開未実施・承認待ち等は配備前の記録。
承認後の実際の配備・SMTP・Operator設定・バックアップ結果は、
[先生版専用配備の実施記録](phase11-teacher-production-deployment-20261028.md)を参照する。

## A. 招待画面

受入済みB2B統合候補`a46fb7340b2bd27becd0f963b099e8ea10dabbb6`を正本として、
専用branch `phase11-account-readiness-20261028`と隔離worktreeで実装した。
バックアップbranch `5bc3ce1`をアプリ本体の正本にしていない。
先生・生徒の実アドレスを事前取得せず、招待予定mari/Teacher・akina/Studentを画面へ用意した。

`/operations`とOrganization詳細に「ユーザー招待」を追加。識別名・役割・所属・メールを入力し、
確認欄と宛先確認ダイアログを経て送信する。Operator APIが成功した場合だけ表示する。
先生・生徒の画面には招待管理を表示せず、APIでも拒否する。
メール形式・重複・既存Userの所属/役割を検査し、別OrgのUserを自動再所属させない。

## B. 既存機能の再利用

AuthRepository、PasswordResetRepository/Service、MailTransport、singleton Operator、
Organization/Membershipを再利用した。新しい認証方式やユーザー名ログインは導入しない。
mari/akinaは識別名、認証IDはメールアドレス。管理者へ平文パスワードを表示・返却しない。

招待追加schemaは`product-invitations-004`の1テーブルと部分一意index。
入金・契約・購入証明・請求を偽らない無料試用の明示grantを招待と結び付けた。
今回は初期0円/月額0円、自動請求なし。既存の未払い・停止正式契約を試用で上書きしない。
将来の2,000円への移行・販売価格編集などの新規課金機能は今回実装せず、別途本人確認とする。
有料化・督促・物理削除を自動開始する処理はない。

## C. 初回設定リンク

既存の暗号学的に安全なtoken、hashのみのDB保存、30分、一回限り、再送による旧token失効を維持。
メール内リンクはHTTPSの`/reset-password#token=...`。秘密tokenをAPI応答・通常ログへ返さない。
既存ページがfragmentを一度取り込んでURLから除去し、本人がパスワードを設定する。
設定完了前の通常ログインを拒否し、完了時に旧token/sessionを失効させる。

送信待ち・処理中・SMTP受付・失敗と、初回設定待ち・完了・期限切れ・取消しを別に記録する。
「送信受付済み（到達未確認）」を表示し、メールボックスへの到達を保証しない。
配送失敗時はそのtokenを失効させ、同じUserへ安全に再送できる。
再送後の古いworker、取消し後/設定完了後の遅延worker、所属変更後の誤送信を防ぐ。
取消しは初回設定待ちのUserとtoken/sessionを無効化する。設定済みUserは既存の利用停止操作を使う。
所属が変わったUserは招待取消しで一括停止せず、管理者の確認を要求する。

## D. SMTP

既存SMTPMailTransportを使用。明示した`FORTUNE_RESET_MAIL_CONFIG`がある場合だけ接続設定を読み込む。
Linux所有者限定ファイル、リンク拒否、親ディレクトリの書込み権限、HTTPS origin一致を確認する。
SSLまたはSTARTTLSと証明書検証を使う。送信元・host・認証名・portは推測しない。
パスワードは別の所有者限定ファイルとし、引数・Git・通常ログへ入れない。
不正な明示設定は起動を止める。未設定のまま招待送信した場合は503で拒否し、Userを作らない。

現在の稼働Web/APIプロセスにはSMTP/MAIL関連環境変数名を確認できなかった。
root管理設定やXserverの契約側に存在しないと断定したものではない。
運営者メールとSMTP設定だけをPC上の専用画面へ入力できるようにした。
先生・生徒のメール欄はなく、設定は新規保護領域へDPAPI暗号化保存する。画面自体は送信しない。
実送信は本人指定・承認した試験宛先への1通から行い、受付と受信確認を区別する。
現時点では入力待ち、実SMTP送信・実メール到達試験は未実施。

## E. Operator初期設定

`scripts/operator_initial_setup.py`で、対象DBと操作、本人確認済みemail/User IDを明示する。
連絡先はJSON stdinから受け、コマンド引数や通常ログへ出さない。
新規本人Userを設定待ちとして準備し、既存30分リンクを送付する。
本人がパスワードを設定した後、既存singleton bootstrapで明示的にOperatorを付与する。
初回設定待ち・停止Userは付与不可、既存singletonは置換/重複しない。
既存Userを選定する場合も明示したgrant操作を必要とし、メール・所属roleから自動推定しない。

本番でのOperator発行・権限付与はまだ行っていない。本人のパスワードはHTTPS画面で本人が設定する。

## F. mari先生

招待予定mari/Teacherを準備済み。メール未入力の本番User・tokenは作成していない。
当日は対象先生OrganizationとTeacherを確認して送信する。生徒の内容・個別回数は従来どおり非開示。

## G. akina生徒

招待予定akina/Studentを準備済み。先生と同じOrganizationを選択し、当日メールを確認して送信する。
無料試用は正式入金/購入証明を作らず、所属・本人認証・Userごとの履歴分離を維持する。
本人以外の鑑定履歴や管理画面へのアクセスは拒否する。

## H. 公開URLの実測

2026-10-28の監査結果：

| URL/対象 | 実際の状態 |
| --- | --- |
| `https://app.hakase-uranai.jp/`・`/login` | HTTPS検証成功、HTTP200。現行B2Cとして維持 |
| B2C `/reset-password` | HTTP404。B2B初回設定が配備済みとは扱わない |
| `https://mari-mutsuro.hakase-uranai.jp/` | DNSは存在するがA接続先がB2Cと異なる。TLS検証code62で失敗 |
| 先生hostのnginx設定 | 未設定 |
| 実効Web/API | Web bdc6de9、API569d149。B2B用schema・Operator・Organizationなし |

次は**公開予定のパスであり、現在利用可能なURLではない**。

- 先生・生徒ログイン：`https://mari-mutsuro.hakase-uranai.jp/login`
- 管理者ログイン：`https://mari-mutsuro.hakase-uranai.jp/login?next=%2Foperations`
- 運営招待画面：`/operations`または対象Organization詳細
- 初回パスワード設定ページ：`/reset-password`（秘密tokenはメール内fragmentだけ）
- 本人からの再設定申請：`/forgot-password`。初回招待再送は運営の「招待を再送信」

## I. 本番変更の承認対象・保全・rollback案

**以下は提案であり、実施していない。本人の明示承認後に行う。**

| 対象 | 提案する新規変更 | 影響・保護 |
| --- | --- | --- |
| 先生DNS | mari-mutsuroだけを確認済みVPSへ向ける。現A/AAAAを記録して変更前後を照合 | appドメイン、MX/送信基盤は変更しない |
| 専用release | `/opt/apps/fortune-mari/releases/<承認commit>` | B2Cの既存releaseを上書きしない |
| 専用永続DB | `/var/lib/fortune-mari/history.sqlite3`を新規作成・migration | B2C原本へmigrationや一括Org割当を行わない |
| 専用サービス | fortune-mari-web/API、localhost3011/8771 | 既存Web/APIを停止・再起動しない。候補portは未使用と確認済み |
| HTTPS/nginx | 先生host専用vhost・先生用証明書を新設。`nginx -t`成功時だけreload | B2Cのvhost/証明書を上書きしない。root権限が必要 |
| SMTP/Operator | 承認済み送信設定、試験1通、本人初回設定、明示singleton付与 | 先生・生徒は当日の管理画面入力まで未作成 |
| B2Bバックアップ | 新DBを対象に専用設定で手動の整合コピー・暗号化・HDD取得/隔離検証 | 現行B2C用backup設定を置換しない。自動cron/Windowsタスクは保留 |

新規候補パスの未使用、既存certbotの存在、port空きを確認した。
Linux隔離buildは既存Node24.22.1/Next16.4.2/React19.3.1/TypeScript6.0.3を使用。新依存・OS更新なし。
公開前に、最終承認commit・実効DB/所有者・origin・cookie・proxy・設定hashを再照合する。
cookieはHTTPS/Secure/HttpOnly/SameSiteとhost分離を維持し、trusted originを先生hostへ明示する。

取得済み07:00の実バックアップ（元DB307,200bytes、暗号文54,771bytes）をRAM内で復号し、
候補migrationで既存6表全行保持・追加26表・integrity/FK・再適用不変・DDL失敗rollback・元schema/dataへの隔離rollbackを確認した。
平文DBファイルは作成していない。接続割当をメモリへ差し替えた検証であり、最新の稼働DBを移行した結果ではない。
新B2B DBには認証・招待・所属・契約/履歴等の必要テーブルを含め、実User発行前に復元可能な整合backupを確保する。
初期化後・Operator/Org設定後・招待後の新B2B世代も保全し、B2Cの1世代だけをB2Bの保全済みとは扱わない。

失敗時は新規B2Bの公開を止め、新規サービスと先生vhostだけを無効化し、検査後reloadする。
DNSを変更した場合は保存した先生レコードへ戻す。B2Cは従来構成を維持する。
作成したB2B DBと暗号化backupを保護し、稼働後のDBを古いschema/dataへ単純巻戻ししない。
顧客データ復元と利用再開は別承認。証明書/DNS不一致、root権限不足、backup未検証、origin不一致、SMTP不明では該当工程を止める。
有料クラウド・課金/督促/物理削除・15分台帳同期・main統合・バックアップ定期有効化は対象外。

## J. 検証・Git・Notion

合成環境で新規招待17件・設定3件、既存reset22件・初回配送2件・product API25件を確認した。
PC1280/スマホ375の招待画面18項目、production build、TypeScriptが成功。lock不変。
VPS非公開stagingでも招待/設定試験とLinux production buildを実施し、公開サービスを変更していない。
Linuxで所有者限定設定を受入れ、公開読取り権限とリンクを拒否する検査も成功。
新規ケースの最終件数・Linux最終HEADは完了報告/Sessionsへ記録する。過去成果を無関係に全再試験していない。

最初の合成試験はsandbox一時領域のACLで停止し、専用一時領域と適切な実行権限へ切り替えた。
追加testの配置ミスはtestだけを修正して成功。Linux権限補助は標準Pythonにargon2がなく停止し、
既存APIの仮想環境を使って成功。環境更新・失敗の無視はしない。

公開Gitにはコード・合成試験・匿名化資料だけを保存する。
実設定、実アドレス、token、password、顧客データ、非公開接続情報は含めない。
[今回のSessions記録](https://app.notion.com/p/407f414e63af81c28c57e403ae702468)。既存判断ログ・原則は変更しない。
共通/プロジェクト指示の未解決競合なし。最終commit/push/既存refsとworktreeの保持は完了報告へ記録する。

## K. 今夜の操作（公開・SMTP・Operator設定完了後）

1. 本人の管理者メールでログインし、運営管理の「ユーザー招待」を開く。
2. mari/先生と対象Organizationを選び、その場で確認したメールを入力する。
3. 無料試用と役割・所属・宛先を確認して「招待メールを送信」を押す。
4. 先生が受信後30分以内に本人だけのパスワードを設定してログインする。
5. akina/生徒に切り替え、同じOrganizationで同様に送る。先生のアドレスは切替時に消える。
6. 受付済みと受信を区別して確認し、不達/失効は宛先を再確認して再送する。誤送信は未設定中に取消す。

現在この手順を公開URLで実行できるとは案内しない。実アドレス判明前や昼間に本番tokenを発行しない。

## L. 未完了・必要な本人操作と承認

ローカル招待機能は検証済みだが、今夜の実利用開始は未完了。
本人のSMTP/テスト宛先/運営者情報の安全なPC入力、試験メールの受信確認、
上記の先生DNS・HTTPS/nginx・新規B2B DB/サービス・手動backup・初期Operator設定に対する明示承認が必要。
先生・生徒のアドレスを開発完了の条件にはしない。各自のパスワードは本人がHTTPS画面で設定する。
既存の自動バックアップ条件（Windows無人実行・通知・対外保持説明）は引き続き未完了で、有効化しない。
