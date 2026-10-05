# Phase 7A 本番認証・利用者識別基盤

## 認証構造

`POST /api/auth/login` → Argon2idによるパスワード照合 → 32 bytesの暗号学的乱数session token → HttpOnly Cookie。
以後はサーバー側でsessionのhash・期限・無効化状態・users.statusを照合し、内部UUIDのuser_idを決定する。
query、JSON、任意header、localStorage、frontend stateのuser_idは認証に使用しない。
JWT、自由登録、初期ユーザーのハードコード、管理者API、管理画面は追加していない。

同じoriginのNext.js `/api/*` rewriteを通してPython APIを呼ぶ。`NEXT_PUBLIC_FORTUNE_API_URL` は未設定または空にする。
ブラウザと別originのAPIへ認証Cookieを転送する構成は今回の対象外。

## DBと追加migration

認証とPhase 4履歴は同じ `FORTUNE_HISTORY_DB_PATH` のSQLiteを使用する。
`AuthRepository` 初期化時に `CREATE TABLE/INDEX IF NOT EXISTS` で追加する。既存テーブルのDROP、初期化、再計算、所有者変更は行わない。

| テーブル | 主な内容 |
| --- | --- |
| users | UUID id、表示email、比較用normalized_email UNIQUE、password_hash、active/disabled、作成/更新時刻 |
| auth_sessions | token_hash PRIMARY KEY、user_id外部キー、作成時刻、expires_at、revoked_at |
| auth_login_attempts | IPと比較用emailのhash、試行時刻。期限を過ぎた試行記録だけを除去 |

既存persons/reading_groups/readings/snapshotはそのまま保持する。過去の開発用ownerの履歴を新しい実アカウントへ自動移管しない。
追加migration後も元ownerを使った既存履歴の読み取りが可能であることを、一時DBの全行比較で確認する。
既存データの所有者移管が必要になった場合は、対象と移管先を確認して別工程で行う。

## Passwordとemail

正式依存 `argon2-cffi==25.1.0`。Argon2id、memory 64 MiB、time cost 3、parallelism 4、salt 16 bytes、hash 32 bytes。
DBへ保存するのはsaltとパラメータを含む標準PHC形式のhashだけ。平文passwordをログ・引数・環境変数・ファイルへ残さない。
存在しないemailにもdummy hash照合を行い、不存在・不一致・disabledは同じ外部メッセージと401にする。

emailは前後空白除去とcasefoldで比較し、domainも大文字小文字を区別しない。dot除去・plus除去等は行わない。
管理者設定passwordは暫定運用値として12〜1024文字、loginは入力上限1024文字。

## Session・Cookie・失効

session tokenは `secrets.token_urlsafe(32)` で発行し、DBにはSHA-256だけを保存する。高エントロピーのtoken用hashであり、password用hashとは区別する。
Cookie名 `fortune_session`、HttpOnly、SameSite=Lax、Path=/、Domain指定なし。
`FORTUNE_ENV=production` のときSecureを付ける。CookieとDBの期限は同じ設定値を使う。

loginごとに新tokenを発行し、ブラウザの旧sessionをrevokeする。logoutはDB revokeとCookie削除の両方を行う。
disableおよびset-passwordはそのuserの全sessionをrevokeする。enableしても旧sessionを復活させない。
認証のたびにusers.statusを確認するので、DB上でdisabledとなったsessionも使えない。
期限切れ・revoked・未知のtokenは401。期限は滑動更新せず、loginからの絶対期限とする。

## 設定

以下の既定値は商品仕様として確定した値ではなく、集中管理した暫定技術設定。

| 環境変数 | 用途／既定値 |
| --- | --- |
| FORTUNE_ENV | 本番は正確に `production`。開発は `development` |
| FORTUNE_HISTORY_DB_PATH | 本番はサービス利用者が書き込める永続SQLiteの絶対パスを明示。未設定時はrepo/data/history.sqlite3 |
| FORTUNE_PUBLIC_ORIGIN | 本番は `https://app.hakase-uranai.jp` 等の実際の公開originを明示。pathを含めない |
| FORTUNE_SESSION_TTL_HOURS | session絶対期限。既定24時間、1〜8760 |
| FORTUNE_LOGIN_WINDOW_SECONDS | login試行計数窓。既定900秒 |
| FORTUNE_LOGIN_ACCOUNT_LIMIT | emailごとの窓内試行上限。既定10 |
| FORTUNE_LOGIN_IP_LIMIT | 接続元IPごとの窓内試行上限。既定30 |
| FORTUNE_HISTORY_DEV_USER_ID | 明示的な開発固定ownerだけ。productionでは常に無視 |
| FORTUNE_PDF_CONVERTER | Windows検証は `windows_excel`。Linux converterは未実装 |

本番で公開originが未設定・不正・HTTPなら認証書き込みを503で拒否する。正常な未認証の所有者機能は401。
Cookieがある場合にsessionが無効でも開発固定ownerへfallbackしない。
`start-local.ps1` はdevelopmentを設定するが固定ownerを自動発行しない。既存回帰用に必要なら管理者が明示的に設定する。
通常の開発認証検証では `FORTUNE_HISTORY_DEV_USER_ID` を未設定にする。

## APIとUI

| API | 応答 |
| --- | --- |
| POST /api/auth/login | JSON email/password。成功は200＋Cookie＋authenticated/user id/email |
| POST /api/auth/logout | JSON `{}`。session revoke＋Cookie削除。未sessionでも200 |
| GET /api/auth/me | 200＋authenticated/user id/email。未認証401。password hashは返さない |

認証・履歴・出力・鑑定API応答はCache-Control: no-store。storage/configurationエラーは安全な固定日本語応答と503。
login入力不正は422、送信元不一致403、JSON以外415、試行上限429＋Retry-After。
login画面 `/login`、全体のログイン表示とlogout、履歴・保存・出力のログイン導線を追加。
通常鑑定 `/` → `/result` は未ログインでも使える。匿名鑑定へexport tokenは発行しない。
匿名状態では保存・出力ボタンを表示せずログイン案内を表示する。認証後は再鑑定する。
login/logout/利用者切替/認証失効を検知したときは共有結果と再鑑定draft・ページ内情報を破棄する。
遅れて届いた前画面の鑑定・保存・再鑑定・download応答が、切替後の画面を更新しない。
定期確認とfocusでsession失効・他タブの切替を確認する。API側は毎回即時確認する。

## Phase 4／5の所有者接続

履歴保存・一覧・詳細・candidate・人物更新・group memo・memo保存・soft delete・rerunはサーバーsessionのuser_idで既存SQLのowner条件を使う。
別userのperson/group/readingは404。存在の有無を第三者へ詳しく開示しない。
保存済みExcel/PDFは同じowner確認後、当時のsnapshotから生成し再計算しない。
未保存tokenはuser_idと発行sessionのhashに結び付ける。同じuserでも別sessionでは使えない。
logout・期限切れ・disabledではAPI認証で拒否する。token自体の既存期限1時間・上限256件も維持する。
未保存tokenは現在も単一Pythonプロセス内保持。複数workerの共有ストレージは後続工程。
PDFは既存完成Excelを変換する。A4縦2ページの既存テンプレート・占術計算は変更していない。

## CSRF・proxy・試行制限・ログ

書き込み時にCookie SameSiteとOrigin（またはRefererのorigin）を確認し、JSON Content-Typeを必須にする。
本番の許可originはサーバー環境設定から確定し、任意X-Forwarded-Host/Protoを信用しない。
Sec-Fetch-Site: cross-siteも拒否する。履歴・出力・認証に加え、Cookie付き鑑定POSTも対象。
Originなしは拒否。例外はCookieなし＋明示的開発固定ownerの既存非ブラウザ回帰クライアントのみで、auth APIには適用しない。

IP/emailの試行制限はSQLiteでtransactionとして計数し、同じDBを使うworker/restart間でも維持する。
IPは接続元を使用する。`server.py` 起動はproxy headersを無効にする。
uvicorn CLIを使う本番サービスでは `--no-proxy-headers` とするか、管理されたproxyが外部のForwarded情報を除去し信頼境界を確定してから別途設計する。
proxy headers無効でreverse proxyを通す場合、IP上限はproxy接続元を共有するため実質的に全体上限となる。利用規模に合わせて暫定設定を監査する。
分散rate limit、強いbot対策、運用監視は後続工程。
password/hash/raw session/Cookie全文/private鑑定内容を認証ログへ出さない。APIアクセスログは無効で検証する。

## 管理者CLI

repo直下から、Windowsは `.\.venv\Scripts\python.exe`、VPSは配備先のvenv Pythonで実行する。

```text
python scripts/manage_user.py create --email user@example.test
python scripts/manage_user.py disable --email user@example.test
python scripts/manage_user.py enable --email user@example.test
python scripts/manage_user.py set-password --email user@example.test
```

create/set-passwordではgetpassによる非表示入力＋再入力を求める。引数によるpassword指定機能はない。
入力を隠せない端末・非対話入力は拒否する。emailは例示であり、実アカウントをコードやGitへ登録しない。
CLIはOS上でDBへアクセスできる管理者の経路。利用者向けWeb APIとして公開しない。

## VPS配備前に別途必要な作業

1. 今回はVPSを変更しない。配備指示を受けてから、旧HEAD・service・DB・作業ツリーを再監査する。
2. SQLiteの既存データとownerを確認し、配備時のDB控えと復元手順を準備する。repo内一時DBへ置き換えない。
3. 本番venvへrequirementsの追加依存を反映し、service利用者のDBディレクトリ権限を確認する。
4. FORTUNE_ENV=production、永続DB絶対path、HTTPS公開origin、session期限・login上限をserviceへ設定する。
5. FORTUNE_HISTORY_DEV_USER_IDを本番の代用にしない。Next.jsから同origin `/api/*` を使い、Cookie・Origin・Content-Typeが届くことを確認する。
6. 管理者CLIを同じservice用DB設定で実行し、実userを対話入力で発行する。秘密値はGit・.env・shell引数へ書かない。
7. Uvicornのproxy header信頼境界とworker数を確認する。未保存tokenが単一プロセス保持のため、当面単一workerを前提に監査する。
8. Linux PDF未対応時の出力UI・機能公開方針を別途確定する。Windows adapterをUbuntuへ設定して代用しない。
9. restart後、匿名通常鑑定、HTTPS Cookie、login/logout、401、A/B owner分離、保存snapshot、Excel、PDF未対応表示を確認する。

## 検証の実行

```text
python -B tests/auth_cases.py
python -B tests/history_cases.py
python -B tests/report_export_cases.py
python -B tests/report_pdf_cases.py
python -B tests/check.py
```

frontendは `tsc --noEmit --incremental false` と `next build`。
`tests/auth_ui.cjs` は既存Playwright/Edge/Excelを使用し、空いている8765/3000ポートへ専用serverを起動する。
毎回新しい検証DBを作成し、架空A/B・ランダムpasswordをmemory/stdinで渡す。秘密値をログや検証JSONへ保存しない。
PC1280px/スマホ375pxで匿名鑑定・導線・login error・A login・保存・履歴・未保存/保存Excel/PDF・logout・遅延応答・B分離を確認する。
終了時は自分が起動したPIDのserverだけを停止する。利用者のserverやExcelを一括停止しない。
PDFの既存比較テストは、ZIP作成時刻の差で失敗しないよう全展開エントリの完全一致を確認する。
未認証productionの既存期待値503は新仕様401へ変更した。他の占術期待値は変更していない。

## 参照した一次資料

- [argon2-cffiの正式配布情報](https://pypi.org/project/argon2-cffi/25.1.0/)
- [OWASP CSRF対策](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)

## 今回の対象外

パスワード再設定メール、SMTP、OAuth、自由登録、本番クラウドDB全面移行、30日後物理削除、バックアップ・監視基盤、管理画面、契約・料金管理、Linux PDF converter、Phase 6ブランド調整。

## 2026-10-05 実装・検証結果

開始：main、HEAD/local origin/main/GitHub mainは `30f3ee63fa90da5454e0e147ef516dcc8b5b7c00`、working tree clean。
共通 `C:\Users\bunch\.codex\AGENTS.md` を参照。正本直下・配下のAGENTS.mdは存在しない。
今回の明示実装指示と共通方針に衝突なし。NotionのSessions記録と商品版ロードマップは参照のみで更新していない。

| 確認 | 最終結果 |
| --- | --- |
| Phase 7A auth / CLI / migration / spoof / owner / CSRF | 44/44 PASS |
| Phase 4 history | 32/32 PASS |
| Phase 5 Excel | 46/46 PASS |
| Phase 5 PDF | 21/21 PASS |
| 占術 Tier A | 524/524 PASS |
| 占術 Tier B | 38/38 一致、REVIEW 0 |
| TypeScript / Next.js production build | PASS |
| PC1280px / スマホ375px UI・A/B E2E | 28/28 PASS |
| 実機PDF4ファイル（未保存/保存、PC/スマホ） | すべてA4縦2ページ、595.2×841.44pt |
| PC/スマホのlogin error・結果画面の目視 | 文字・入力欄・ボタンに崩れなし |
| diff --check | PASS |

検証成果物：`C:\Users\bunch\Documents\Codex\fortune-app\outputs\phase7a-auth-20261005-final`。
`ui_verification.json`、PC/mobileのanonymous・login error・history・result画面PNG、未保存/保存のExcel/PDFを保存。
架空アカウントの専用検証DBを使用し、既存の利用者保存DBへテストデータを作成していない。
検証用8765/3000のserverは終了時に停止し、両ポートの待受がないことを確認。
VPS、既存占術ロジック、鑑定書テンプレート、共通ルールファイルは変更していない。
Tier Cの既知6項目は従来のまま。今回の重大な未解決事項はなし。

新規9ファイル：`auth_service.py`、`fortune-next-app/backend/auth_api.py`、`scripts/manage_user.py`、
`fortune-next-app/app/auth.tsx`、`fortune-next-app/app/auth.css`、`fortune-next-app/app/login/page.tsx`、
`tests/auth_cases.py`、`tests/auth_ui.cjs`、本書。

変更17ファイル：`requirements.txt`、`report_export_service.py`、`report_pdf.py`、
`fortune-next-app/backend/server.py`、`history_api.py`、`export_api.py`、`start-local.ps1`、
`fortune-next-app/app/layout.tsx`、`main-fortune.tsx`、`history-client.ts`、`history-controls.tsx`、`report-export.tsx`、
`fortune-next-app/app/history/page.tsx`、`fortune-next-app/app/history/[historyId]/page.tsx`、
`tests/history_cases.py`、`tests/report_export_cases.py`、`tests/report_pdf_cases.py`。
