# 契約停止時のアクセス制御・HTTPヘッダー・証明書更新反映の本番配備

作業日：2026-10-28（JST）。対象は独立監査のF-03/F-04/F-05に限定。

## 1. 本番配備の概要と成否

本人が直接送信した具体的な本番反映指示に基づき、承認範囲を反映した。
技術配備と機械検証は成功。管理者ログインも本人が確認した。
正規の先生・生徒による「教室付き鑑定→保存→Excel出力」は本人が今回は未確認として残したため、正式受入は未完了。
合成試験成功と本番利用者による実操作確認を混同しない。

新専用branch：`security-production-f03-f04-f05-20261028`。
開始記録HEAD：`5726fb7968f31d1d84c31ecea1c8259a4aa10a83`。
アプリ候補：`b7ad25be2f31976941e54e1fe200e799ed382fd0`。
両者の差分は資料だけ。GitHubの開始HEAD、ローカル候補、検証証跡を照合した。

グローバル・親・プロジェクトのAGENTS/CLAUDE/WORKSPACE_RULESと、Notionの有効・反復確認済みの表現原則、
B2B確定判断ログ、直前の是正候補記録、USB回復成功と定期バックアップ保留記録を確認した。
今回の明示承認と作業ルールに未解決の競合はない。

## 2. 配備前バックアップ

既存方式によるSQLite Backup API整合コピー、gzip、既存AES-256-GCM鍵を使用。
本人指定済みHDDをOS識別し、新規専用領域へ保存した。既存バックアップと回復USBは変更していない。

| 項目 | 実測・結果 |
| --- | --- |
| 生成日時 | 2026-10-28 19:50:26 JST（実時刻） |
| SQLite整合コピー | 389,120 bytes |
| gzip | 8,938 bytes |
| 暗号文・HDD保存 | 12,631 bytes |
| 生成時間 | 約0.171秒 |
| SSH取得・検証・ACK | 約3.708秒 |
| SHA・AES認証 | 成功 |
| 隔離復号 | RAM内だけで実施、成功 |
| SQLite integrity・FK・必要schema | 成功 |
| 取得成功記録・VPS ACK | 成功 |
| 既存AES・PC運用DPAPI | 再利用、既存ファイル不変 |

過去の予定枠を取得済みとしていない。手動バックアップ1回であり、定期運用の開始ではない。

## 3. 正確なrelease・commitと事前照合

旧実効コードを各commitから取得したソースhashと照合した。

| 対象 | 配備前 | 配備後 |
| --- | --- | --- |
| B2C Web | `bdc6de9`（42ファイル照合） | 同じ配置・PID、変更なし |
| B2C API | `569d149`（38ファイル照合） | 同じ配置・PID、変更なし |
| B2B共用Web | `0f53804`（66ファイル照合） | `b7ad25be2f31976941e54e1fe200e799ed382fd0` |
| 先生・管理者API | `7670845`（57ファイル照合） | 両方とも上記同一release |

新規独立配置：`/opt/apps/fortune-mari/releases/b7ad25be2f31976941e54e1fe200e799ed382fd0`。
旧releaseを上書きしていない。先生・管理者のsurfaceと既存envを維持した。

新releaseの246ファイルをGit archiveと完全hash照合し、Python構文確認を実施。
既存の同一依存・lockfileを再利用してLinux production build成功。build後と切替後にもソース不変を確認。
本番向けrewrite先は既存先生APIのローカル接続先を指定した。
新releaseで関連104件（アクセス制御21、hook8、帳票58、招待17）がすべて成功。

前段の検証成果（今回再加算しない）：Windows438成功/8 skip、Linux446成功、隔離nginx77確認、
合成UI11確認、両OS build/型確認。後続の候補変更と検証対象の対応も照合済み。

## 4. 契約停止後のアクセス制御（F-03）

先生surfaceの教室なし鑑定拒否、保存時の教室必須、実履歴/人物の所有者・教室・現在契約の照合、
transaction内の再確認、出力tokenの教室束縛と帳票生成前後の現在権限確認を反映した。
人物候補検索には選択中教室を渡す。B2C公開計算とadminの鑑定禁止境界を維持した。

[権限マトリクス](security-f03-permission-matrix.md)の内容を変更していない。
本番利用者の停止・契約・所属変更を試験目的で行っていない。
本人履歴の閲覧方針、過去完成帳票の再配信方針、先生提携終了の自動権限取消しは今回追加していない。
先生の提携終了を理由に生徒の有効契約を一括停止しない。

公開の未認証確認：先生の教室なし鑑定404、教室付きAPI401、先生管理API404、
admin管理API401/no-store、admin鑑定・履歴・帳票・教室付き鑑定API404。
本番の正規ログイン下での鑑定・保存・Excelは正式受入の残件。

## 5. HTTPヘッダー実測（F-04）

候補どおり3vhost・3snippetを反映。公開HTTPSの正常・転送・401/404で確認した。

| ヘッダー | 3ホストの実測 |
| --- | --- |
| Strict-Transport-Security | `max-age=300`、includeSubDomains/preloadなし |
| Content-Security-Policy | `frame-ancestors 'none'; base-uri 'self'; object-src 'none'` |
| X-Frame-Options | `DENY` |
| X-Content-Type-Options | `nosniff` |
| Referrer-Policy | B2C：`strict-origin-when-cross-origin`、先生/admin：`no-referrer` |
| Server / X-Powered-By | `nginx`だけ、X-Powered-Byなし |

上記ヘッダーは各応答1個で、重複なし。B2Cログインの既存`s-maxage=31536000`を維持し、
未認証管理APIの`no-store`を維持。既存Cookie/CORS設定を書き換えていない。
HTTP→HTTPS、ACME webroot経路、先生→admin誘導を維持し、先生root/旧productは所属入口へ誘導する。
nginxの構文検査成功後にreloadだけを実施し、restartしていない。
ブラウザーでも公開admin画面の外部iframe埋込み拒否を確認した。

## 6. 証明書更新hook・dry-run・reload（F-05）

既存構成はB2Cがnginx authenticator/installer、先生/adminがwebroot・installerなし。
既存pre/post/deploy hookは空で競合なし。Snap更新timerは従来どおりactive/enabled。

`/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh`をroot所有0755で設置。
対象2lineageの成功deployだけでnginx -t後reloadし、B2C/他lineageには処理しない。
renewal設定・B2C installer・timerは変更していない。

対象を1件ずつ指定し、`renew --cert-name <対象> --dry-run --run-deploy-hooks --non-interactive --no-random-sleep-on-renew`を実行した。
末尾のオプションは今回の手動試験の待機抑止だけで、定期更新設定には保存していない。

| 対象 | 開始（JST） | 所要時間 | 結果 |
| --- | --- | --- | --- |
| 先生版証明書 | 19:53:13 | 約11.55秒 | simulated renewal成功、exit0、hook成功ログ1回 |
| 管理者証明書 | 19:54:03 | 約11.51秒 | simulated renewal成功、exit0、hook成功ログ1回 |

各回、hookエラーログなし、nginx ExecReloadの更新、構文検査成功、全アプリPID維持を別々に確認した。
Certbot終了コードだけで成功判定していない。
有効証明書・秘密鍵のhashは前後一致し、公開されたleaf証明書も現在の有効証明書と一致した。
dry-runは試験CAによる更新試験であり、本番の新証明書保存・有効期限延長ではない。
[Certbot公式説明](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)のとおり、dry-run時のdeploy hookは現行有効証明書を使う。

## 7. B2C・B2B・管理者の動作確認

- 切替後および2件の更新試験後に、正規CA/ホスト名検証付き公開29項目が成功。再確認分を別件として加算しない。
- 3ドメインのログイン、先生/admin初回設定・再設定画面、admin管理画面、未認証API境界を確認。
- 独立した未ログインブラウザーでPC1280/スマホ375のログイン6画面・admin画面2件とiframe拒否1件、計9確認成功。
- JavaScript例外なし、横幅はみ出しなし。本人のブラウザーや資格情報を取得していない。
- 本人から、従来の資格情報によるadminログイン・管理画面表示の確認済み回答を受領した。
- 本人から、正規の先生・生徒による鑑定→保存→Excelは今回は未確認として残すとの回答を受領した。
- 帳票生成と権限行列は本番と同一候補の合成環境で検証済み。本番の試験用ユーザー/所属は作成していない。

## 8. 問題・未確認事項・rollback

配備自体の失敗はなく、rollbackは実施していない。確認用コードの次の誤りを訂正した。

1. B2C公開計算を未認証401と誤って期待した。基準`569d149`の実コードで公開計算を許可する既存仕様を確認し、期待値を訂正。本番変更なし。
2. nginxの転送先を相対文字列だけで比較して停止。scheme/host/pathを含む絶対URLとして比較し、正しい転送を確認。本番変更なし。
3. hookとWindows Git archiveのhash比較で停止。archiveはCRLF、設置hookはGit本文のLFであり、改行正規化後に内容差なしと確認。
   最終検査では設置7設定を正規Git本文へ完全hash照合し成功。本番の書き直しなし。
4. 通常sandboxのWindowsタスク読取りはCIMアクセス拒否。必要な読取り権限で確認し、関連タスク0件。登録・有効化なし。

正式受入は正規先生/生徒の鑑定・保存・Excel操作確認が残る。実利用者の契約停止試験や実メール送信はしていない。
hookの失敗通知そのものは今回試験せず、既存バックアップ通知/無人実行/保持説明の残件も解消扱いにしない。

rollback用に旧unit/env/vhostの本文・所有者・権限・hash・リンクと、新snippet/hookが元は存在しないことをVPS非公開領域へ保存した。
問題時は旧Web `0f53804`、旧API `7670845`へB2Bだけ切り戻す。nginxは保存設定へ戻して検査成功時だけreloadする。
新snippet/hookは削除せず専用の無効領域へ退避する。DBを過去へ戻さない。
旧APIへのrollbackでは既知のF-03欠陥が戻るため、追加のアクセス制限は対象・影響を説明して別承認とする。
HSTSは設定を戻した後もブラウザーに最大5分残る。

## 9. Git・Notion記録と本番終了状態

今回の公開変更はこの配備記録だけ。アプリ候補のコード・依存・schemaは変更していない。
通常commit/pushを新専用branchで行い、既存14 branch/worktree/refsを保護。main統合・強制push・履歴書換えなし。
正確な記録HEADとGitHub一致、全worktree cleanは非公開の最終監査と完了報告に記録する。
Notion Sessions DBへ承認・参照・照合・backup・試験・実効release・残件を記録した。

19:56:45 JSTの最終監査で、新release全246ソースと反映7設定の一致、B2B3サービスactive/enabled、B2C PID維持を確認。
B2C/B2B DBファイルhash不変、B2B integrity/FK/schema不変、AES・証明書/秘密鍵・env hash/属性不変を確認した。
既存nginx有効リンクとrenewal設定を維持し、root/実行アカウントのcrontabも前後一致。
Windows関連タスク0件。定期バックアップは引き続き未登録・未有効化。
非公開の接続・鍵情報、顧客本文、ID、資格情報、ローカル制御設定はGit/Notionへ記録していない。

## 10. 次の工程への引継ぎ

次は本人の正規先生/生徒アカウントで、所属教室を開いて鑑定→保存→Excelを確認し、正式受入を判断する。
今回の技術配備成功を、全監査指摘の解消やPhase11全体完了として扱わない。
F01/F02/F06以降、契約終了後閲覧、先生提携終了の自動権限停止、定期バックアップ、依存更新、長期HSTS等は別工程。
