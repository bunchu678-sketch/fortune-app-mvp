# VPS final predeploy audit / deployment runbook

監査日：2026-10-06（Asia/Tokyo）。本書のVPS変更コマンドは夜間には一つも実行していない。
本番変更はユーザーの明示承認後だけ。sudo password、初期利用者passwordは本人が対話端末に入力し、チャット・Git・コマンド引数・ログには残さない。

## 1. 次回Codexへ渡す実行指示

本書を読んで配備する。開始時、ローカルmain・origin/main・GitHub mainの一致とcleanを確認し、
ユーザーが承認した最終報告のcommitをTARGETとして固定する。動くorigin/mainだけを根拠に別commitを配備しない。
VPSはnatsuki@162.43.22.37、repo /opt/apps/fortune-app、venv /opt/venvs/fortune-app。
VPS main / clean / HEAD d8fe9a970ddae6fa0a6b58115164a0b1825c2075、API/Web正常、HTTPS200、HTTP301を再確認する。
出所不明の差分、未知DB、異常稼働なら停止。fetchは本番変更承認前にしない。

まずユーザー操作でsudo認証し、**読み取り検査だけ**を行う：

```bash
sudo -v
sudo -n nginx -T
sudo -n nginx -t
```

nginx -Tは秘密headerや設定値を出力する可能性があるため、Codexはサーバー側で秘密行を伏せてから結果を取得する。
特権を恒久付与する変更やNOPASSWD設定はしない。sudo認証が失効した場合も本人が再入力する。
全includeが本書の監査内容と一致し、構文検査成功の場合のみ「ここから本番変更」と宣言してStep 3以降へ進む。
夜間はsudo: パスワードが必要ですで検査できなかった。この確認を省略しない。

## 2. read-only監査結果

| 項目 | 結果 |
| --- | --- |
| ローカル開始 | main、8f481fe20943cea4d987b080801a23ea98215489、clean、GitHub/origin一致 |
| VPS | main、d8fe9a970ddae6fa0a6b58115164a0b1825c2075、clean |
| remote | https://github.com/bunchu678-sketch/fortune-app-mvp.git |
| API / Web / nginx | active・running・enabled。API PID243548、Web MainPID203393、Next PID203407、nginx PID243562 |
| runtime | Ubuntu24.04.4、Python3.12.3、Node24.17.0、Corepack0.35.0、pnpm11.7.0（cache/package.jsonも確認） |
| API / Web listener | 127.0.0.1:8765 / 127.0.0.1:3000 |
| 公開 / health | HTTPS / 200、HTTP→HTTPS301、localhost API health200 |
| services | natsuki:natsuki、WorkingDirectory=/opt/apps/fortune-app/fortune-next-app、Restart=on-failure、RestartSec=5、UMask=0022 |
| EnvironmentFile / drop-in | 現在なし。APIにFORTUNE_*なし、Web NODE_ENV=production |
| Next .env系 | .env / .env.local / .env.production / .env.production.localは存在しない |
| DB | repo内の限定探索でDB/sidecarなし、/var/lib/fortune-appなし。DBは開いていない |
| argon2-cffi | VPS未導入 |
| 容量 | repo398M、venv539M、対象FSの空き138G |
| nginx include | conf.d / modules-enabled空、sites-enabledはdefaultとfortune-app。Certbot SSL includeは読み取り確認 |
| nginx -T/-t | sudo passwordが必要なため未確認 |
| rollback DB互換 | 旧HEADにauth/history DBモジュール・Python sqlite参照なし。旧コードは追加DBを読み書きしない |

本番採用はB：Webはnginx→Next.js、/api/はnginx→Python。Aの2段proxyはNext.jsのXFF転送規則まで監査が必要。
Bは同originとCookie契約を維持し、境界で外部headerを上書きし、復旧対象をappのnginx locationに限定できる。
信頼対象はlocalhostプロセスであるため、OSアカウントの管理が前提。APIは1 worker、未保存tokenは1時間/256件、restartで消失。

## 3. EnvironmentFile完成案

配置先：/etc/fortune-app/production.env、root:root、0600。systemdがrootで読みAPIへ渡す。秘密値は含めない。

```ini
FORTUNE_ENV=production
FORTUNE_PUBLIC_ORIGIN=https://app.hakase-uranai.jp
FORTUNE_HISTORY_DB_PATH=/var/lib/fortune-app/history.sqlite3
FORTUNE_PDF_CONVERTER=disabled
FORTUNE_SESSION_TTL_HOURS=24
FORTUNE_LOGIN_WINDOW_SECONDS=900
FORTUNE_LOGIN_ACCOUNT_LIMIT=10
FORTUNE_LOGIN_IP_LIMIT=30
FORTUNE_PROXY_HEADERS=1
FORTUNE_TRUSTED_PROXY_IPS=127.0.0.1
```

| 設定 | 区分 | コードdefault | purpose / production値 |
| --- | --- | --- | --- |
| FORTUNE_ENV | 必須 | 未設定はproduction扱いにならない | production判定/Secure Cookie。production |
| FORTUNE_PUBLIC_ORIGIN | 必須 | 空 | CSRF許可origin。上記HTTPS、pathなし |
| FORTUNE_HISTORY_DB_PATH | 運用必須 | repo/data/history.sqlite3 | 永続DB絶対path。上記/var/lib |
| FORTUNE_PDF_CONVERTER | 推奨 | Linuxではdisabled、Windows developmentではwindows_excel | Ubuntuはdisabled |
| FORTUNE_SESSION_TTL_HOURS | 任意 | 24 | 絶対期限、1～8760。24 |
| FORTUNE_LOGIN_WINDOW_SECONDS | 任意 | 900 | 計数窓、1～86400。900 |
| FORTUNE_LOGIN_ACCOUNT_LIMIT | 任意 | 10 | email上限、1～1000。10 |
| FORTUNE_LOGIN_IP_LIMIT | 任意 | 30 | IP上限、1～10000。30 |
| FORTUNE_PROXY_HEADERS | 任意 | 0 | 境界完成後1。0/1以外拒否 |
| FORTUNE_TRUSTED_PROXY_IPS | 任意 | 127.0.0.1,::1 | 実upstreamに合わせ127.0.0.1。localhost2個以外拒否 |
| NEXT_PUBLIC_FORTUNE_API_URL | Web任意 | 空 | build/runtimeとも空、同origin /api |
| NODE_ENV | Web推奨 | Next startのproduction | production |
| FORTUNE_HISTORY_DEV_USER_ID | production禁止 | 空 | 本番で設定しない。設定されてもproductionでは無視 |

proxy設定はserver.py mainで読む。uvicorn CLIへ起動方式を変更しない。

## 4. systemd完成差分

既存base unitは保持する。API drop-in /etc/systemd/system/fortune-app-api.service.d/production.conf：

```ini
[Service]
EnvironmentFile=/etc/fortune-app/production.env
UMask=0077
```

有効API完成形（base＋drop-in）：

```ini
[Unit]
Description=Fortune App FastAPI service
After=network.target
[Service]
Type=simple
User=natsuki
Group=natsuki
WorkingDirectory=/opt/apps/fortune-app/fortune-next-app
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/etc/fortune-app/production.env
UMask=0077
ExecStart=/opt/venvs/fortune-app/bin/python /opt/apps/fortune-app/fortune-next-app/backend/server.py
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
```

Web drop-in /etc/systemd/system/fortune-app-web.service.d/production.conf：

```ini
[Service]
Environment=NEXT_PUBLIC_FORTUNE_API_URL=
```

Web baseのUser/Group=natsuki、WorkingDirectory同上、HOME=/home/natsuki、PATH=/usr/local/bin:/usr/bin:/bin、
NODE_ENV=production、ExecStart=/usr/local/bin/corepack pnpm start、Restart=on-failure/5秒、
Wants/After=fortune-app-api.service、WantedBy=multi-user.targetを維持する。Web EnvironmentFileは不要。
API mainがworkers=1を渡す。Webのbuild worker数はAPI worker数ではない。

## 5. nginx完成差分

対象は/etc/nginx/sites-available/fortune-app（sites-enabledから既存symlink）。他サイト・global・Certbot証明書は変更しない。
現在のlocation /だけを以下の2 locationへ置換する。

```diff
+    location ^~ /api/ {
+        proxy_pass http://127.0.0.1:8765;
+        proxy_http_version 1.1;
+        proxy_set_header Host $host;
+        proxy_set_header X-Real-IP $remote_addr;
+        proxy_set_header X-Forwarded-For $remote_addr;
+        proxy_set_header X-Forwarded-Proto $scheme;
+        proxy_set_header X-Forwarded-Host $host;
+        proxy_set_header Forwarded "";
+        client_max_body_size 1m;
+        proxy_read_timeout 60s;
+        proxy_send_timeout 60s;
+    }
     location / {
         proxy_pass http://127.0.0.1:3000;
         proxy_http_version 1.1;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
-        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
+        proxy_set_header X-Forwarded-For $remote_addr;
         proxy_set_header X-Forwarded-Proto $scheme;
+        proxy_set_header X-Forwarded-Host $host;
+        proxy_set_header Forwarded "";
+        client_max_body_size 1m;
+        proxy_read_timeout 60s;
+        proxy_send_timeout 60s;
     }
```

完成サイトは現行server_name=app.hakase-uranai.jp、IPv4/IPv6 listen443 ssl、
/etc/letsencrypt/live/app.hakase-uranai.jp/fullchain.pem・privkey.pem、options-ssl-nginx.conf・ssl-dhparams.pemを維持。
2つ目のHTTP80 serverの301 https://$host$request_uriと未知Host404もそのまま。
proxy_passへURI末尾/を追加しない（/api/を保つ）。Cookie/Set-Cookie、Origin、Content-Typeを除去しない。
API/Webとも外部XFFを追記せずremote_addrへ上書き。Forwardedも除去。CSRFは公開originを使用。

## 6. backup / 保守表示（承認後だけ）

Codexは各段階の終了コードを確認し、非0なら次へ進まない。以下はnatsukiのSSH対話端末で実施する。
TARGETは開始時に固定した承認commit、DB=/var/lib/fortune-app/history.sqlite3、ROLLBACKは実測旧HEAD。

```bash
umask 077
DEPLOY_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
B=/var/backups/fortune-app/$DEPLOY_STAMP
DB=/var/lib/fortune-app/history.sqlite3
ROLLBACK=d8fe9a970ddae6fa0a6b58115164a0b1825c2075
sudo -n install -d -o root -g root -m 0700 /var/backups/fortune-app "$B"
git -C /opt/apps/fortune-app rev-parse HEAD | sudo -n tee "$B/git-head.txt"
sudo -n cp -a /etc/nginx/sites-available/fortune-app "$B/original-site.conf"
sudo -n tar --acls --xattrs --numeric-owner -cpf "$B/config.tar" -C / etc/nginx etc/systemd/system/fortune-app-api.service etc/systemd/system/fortune-app-web.service
```

新しいdrop-in/envを作る前に存在/不存在をmanifestへ記録する。今回の監査ではすべて不存在。
再監査で存在した場合はその内容と用途を確認し、既存drop-in・/etc/fortune-appもconfig.tarへ含める。未知設定を上書きしない。
所有権・mode・symlink先・services enabled状態・pip freeze・Node/Corepack/pnpm version・requirements・lockfileを控える。
pip freezeは旧venvで実行してroot専用backupへ保存。秘密環境値やprivate DB内容をmanifestに出さない。

予定停止中の502を避けるため、設定控え後、original-site.confの最初のHTTPS `server {` 直後に
`return 503;` を1行挿入したmaintenance-site.confをB内で作る（HTTP301は保持）。
変更箇所がその1行だけであることをdiff確認し、次を順に実施：

```bash
sudo -n install -o root -g root -m 0644 "$B/maintenance-site.conf" /etc/nginx/sites-available/fortune-app
sudo -n nginx -t
sudo -n systemctl reload nginx
sudo -n systemctl stop fortune-app-web.service fortune-app-api.service
sudo -n tar --acls --xattrs --numeric-owner -cpf "$B/repo.tar" -C /opt/apps fortune-app
sudo -n tar --acls --xattrs --numeric-owner -cpf "$B/venv.tar" -C /opt/venvs fortune-app
```

maintenanceの構文検査が失敗したらoriginal-site.confを復元し、reloadせず停止。以降に進まない。
full repo archiveはGit・node_modules・.nextを含み、停止後なのでbuild/cacheの混在を避ける。
空き容量を再確認し、tar失敗、途中変更、読めないファイルを無視しない。

### SQLiteあり／なしの分岐

未知のDBが見つかったら夜間指示の絶対停止条件に従い停止。用途を確認できたDBだけが以下の対象。

- DBなし：manifestに不存在を記録。backup用に空DBを作らない。次のschema工程で新規作成。
- DBあり：API/Webと他の書き込み元の停止を確認し、metadata/sidecarを記録。Python標準SQLite backup APIで整合したbackupを作る。

既知DBをbackupする完成例（DB/Bの絶対pathを渡す。標準sqlite3だけ）：

```bash
sudo -n python3 - "$DB" "$B" <<'PY'
import os,sqlite3,sys
from pathlib import Path
os.umask(0o077)
src=Path(sys.argv[1]);dest=Path(sys.argv[2])/'history.sqlite3.backup'
if not src.is_file():raise SystemExit('Source DB missing; no implicit creation')
source=sqlite3.connect(src.resolve().as_uri()+'?mode=ro',uri=True)
backup=sqlite3.connect(str(dest))
try:
    source.backup(backup)
    if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Backup integrity failed')
finally:
    backup.close();source.close()
print('SQLite backup integrity: ok')
PY
```

-wal/-shm/-journalがある場合は所有者/mode/sizeとjournal modeを記録する。
本体だけのcpを整合backupと扱わない。backup APIの単独ファイルはcheckpoint済みの整合copyで、元sidecarの再生は不要。
障害調査用にsidecarを保全する場合も、書き込み元停止を確認した同じ時点の一式を扱う。

```bash
sudo -n tar -tf "$B/repo.tar" >/dev/null
sudo -n tar -tf "$B/venv.tar" >/dev/null
sudo -n tar -tf "$B/config.tar" >/dev/null
sudo -n sh -c 'cd "$1" && sha256sum *.tar > SHA256SUMS && sha256sum -c SHA256SUMS' sh "$B"
```

DB backupもhashをmanifestへ追記し、integrity_check成功を記録。archiveの復元対象pathが想定prefix内であることを確認する。
backup失敗時はコードを更新せず、必要なら旧servicesとoriginal-siteを復帰して終了。

## 7. DB / migration完成手順

backup検証後に以下を準備：

```bash
sudo -n install -d -o natsuki -g natsuki -m 0700 /var/lib/fortune-app
sudo -n install -d -o root -g root -m 0700 /etc/fortune-app
sudo -n install -d -o root -g root -m 0755 /etc/systemd/system/fortune-app-api.service.d /etc/systemd/system/fortune-app-web.service.d
```

EnvironmentFileとdrop-inは本書の完成内容でroot所有ファイルとして作成。env0600、drop-in0644。
nginx完成候補はBに保存し、まだmaintenanceを公開したままにする。

既存DBありの場合、owner/mode/親directoryが計画と一致するか先に確認。未知DBをchownして奪わない。
CLIとAPIの指定pathを同じ絶対pathにする。repo/dataを代用しない。

コード/dependency/build成功後、natsukiで明示的にschemaを初期化：

```bash
cd /opt/apps/fortune-app
umask 077
env FORTUNE_ENV=production FORTUNE_HISTORY_DB_PATH=/var/lib/fortune-app/history.sqlite3 /opt/venvs/fortune-app/bin/python -B - <<'PY'
import hashlib,json,sqlite3,os
from pathlib import Path
from auth_service import AuthRepository
from history_repository import SQLiteHistoryRepository
p=Path(os.environ['FORTUNE_HISTORY_DB_PATH'])
def history_state():
    if not p.exists():return {}
    with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
        present={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {t:hashlib.sha256(json.dumps(db.execute('SELECT * FROM '+t+' ORDER BY id').fetchall(),ensure_ascii=False).encode()).hexdigest() for t in ('persons','reading_groups','readings') if t in present}
before=history_state()
AuthRepository();SQLiteHistoryRepository(p)
after=history_state()
if any(after.get(t)!=digest for t,digest in before.items()):raise SystemExit('Existing history changed; STOP')
with sqlite3.connect(p) as db:
    required={'users','auth_sessions','auth_login_attempts','persons','reading_groups','readings'}
    present={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required<=present or db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Schema/integrity failed')
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:raise SystemExit('Foreign key check failed; STOP')
print('Schema and existing history preservation: ok')
PY
chmod 0600 /var/lib/fortune-app/history.sqlite3
stat -c '%n %U:%G %a' /var/lib/fortune-app /var/lib/fortune-app/history.sqlite3
```

AuthRepositoryを先に、historyを次に初期化。CREATE IF NOT EXISTSで追加するだけ。DROP・既存owner移管・再計算なし。
API起動自体はDBを初期化しないが、login・Cookie付き認証や履歴利用でもrepository初期化は起きる。
DDL全体を一括rollbackする専用migration transaction/version管理はない。
失敗時はサービスを起動せず、失敗DBを保全し、原因と既存table互換を確認。IF NOT EXISTSの再実行は確認後だけ。
未確認のschemaへ繰り返し実行しない。DBをreset/DROPして回避しない。

## 8. initial user完成コマンド

natsukiのTTY付きSSH端末で、emailだけを対話取得し、CLIのgetpassでpasswordを2回入力：

```bash
read -r -p '初期利用者email: ' INITIAL_EMAIL
env FORTUNE_ENV=production FORTUNE_HISTORY_DB_PATH=/var/lib/fortune-app/history.sqlite3 /opt/venvs/fortune-app/bin/python -B /opt/apps/fortune-app/scripts/manage_user.py create --email "$INITIAL_EMAIL"
```

password12～1024文字、非表示入力。echo/stdin pipe/env/password引数に置き換えない。CLIはEnvironmentFileを自動読込しない。
重複emailやCLIエラーなら停止し、勝手にset-passwordしない。
作成後の確認は同じ絶対DBに対するreadonly SELECTで該当emailの件数/statusとhash方式だけを判定し、
password_hash/raw sessionを表示しない。公開HTTPSで本人がloginし、meの認証状態を確認する。
初期利用者のemail/passwordは今回未受領・未作成。本人の対話入力は配備時に必要。

## 9. deployment順序と停止条件

| Step | 実行 | failure時 |
| --- | --- | --- |
| 1 | ローカル/GitHub一致、承認TARGETを固定。VPS branch/HEAD/clean・runtime・DB・config再監査 | 不一致/未知DB/未承認commitは停止 |
| 2 | 公開旧版HTTPS200/HTTP301/API health200。本人sudo認証でnginx -T/-tを完了 | 未確認・失敗・異常なら本番変更しない |
| 3 | ユーザー承認を確認し「ここから本番変更」。予定保守表示と復旧targetを宣言 | 承認不足は停止 |
| 4 | 設定backup→maintenance503→API/Web停止→repo/venv/SQLite backup・hash検査 | 失敗なら旧版復帰。Git更新しない |
| 5 | 永続DB directory/owner/permission準備 | 権限/既存DB用途不明は停止 |
| 6 | EnvironmentFile完成案をroot0600で作成 | 内容不一致は停止 |
| 7 | API/Web drop-inを準備（既存unit保持） | 余分な差分なら停止 |
| 8 | nginx完成候補をBへ保存、diffを確認。公開はmaintenanceのまま | HTTPS/HTTP変更や他サイト差分なら停止 |
| 9 | `git fetch origin main`、TARGETがorigin/mainと一致、`git merge --ff-only "$TARGET"`（現在mainから） | fetch/一致/ff失敗ならrollback。resetしない |
| 10 | `/opt/venvs/fortune-app/bin/python -m pip install -r requirements.txt`、`pip check`、argon2/fastapi/uvicorn import | 失敗ならrollback。旧venvを控えてある |
| 11 | fortune-next-appで`corepack pnpm install --frozen-lockfile` | lock変更や導入失敗ならrollback |
| 12 | `env NODE_ENV=production NEXT_PUBLIC_FORTUNE_API_URL= corepack pnpm build`、template/hash確認 | build/template不一致ならrollback |
| 13 | backup確認後、本書のschema手順。history fingerprint/integrity/mode確認 | 失敗DB保全、DB resetせず停止/コードrollback |
| 14 | initial userをTTY CLIで作成 | 不正/重複/入力不能は停止 |
| 15 | `sudo -n systemctl daemon-reload`、API start。health/1 worker/限定trust/DB設定を確認 | 起動・health失敗ならrollback |
| 16 | Web start。localhost:3000の200確認 | 失敗ならrollback |
| 17 | nginx完成候補をsiteへinstall、`sudo -n nginx -t` | 失敗ならmaintenance/original復元、reloadしない |
| 18 | `sudo -n systemctl reload nginx` | 失敗ならrollback |
| 19 | HTTPS /200、HTTP301、匿名鑑定、me401、capability false | 予期せぬ5xx/公開範囲不正ならrollback |
| 20 | initial user login＋me。Cookie値を出力しない | 認証失敗は停止、修正不可ならrollback |
| 21 | Secure/HttpOnly/SameSite、CSRF wrong-origin拒否、wrong password/429 | security失敗なら公開をmaintenanceへ戻しrollback |
| 22 | 最小限の架空A/Bで所有者分離（次節） | 他人資産アクセスなら直ちにmaintenance/rollback |
| 23 | save/list/detail/memo/rerun/delete、snapshot再計算なし | 履歴破損/不整合ならDB保全し停止 |
| 24 | 完成Excelをdownload、template/内容/owner | 失敗なら停止、原因不明はrollback |
| 25 | PDF disabled表示、Excel有効、直接PDFは既知503 | PDF有効表示や未知5xxなら停止 |
| 26 | 通常鑑定を再確認 | 占術差分は勝手に修正せず停止 |
| 27 | 起動/検査開始時以降のAPI/Web/nginx logを秘密非表示で検査 | 想定外5xx/起動loopならrollback |
| 28 | VPS HEAD=TARGET、clean、services enabled/active/running、1 worker、local/GitHub一致。backup場所とsmoke結果を報告 | 不一致を隠さず停止 |

sudo -vは必要時に本人が再入力する。service start/reloadは成功を確認して次へ進める。
DBを変更する操作は指定したproduction DBだけ。テスト用DBを本番にコピーしない。

## 10. HTTPS smoke test詳細

初期利用者のprivate鑑定を試験ログへ保存しない。架空名・少量のtestデータだけを使う。
A/B検証には架空testアカウント2件を専用に発行し、passwordは乱数でmemory/非表示対話入力だけに保持。
既存本人アカウントのpassword変更・disable・rate limit試験はしない。
Codexは本番への操作承認がある次回だけ、ブラウザで以下を確認する。

- 未認証通常鑑定200/ok:true、履歴/保存/export/me401。
- login200、me本人、Secure/HttpOnly/SameSite=Lax/Path=/、JSからCookie不可、logout後me401。
- wrong Origin403、JSON以外415、wrong password401、未知emailも同じ応答。
- rate limitは専用testアカウントに最大11試行で429/Retry-After900。IPの合計試行を30以下に管理し、一般利用を妨げない保守中に行う。
- 外部からXFF/X-Real-IP/Forwardedを偽装してもnginxが上書きし、期待client IPで計数。任意user_idで権限を取得できない。
- Aで架空1件をsave/list/detail/memo更新・再鑑定。保存済みsnapshotからExcel出力。再鑑定で元snapshotを上書きしない。
- BのlistはAを含まず、Aのreading/person/group/memo/export-token/exportを404。失効A sessionも401。
- Aの再鑑定分をsoft deleteし、元履歴は維持。UIで削除確認、detail404。
- PDFはdisabled表示、Excel利用可能。直接PDFのconverter_unavailable503は既知の期待応答。その他の5xxは不可。
- PC1280/375pxで通常鑑定・login・履歴・出力の表示を確認。
- 終了時にtestアカウントをdisableしてsessionを失効。test履歴はsoft delete。DBの物理削除/resetはしない。

log確認はAPI/Web journalとnginx access/errorの検査開始位置以降に限定し、status/件数/エラー分類を報告。
Cookie/password/hash/private入力を含むraw logや全文headerをチャット・artifactへ出さない。
保守中503とPDF未対応の明示503、401/403/404/429を期待応答として区別し、想定外500/502等がないことを確認。

## 11. rollback（コードとDBは別判断）

target：d8fe9a970ddae6fa0a6b58115164a0b1825c2075（当日実測）。
保守表示へ戻し、API/Webを停止。失敗時の新DBをSQLite backup APIでB内へ保全し、元DBは変更しない。
対象pathsとbackup hashを確認してから以下を行う。Bは今回作成した絶対backup directoryを再確認する。

```bash
git -C /opt/apps/fortune-app switch --detach "$ROLLBACK"
sudo -n mv /opt/venvs/fortune-app "$B/failed-venv"
sudo -n tar --acls --xattrs -xpf "$B/venv.tar" -C /opt/venvs
sudo -n mv /opt/apps/fortune-app/fortune-next-app/node_modules "$B/failed-node_modules"
sudo -n mv /opt/apps/fortune-app/fortune-next-app/.next "$B/failed-next"
sudo -n tar --acls --xattrs -xpf "$B/repo.tar" -C /opt/apps fortune-app/fortune-next-app/node_modules fortune-app/fortune-next-app/.next
```

mv対象が欠ける場合はその事実を記録して該当moveだけ省略し、archiveに該当treeが存在することを確認して復元。
移動先がすでに存在する場合は上書きせず、新しい保全先を確定して停止点から再開。
旧Git commitでrequirements/lock/sourceを復旧、venvとWeb dependency/buildは同じpathへarchiveから復旧する。
Git履歴を書き換えずdetached旧HEADで稼働させ、branch状態も報告する。

今回新設したAPI/Web production.confとproduction.envはBのfailed-config保全先へ移動し、削除しない。
元から存在した設定はconfig.tarから対応ファイルだけを復元。base unitとnginx original-site.confも復元する。
他サイトやCertbot証明書を巻き戻さない。daemon-reload→旧API/Web start→localhost正常→nginx -t→reload→HTTPS/301を確認。
復旧検査に失敗したらmaintenanceを維持して停止。繰り返しreset/installしない。

旧HEADはSQLiteを使わないため、追加users/session/history schemaが残ったDBをそのまま保全してコードrollbackできる。
DBを過去backupへ戻すことは自動rollbackに含めない。配備後の実利用者・session・鑑定を失うため、対象と損失を説明して別承認が必要。
初回DB作成後に旧版へ戻す場合も新DBは残す。backup・失敗環境・空directoryの削除は別工程。

## 12. 夜間の確認範囲と翌朝の条件

アプリコードに安全境界の追加修正は不要。Argon2id、token hash保存、絶対期限、disable/password変更失効、
CSRF、session由来owner、SQL owner条件、保存snapshot、未保存tokenのuser/session条件を再監査。
正式requirementsから新規Windows検証venvの構築とpip checkを実施し、既存venvとは別に回帰を確認。
requirementsの一部とtransitive依存は未固定なので、将来の完全な同一version再現は保証しない。今回は方式を変更せず解決一覧をartifactへ保存。
Ubuntuへの導入・実build・実Excelは未実行で、配備runbookの停止条件付き工程で確認する。
Notion引継ぎ記録は参照のみ。過去の未着手記録より現在の明示指示と実Git状態を優先。Notion/共通ルール変更なし。

翌朝はsudoの対話認証とnginx -T/-tのread-only確認が必要。初期利用者email/passwordも本人の対話入力が必要。
夜間にこの未確認を成功扱いせず、nginx検査に失敗した場合は本番変更しない。


## 13. 完了検証結果

| 検証 | 既存venv | 新規requirements venv |
| --- | --- | --- |
| 認証 | 44/44 PASS | 44/44 PASS |
| 履歴 | 32/32 PASS | 32/32 PASS |
| Excel | 46/46 PASS | 46/46 PASS |
| PDF | 21/21 PASS | 21/21 PASS |
| Tier A / Tier B | 524/524・38/38、REVIEW0 | 524/524・38/38、REVIEW0 |
| deploy blocker / proxy spoof | 20/20 PASS | 20/20 PASS |
| 公開origin/本番既定値・失効・hash・IP30/account10・owner・出力 | 7/7 PASS | 7/7 PASS |
| production TLS PC1280/375px E2E | 34/34 PASS | 34/34 PASS |
| Windows PDF available PC1280/375px E2E | 34/34 PASS | 未実施（既存Windows環境で確認） |

TypeScript、Next.js production build、diff --checkはPASS。新規venvは正式requirementsから導入完了、pip check成功。
Windows実PDF4件はすべてA4縦2ページ、595.2×841.44pt。production disabled画面はPC/mobile目視確認済み。
production E2Eはテスト用証明書とlocalhost:443 proxyを使い、ブラウザの公開hostnameを127.0.0.1へ固定。
APIRequestContext/route.fetchによる外部接続も避け、補助リクエストをbrowser fetchかlocalhost固定transportへ限定した。
証明書は一時検証用でWindows証明書storeへ登録せず、TLS helper用cryptographyは既存bundleを使用。本番依存追加なし。
app本体・占術ロジック・鑑定書templateに変更なし。追加は検証コードと文書だけ。既存testの期待値は緩和していない。

追加実行：python -B tests/predeploy_cases.py。
E2E既定はWindows development。production検証はFORTUNE_TEST_PRODUCTION=1、FORTUNE_TEST_PDF_CONVERTER=disabled、
FORTUNE_TEST_CERT_PYTHONを既存cryptography利用可能Pythonへ指定し、tests/auth_ui.cjsを実行する。
FORTUNE_TEST_PYTHONへ新規venv Pythonを指定した場合も同じ検証を行える。PLAYWRIGHT_MODULEは既存bundleを指定。
成果物：C:\Users\bunch\Documents\Codex\fortune-app\outputs\predeploy-night-20261006。
production-tls / production-tls-fresh / windows-pdf、resolved-requirements.txt、新規dependency-venvを保存。
専用DBはユーザー保存DBと分離。全検証用serverは自分のPIDだけを停止した。

runbookの9 shell blockと2 Python blockはparserで構文確認だけを行い、本番操作は未実行。
Ubuntuの実install/build/migration/login/export、maintenance/backup/rollbackは次回承認後の停止条件付き工程であり、夜間検証済みとしない。

### 夜間終了時の判定（以下は夜間時点の記録）

**NOT_READY_FOR_PRODUCTION_DEPLOY_APPROVAL**

ローカル検証と実行指示書は完成。残る確認は本人sudo認証を伴うVPS nginx -T/-t。
未確認を成功扱いせず、翌朝このread-only検査が成功した後に配備承認へ進む。
initial userの本人email/password入力も配備時に必要（手順完成、未作成）。
VPS production状態の変更なし。旧版正常・Git clean・API/Web PID不変を監査した。

## 14. 本人sudo認証後のnginx最終read-only確認（2026-10-06）

本人が可視SSH TTYへsudo passwordを非表示入力。sudo -v後、同じTTYでsudo -n nginx -T、sudo -n nginx -tを実行。
両方終了コード0、syntax is ok / test is successful。秘密鍵内容は読まず、設定出力は秘密値を伏せて取得した。
端末起動の最初の引用符エラーはnginx実行前に終了し、修正した別端末で上記成功を確認。
VPS Gitはmain/clean/d8fe9a970ddae6fa0a6b58115164a0b1825c2075、API/Web/nginxは前回PIDのままactive/running。
HTTPS /200、HTTP→同domain HTTPS301。設定変更・reload・restart・DB/Git更新・本番loginなし。

実際の全includeはnginx.conf、mime.types、sites-enabled/default、sites-enabled/fortune-app、Certbot options-ssl-nginx.conf。
modules-enabled/conf.dから追加設定は読み込まれていない。defaultは80のdefault_server、server_name _、静的try_files。
fortune-appは443 ssl（IPv4/IPv6）と80（IPv4/IPv6）の2 server。app.hakase-uranai.jpの同じlistenでの重複なし。
80は対象HostをHTTPS301へ転送し、その他404。443はlocation /のみ、Next.js 127.0.0.1:3000へ全pathを転送。
/api/専用location・regex/exact location・rewrite・Cookie書換えなし。現行APIもNext.jsの/api/:path* rewrite経由。
Host=$host、X-Real-IP=$remote_addr、XFF=$proxy_add_x_forwarded_for、XFP=$scheme。Forwarded上書きは現行なし。
body/read/send timeoutの明示上書きなし（nginx既定1m/60s/60s）。
証明書/鍵path、Certbot SSL include、DH paramsは第5節と一致。appの実効TLSはCertbot includeのTLS1.2/1.3。
nginx.confの広いTLS既定を理由にappの実効設定を取り違えない。他サイト/Certbotとの競合なし。

第5節の差分は実環境から適用可能。location ^~ /api/でAPIだけPythonへ転送し、location /の画面routeは維持。
proxy_pass http://127.0.0.1:8765にはURI部分も末尾slashもないため、/api/接頭辞とqueryを保持する。
/api/auth/*、/api/history（末尾slashなしも含む）とその配下、/api/export/*、/api/export-capabilities、/api/fortuneはすべて対象。
Cookie/Set-Cookie/Originを保持し、公開originはhttps://app.hakase-uranai.jp。Host/$schemeの上書きとlocalhostだけのtrustが整合。
外部XFFをremote_addrへ置換し、Forwardedを除去する予定差分はそのまま維持。security boundary/architecture変更不要。
/healthは内部確認用のまま、公開API経路へ追加しない。
候補設定そのもののsudo nginx -tは配備時Step 17で必須。今回の成功は現在設定の検査で、候補をVPSへ置いてはいない。

### 最新の配備前判定

**READY_FOR_PRODUCTION_DEPLOY_APPROVAL**

夜間終了時の唯一のblockerだった権限付きnginx全設定・構文確認を完了。unresolved blockerなし。
本人による初期利用者email/password入力は引き続き配備時に必要。
次はユーザー承認後、本書の本番配備runbookを実行する。今回VPSのproduction状態を変更していない。
