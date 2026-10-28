# 独立セキュリティ監査 第1次是正（本番未適用）

対象はF-03/F-04/F-05のみ。2026-10-28の本人指示に基づき、調査・再現・候補実装・隔離検証・Git保全・配備案を作成した。
**本番の変更・reload・再起動・証明書更新・dry-run・hook設置・新しい本番バックアップは実施していない。**

## 【1】作業概要

| 本番構成 | 開始時の実体 |
| --- | --- |
| B2C Web | bdc6de9。画面ソース24ファイルの改行正規化SHA一致 |
| B2C API | 569d1494202782099e6b8197f7825750f5d463fb。実Git HEAD確認 |
| B2B Web | 0f53804189489df9041c1e86702bef33d51e3913。画面ソース45ファイルSHA一致 |
| 先生・管理者API | 7670845af014956cc5790e77e489c66a49969138。Python57ファイルSHA一致 |
| nginx / Certbot | 1.24.0 / 5.8.0 |

最新記録4c9d60eを基準に `security-f03-f04-f05-20261028` と隔離worktreeを新設。
本番でWeb/APIが異なるreleaseであることと、基準commitが本番と同一のアプリソースを含むことを区別した。
mainにB2Bが含まれるとは仮定していない。
候補commitは **b7ad25be2f31976941e54e1fe200e799ed382fd0**。後続の記録commitとは区別する。

グローバルAGENTS/CLAUDE、親WORKSPACE_RULES、プロジェクトAGENTS、Notionの有効な表現原則、
2026-10-09のB2B契約確定方針、直前のPhase11/回復鍵記録、実在する独立監査報告書を参照。
F-01/F-02/F-06以降、OS/依存更新、課金/督促/物理削除の有効化には着手していない。

## 【2】F-03：契約停止後のアクセス

### 再現

合成DB・実ASGI入口で、同じ有効セッションの教室契約を休止すると、教室付き鑑定は403に対して、
教室なし鑑定・教室なし履歴保存・教室なし履歴のメモ変更・その実行tokenによるExcel生成がすべて200になった。
本番の実ユーザー/契約を使って再現していない。

原因は、教室付き経路だけが `member_access()` を通り、通常履歴経路が所有者確認だけだったこと、
メモリ内出力tokenに教室情報がなく、出力利用時の契約確認がなかったこと。

### 修正候補

- teacher surfaceで `/api/fortune` と末尾スラッシュを404。adminの既存境界を維持。
- 先生版の保存は教室必須。現在の本人・所属・契約を確認し、実際の履歴スコープと所有者を照合。
- 履歴メモ変更/削除/復元、人物変更は書込みtransaction内で再確認。再鑑定準備にも同じ確認を適用。
- 別教室/B2Cの人物・グループ・再鑑定元を指定してスコープを付け替える経路を拒否。
- 新規鑑定の候補検索は選択中教室を送り、同じ教室に属する人物候補だけを返す。
- tokenにサーバー側の教室を追加。Excel/PDFの実行時に再判定し、生成/変換中の契約変更も応答前に再確認。
- 古い教室なしtokenを先生版では拒否。B2C/combinedの既存token形式、本人/セッション束縛、期限・容量上限・期限内再利用は維持。

新しいDB schemaやmigrationはない。再起動により従来どおり未保存実行の一時出力tokenは失われる。
既存の保存履歴は削除/移動しない。教室情報のない既存行を推測で教室へ割り当てる処理はない。

実装対象：`b2b_content_access.py`、`deployment_boundary.py`、`history_repository.py`、`history_service.py`、
`report_export_service.py`、`report_pdf.py`、backendのfortune/history/export入口、Webの候補検索1箇所。

### 権限マトリクスと留保

[期待結果表](security-f03-permission-matrix.md)に、利用者6区分・契約8状態・surface3種・教室指定・tokenの組合せを整理した。
有効契約/有効試用では正規の教室付き操作が成功。休止/未納休止/利用終了/試用利用権取消し/所属権限取消しでは新規利用を拒否。
一方の教室の有効契約を、他方の休止した教室の履歴変更/出力へ流用できない。
先生/運営者も他人の鑑定本文を閲覧・出力できない。先生提携終了で生徒の有効契約を一括停止しない。
試用の自動期限は追加せず、合成DB内で既存の試用判定がfalseになる状態を作って終了後を検証した。
完了済み試用を終了する新しい管理画面/正式運用経路は追加していない。F-15には着手していない。

**休止/解約後の履歴閲覧は新たに決定していない。**
既存の所有者SQLと `content_visible()` を維持したため、休止の一部では閲覧可、
利用終了後は復旧状態/期限で非表示になる既存挙動がある。これは今回承認された商品仕様ではない。
一覧/詳細/削除済み一覧/過去メモの所有者分離を維持し、契約停止後の閲覧方針は別の本人判断とする。

現行の帳票APIは毎回新しく生成し、完成帳票を恒久保存していない。
今回拒否するのは新規生成であり、「過去の完成帳票の再配信」という未実装機能の方針を決定していない。

Notionでは提携終了後に先生の管理/利用権を適切に停止する方針だが、
現行の「提携終了」記録は所属権限の自動取消しと連動していない。
今回は生徒の契約維持と先生の所属権限取消し後の拒否を検証し、自動連動の仕様は追加しなかった。
先生権限の停止方法は、本番の提携終了運用前に整合を確認する必要がある。

既存本番履歴のスコープ件数の集計は、当初、自動承認審査により「集計値をPCへ転送する具体的承認不足」として停止した。
その後、本人が3件数の取得とPCの専用outputsへの保存を明示承認し、読み取り専用で取得した。
件数と影響評価は非公開outputsに保存し、公開Gitには転記しない。個人情報・IDの取得やDB更新は行っていない。
最初の実行はスクリプトの引用符誤りでDB接続前に停止したため、引用符だけを修正して取得を完了した。
この承認は集計だけに限り、本番配備の承認として扱わない。

## 【3】F-05：証明書更新と反映

| 対象 | authenticator | installer | 更新後の反映経路 |
| --- | --- | --- | --- |
| B2C | nginx | nginx | 既存installerを利用。今回の実更新/dry-runは未実測 |
| 先生 | webroot | 設定なし | 現行のpre/post/deploy hookなし |
| 管理者 | webroot | 設定なし | 現行のpre/post/deploy hookなし |

`snap.certbot.renew.timer` はactive/enabled。直近起動は2026-10-28 12:23 JST、サービス終了コード0。
「更新タイマーがない」という状態ではない。対象renewal設定とグローバルhook設定を読取り確認した。
参照した現行ログ範囲ではdry-runの証跡は確認できず、今回も実行していない。

監査の「先生/adminの更新後reload経路がない」という指摘を裏付けた。
候補 `deployment/security/reload-nginx.sh` は、先生/adminの既知lineageの成功deployイベントだけを扱う。
`nginx -t` 成功時だけ `systemctl reload nginx.service`。restartなし。
失敗段階を標準エラーとloggerへ記録し、hook自身は非0で終了する。nginxの生出力や秘密値を通常ログへ流さない。
B2C/他プロジェクトのlineageでは何もせず、既存nginx installerと重複させない。

Linuxの隔離コピーで8件成功：sh構文、成功時の順序、先生lineage、構文エラー時reload抑止、
reload失敗、B2C対象外、他プロジェクト対象外、成功更新文脈欠落。
実コマンドを模擬コマンドへ置換した試験専用コピーであり、本番hookは設置/実行していない。

注意：hook失敗がCertbot全体の終了コードへ直接反映されない場合があるため、
将来の通知はhookのlogger/標準エラーも監視対象にする必要がある。今回、実失敗通知は試験していない。
根拠：[Certbot公式・更新とhook](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)。

## 【4】F-04：HTTPヘッダー

実公開HTTPS24 GETで3ドメインの通常画面・401/404・管理者/先生境界を確認。
B2Cのreset/forgotは既存どおり404であり、新しい認証画面を追加していない。実ユーザーログインや実Cookieは使っていない。
既存コード/資料に正当なiframe利用は見つからなかった。外部サイト側の埋め込み契約の有無は未確認。

| ヘッダー等 | 現状 | 候補 |
| --- | --- | --- |
| HSTS | なし | HTTPSのみ `max-age=300` |
| X-Frame-Options | なし | `DENY` |
| CSP | なし | `frame-ancestors 'none'; base-uri 'self'; object-src 'none'` |
| X-Content-Type-Options | 先生/adminのみ既存 | 3ドメインで `nosniff` |
| Referrer-Policy | B2Cなし、先生/admin no-referrer | B2C strict-origin-when-cross-origin、先生/adminを維持 |
| X-Powered-By | Next.jsを公開 | 対象vhostでupstreamヘッダーを抑制 |
| Server | nginx版数を公開 | 対象のHTTP/HTTPS serverで版数だけ抑制 |

HSTSにincludeSubDomains/preloadなし。1年へ自動引上げしない。
最小CSPにはscript-src/style-src制限を入れず、Next.jsの既存処理を維持する。
HSTSの将来引上げは、3ホストの更新/監視の実運用とHTTPS回帰が安定してから別承認で行う。

本番3vhostから候補を作成し、Certbot管理の証明書/SSL部分を編集していない。
対象serverのincludeと必要な先生版境界だけを追加し、グローバルhttpや同居アプリへ適用しない。
upstreamの同名セキュリティヘッダーを隠してから一度だけ追加し、二重送信を防ぐ。
既存Cache-Control、Set-Cookie、Content-Disposition、CORSの状態は維持する。

対象vhostの現行locationには独自add_headerがないことを確認。
nginx1.24では下位にadd_headerを書くと上位分を継承しないため、将来そのようなlocationへ追加する際は同じsnippetもincludeする。
新しいnginx向けのadd_header_inheritを1.24へ持ち込んでいない。
根拠：[nginx公式・add_header](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header)。

先生版は教室なし鑑定2経路をnginxでも404とし、root/旧product入力をmypageの所属入口へ302。
正規のB2B入力は `/b2b/{org}` で既に教室付きAPIを利用するため維持する。
B2Cのroot/通常鑑定は変更しない。Webの1行変更は候補検索に教室を添えるもの。

### 隔離結果

実nginx1.24・ループバック専用高ポート・合成TLS・合成upstreamで77確認成功。
通常/401/403/404、3vhost、各locationの単一ヘッダー、子locationのadd_header＋no-store、
API境界、先生入口誘導、B2C通常鑑定、ダウンロード/クッキー、HTTP ACME到達を確認した。
合成CAとホスト名を通常検証し、本番TLS検証を回避していない。
fixtureでは証明書とlisten/一時パス/upstreamを独立値へ置換し、本番のDH/Certbot includeは使っていない。

Windowsの実ブラウザーではビルド済みNext＋候補と同じヘッダーを付ける検証用proxyで11確認成功。
PC1280/スマホ375の正規鑑定/候補検索/保存/Excelダウンロード/幅と、別originからのiframe拒否を確認した。
このブラウザー試験は本番nginxやLinux nginxへの直接ブラウザー接続とは別で、合成APIを用いる。
PDFは権限/変換前後を模擬converterで検証した。本番LinuxのPDF変換無効は従来どおり。

## 【5】試験結果

| 区分 | Windows | 隔離Linux |
| --- | --- | --- |
| 新規F03 ASGI | 21成功 | 同じ21成功 |
| 新規hook | POSIX専用8をskip | 8成功 |
| 既存関連回帰 | 417成功 | 同じ417成功 |
| 合計（重複加算しない） | 438成功、8 skip | 446成功 |
| production build/型 | 成功 | Linux build成功、lock不変 |
| 実ブラウザー | PC/スマホとiframeの11確認 | 別途実nginx77確認 |

対象はproduct API、password reset、招待/配送/設定、admin境界、auth、history/restore、
Excel/PDF、契約/所属/運営管理、実行集計、ライフサイクル/保持。22 suite。
同一ケースのWindows/Linux、初回失敗後の再試験、最後の該当1件を足し合わせていない。

アプリコードの全回帰/buildはb252997で成功。
その後の8d1ca43/b7ad25bはnginx候補と試験だけの差分であることをGitで確認し、
最終候補のnginx77確認と先生権限の該当1件を再検証した。アプリ回帰/buildを無関係に繰り返していない。

初回F03試験は、試験のASGI参照が固定され外側境界を通っていなかったため失敗。動的な参照へ直して成功。
初回nginx試験は、高ポート環境のnginxが転送先URLへ試験用portを付けたためURL文字列比較で失敗。
転送先のscheme/hostname/pathを確認する形へ直し、通常の本番443でportが省略される仕様と区別して成功。
初期の通常sandboxでのGit状態読取りは権限環境で失敗し、適切な読取り権限で既存worktreeのcleanを確認した。
失敗を隠すために本番や実装の拒否条件を緩めていない。

## 【6】本番配備案（未実施・別承認）

### 対象と影響

1. 切替直前に既存方式でB2B DBの手動暗号化バックアップを取得。HDD保存、SHA/AES認証、隔離復号、SQLite/FK/schema、ACKを確認。
2. 候補b7ad25bを新規release `/opt/apps/fortune-mari/releases/b7ad25be2f31976941e54e1fe200e799ed382fd0` へ配置。
   アプリソースが全回帰/build済みb252997と一致すること、流用buildの対応をhash照合する。
3. 先生API8771と管理者API8772を同じ候補へ揃える。境界/共通履歴コードの取り違えを防ぎ、adminから鑑定を開放しない。
4. 共用B2B Web3011も候補へ切替。候補検索1行の変更に必要。3つのB2Bサービスだけ短時間再起動。
   B2C Web/APIは停止/再起動しない。既存User/Org/所属/契約/SMTP/AESを再利用し、DB schema変更なし。
5. 3つのvhostと3つのheader snippetを配置し、構文検査成功時だけnginx reload。
   B2Cはヘッダー以外の経路を変えない。先生の教室なし鑑定拒否と入口誘導を追加。
6. 既存更新経路を再確認し、競合がなければroot所有0755でdeploy hookを専用パスへ配置。
   既存renewal設定・timerは書き換えず、B2C installerに重複適用しない。

本番配備の明示承認範囲には、上記B2B3サービスの切替/短時間再起動、3vhost/snippetの反映とnginx reload、
先生/admin限定hook設置と下記承認後試験、直前バックアップを含める必要がある。main統合・課金・定期バックアップは含めない。

### 承認後の確認

通常TLSで3ドメインの画面/401/403/404/単一ヘッダー/no-store/cookie/帳票を確認。
本人の正規B2B入力→鑑定→保存→出力、管理画面と先生管理の分離を確認。
実顧客の契約停止・権限変更を試験のために行わない。契約状態の行列は隔離合成試験を利用する。

先生/adminのwebroot更新試験は、次を別承認後に1件ずつ実行する案。

```sh
sudo /snap/bin/certbot renew --cert-name mari-mutsuro.hakase-uranai.jp --dry-run --run-deploy-hooks
sudo /snap/bin/certbot renew --cert-name admin.hakase-uranai.jp --dry-run --run-deploy-hooks
```

これらは外部ACME通信/作業ファイルと実hookのnginx reloadを伴い得るので、今回実行していない。
dry-runは本物の新しい証明書を本番へ保存する試験ではなく、hookは現行の有効証明書で実行される。
B2C nginx installerのdry-runは一時的な設定書換え/reloadを伴い得るため、この限定2件と混同しない。
更新成功とreload成功、実際に配信している証明書の一致は別々に確認する。

### rollback

- 切替前に各unit/env/vhost/snippet/hookの存在・所有者・mode・hashを非公開専用領域へ保存。
- 問題時はB2B Webを0f53804、先生/管理者APIを7670845の保存unitへ戻し、B2B3サービスだけ再起動。
- vhost/snippetを元の正確な内容へ戻し、nginx -t成功後reload。B2C Web/APIを再起動しない。
- 新hookは実行を止める専用退避先へ移して無効化。既存ファイル削除やrenewal/timer変更はしない。
- 書換え前後のhash、3ドメインHTTPS/境界/ヘッダーとB2C正常性を再確認。
- DBを過去へ戻すSQL/原本置換は行わず、配備中のUser/契約/招待変更を保全する。
- HSTSは配信済みブラウザーに最大5分残る。nginxを戻しても即時に解除できない。

## 【7】記録と終了状態

候補コード/設定/試験/本書は専用branchへ通常commit/pushする。
実環境snapshot、元設定のhash、試験ログ/画像、限定承認後に取得した件数集計は開発元outputsの非公開専用領域へ保管。
秘密鍵/SMTP資格情報/顧客本文/非公開SSH情報をGit/Notion/通常ログへ保存しない。
Notion Sessions DBへ新しい監査是正記録を作成し、参照・再現・失敗と修正・試験・未確定条件を記録する。

開始/終了のサービス状態/PID/配置先、対象nginx/renewal/env設定hash、DBファイルhash/属性を比較し、すべて一致した。
今回作った隔離nginx/UIプロセスだけを終了し、既存13 worktree/refsと確認用プロセスを維持する。
本番の実reload/dry-run/更新・DB更新・実メール・新しい本番バックアップ・定期ジョブは行っていない。
終了時の正確なGit HEAD、origin一致、clean、保護比較結果は最終報告と非公開summaryへ記録する。
グローバル/プロジェクトの作業ルールに未解決の競合はない。提携終了時の先生権限運用と閲覧方針の留保は上記のとおり。

## 【8】次の作業

今回の新規利用制限・最小ヘッダー・限定更新hookは隔離検証済みで、本番配備承認前まで準備した。
ただし本番は修正前のままなので、脆弱性を解消済みとは報告しない。

本人判断/承認が必要なもの：

1. 本番への上記具体的配備と更新試験。
2. 休止/解約後の本人履歴閲覧。推奨案は新規処理を禁止して本人の過去履歴は読み取りだけ許可するものだが、今回未採用。
3. 先生の提携終了記録と所属権限停止の運用/自動連動の要否。生徒の有効契約は維持する。
4. 外部サイトに正当なiframe用途がある場合の例外方針。今回コード/資料では用途なし。

3つの履歴スコープ件数の限定承認・取得・PC保存は完了した。上記の本番配備や商品方針の承認とは区別する。

本番のバックアップ自動運用、OSユーザー/鍵分離、監視やMFA等は今回の是正へ混ぜず、別途指示を待つ。
