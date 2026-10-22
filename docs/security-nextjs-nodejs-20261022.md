# Next.js / Node.js 緊急更新 — b2b

**本番未適用。独立Windows検証環境のみ更新済み。Windows全体のNodeも未交換。**
基準日2026-10-22（Asia/Tokyo）。翌日の配備承認を含まない。

元Repositoryはfortune-app-public、作業前/完了前ともclean。
既存作業branch phase10-special-two-column-20261022：
5854eed16b71671fc6c6f1d33ae30b238e8552d9。
mainはe8b53082775744a74f66502e8fb8f3cef72974c1。GitHub両branchも一致。
独立branch **security-b2b-next-node-20261022**、起点 **5854eed16b71671fc6c6f1d33ae30b238e8552d9**、
更新コードcommit **343edd3f40299ce8bb8c6434e14128a983d367ac**。この記録は後続commitに保存する。
作業先は開発元内.security-validation-20261022/b2bの独立clone。
既存branch切替、main merge、force pushなし。両security branchのGitHub新規push成功を確認済み。最終記録HEADは完了報告で照合。
Python/templates/adapters計96ファイルは改行正規化込みのGit blob照合で不変。
B2B二列レイアウトと鑑定文を保持。

## 検証結果

| 項目 | 結果 |
| --- | --- |
| Node24.22.1 / Corepack0.36.0 / pnpm11.7.0 | PASS |
| install / 最終audit | PASS / 脆弱性0 |
| 空のnode_modulesからfrozen-lockfile再インストール | PASS、lockfile SHA-256不変 |
| TypeScript / production build | 両系統PASS |
| sharp native PNG | PASS、libvips8.18.7 |
| Node標準テスト | 51件PASS |
| 正式回帰Tier A | 556件PASS |
| 観測Tier B | 38/38一致、REVIEW0 |
| Python unittest | 24 suite、491回実行、全suite終了0 |
| 公開版認証/履歴/再鑑定/Excel/PDF実画面 | 34項目PASS |
| B2B会員/先生/運営実画面 | 156項目PASS、1280/390/320幅 |
| B2B履歴/境界/再鑑定 | 既存スイートPASS、履歴28/境界1 |
| B2B実ダウンロードと異常時復帰 | 12項目PASS |
| 出力物 | 両系統8 PDFすべてA4縦2頁、B2B二列セル保持、B2B代表PDFの両ページ画像確認 |
| 正式回帰前後の本体hash | 差分0 |
| diff --check | PASS |

Python数は継承テストを含む実行回数であり、ユニーク仕様数ではない。
Tier Cの既知課題を解決済みとは扱わない。

| Python suite | 実行数 | 結果 |
| --- | --- | --- |
| test_harness.py | 16 | PASS |
| account_lifecycle_cases.py | 12 | PASS |
| auth_cases.py | 44 | PASS |
| billing_api_cases.py | 11 | PASS |
| billing_retention_cases.py | 42 | PASS |
| deploy_blocker_cases.py | 20 | PASS |
| execution_cases.py | 15 | PASS |
| final_retention_api_cases.py | 8 | PASS |
| final_retention_cases.py | 34 | PASS |
| history_cases.py | 32 | PASS |
| history_recovery_cases.py | 12 | PASS |
| k01_k03_cases.py | 42 | PASS |
| mail_delivery_cases.py | 9 | PASS |
| operations_cases.py | 22 | PASS |
| password_reset_cases.py | 22 | PASS |
| phase10_integration_cases.py | 6 | PASS |
| predeploy_cases.py | 7 | PASS |
| product_api_cases.py | 24 | PASS |
| product_foundation_cases.py | 19 | PASS |
| product_ui_cases.py | 9 | PASS |
| report_export_cases.py | 55 | PASS |
| report_pdf_cases.py | 21 | PASS |
| sekki_confirmation_cases.py | provider | PASS |
| usage_cases.py | 9 | PASS |

## 更新前監査の対応一覧

| 部品 | severity | GHSA | 修正基準 |
| --- | --- | --- | --- |
| postcss | moderate | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93) | >=8.5.10 |
| sharp | high | [GHSA-f88m-g3jw-g9cj](https://github.com/advisories/GHSA-f88m-g3jw-g9cj) | >=0.35.0 |
| next | high | [GHSA-6gpp-xcg3-4w24](https://github.com/advisories/GHSA-6gpp-xcg3-4w24) | >=16.2.11 |
| next | high | [GHSA-m99w-x7hq-7vfj](https://github.com/advisories/GHSA-m99w-x7hq-7vfj) | >=16.2.11 |
| next | high | [GHSA-89xv-2m56-2m9x](https://github.com/advisories/GHSA-89xv-2m56-2m9x) | >=16.2.11 |
| next | moderate | [GHSA-68g3-v927-f742](https://github.com/advisories/GHSA-68g3-v927-f742) | >=16.2.11 |
| next | moderate | [GHSA-4633-3j49-mh5q](https://github.com/advisories/GHSA-4633-3j49-mh5q) | >=16.2.11 |
| next | moderate | [GHSA-4c39-4ccg-62r3](https://github.com/advisories/GHSA-4c39-4ccg-62r3) | >=16.2.11 |
| next | high | [GHSA-p9j2-gv94-2wf4](https://github.com/advisories/GHSA-p9j2-gv94-2wf4) | >=16.2.11 |
| next | moderate | [GHSA-q8wf-6r8g-63ch](https://github.com/advisories/GHSA-q8wf-6r8g-63ch) | >=16.2.11 |
| next | moderate | [GHSA-955p-x3mx-jcvp](https://github.com/advisories/GHSA-955p-x3mx-jcvp) | >=16.2.11 |
| postcss | high | [GHSA-6g55-p6wh-862q](https://github.com/advisories/GHSA-6g55-p6wh-862q) | >=8.5.12 |
| postcss | moderate | [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) | >=8.5.23 |
| nanoid | high | [GHSA-28wg-ghj8-5hjv](https://github.com/advisories/GHSA-28wg-ghj8-5hjv) | >=3.3.16 |
| nanoid | high | [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8) | >=3.3.18 |
| postcss | high | [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849) | >=8.5.18 |
| next | critical | [GHSA-p293-qw3h-jr36](https://github.com/advisories/GHSA-p293-qw3h-jr36) | >=16.3.3 |
| baseline-browser-mapping | moderate | [GHSA-w5vr-8v7q-w6rv](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv) | >=2.11.0 |
| sharp | high | [GHSA-rgj7-g3m4-5g8c](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c) | >=0.35.4 |
| next | critical | [GHSA-2xp9-vwfh-vxw4](https://github.com/advisories/GHSA-2xp9-vwfh-vxw4) | >=16.3.3 |
| next | critical | [GHSA-vcvr-r3jv-pc5j](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j) | >=16.3.6 |
| source-map-js | high | [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) | >=1.2.2 |
| sharp | high | [GHSA-wq5f-xc86-pv6w](https://github.com/advisories/GHSA-wq5f-xc86-pv6w) | >=0.35.5 |
| next | moderate | [GHSA-4jqv-mc3x-m676](https://github.com/advisories/GHSA-4jqv-mc3x-m676) | >=16.3.8 |
| next | low | [GHSA-39w2-rjm5-chcv](https://github.com/advisories/GHSA-39w2-rjm5-chcv) | >=16.3.8 |
| next | moderate | [GHSA-f87g-xv8r-7p7x](https://github.com/advisories/GHSA-f87g-xv8r-7p7x) | >=16.3.8 |
| next | moderate | [GHSA-mcj8-r9mp-w47p](https://github.com/advisories/GHSA-mcj8-r9mp-w47p) | >=16.3.8 |
| next | high | [GHSA-cjq9-62q9-8jv4](https://github.com/advisories/GHSA-cjq9-62q9-8jv4) | >=16.3.8 |

## 更新前後と公式確認

| 部品 | 更新前 | 独立検証環境の更新後 |
| --- | --- | --- |
| Node.js Windows | 共通環境24.19.0 | 専用配置24.22.1 |
| Node.js VPS | 24.17.0 | 未適用 |
| Corepack検証用 | 共通環境を変更せず | 専用toolingの0.36.0 |
| pnpm | packageManager指定11.7.0 | 11.7.0 |
| Next.js | lockfile16.2.9 / manifest latest | 16.4.2固定 |
| React / React DOM | 19.2.7 / latest | 19.3.1 / 19.3.1固定 |
| sharp（間接依存） | 0.34.5 | 0.35.5 |
| PostCSS | 8.4.31 | 8.5.23 |
| baseline-browser-mapping | 2.10.40 | 2.11.0 override固定 |
| source-map-js | 1.2.1 | 1.2.2 override固定 |
| lucide-react | 1.22.0 / latest | 1.22.0固定 |
| TypeScript | 6.0.3 / latest | 6.0.3固定 |
| @types/node | 26.0.1 / latest | 24.12.3、Node24に合わせる |
| @types/react / @types/react-dom | 19.2.17 / 19.2.3 / latest | 同じ版に固定 |

更新前の値は起点commitのlockfileから取得。26系へは更新していない。
engines.nodeは >=24.22.1 <25、.node-versionと.nvmrcは24.22.1。
Windows共通pnpmは所在確認時11.25.0だったが、実検証はCorepack経由11.7.0に統一した。

- [Node公式security release](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)、
  [24.22.1 release](https://nodejs.org/en/blog/release/v24.22.1)、
  [配布index](https://nodejs.org/dist/index.json)で24系の最新修正版24.22.1を確認。
- 24系対応CVE：CVE-2026-105482、CVE-2026-105483、CVE-2026-106069、CVE-2026-111497、
  CVE-2026-105481、CVE-2026-106072、CVE-2026-106074、CVE-2026-106073。
  26系だけのCVEは実績に含めない。
- [Next16.4.2安定版](https://github.com/vercel/next.js/releases/tag/v16.4.2)を確認。
  [画像RCE/CVE-2026-96889](https://github.com/vercel/next.js/security/advisories/GHSA-2464-fhr4-w9xw)、
  [use cache RCE](https://github.com/vercel/next.js/security/advisories/GHSA-673q-mjm6-r5xr)、
  [Server Actions DoS](https://github.com/vercel/next.js/security/advisories/GHSA-p3m5-59mp-jv5r)
  の16.4.1以上、sharp0.35.5以上という修正基準を満たす。
- Windows zipは https://nodejs.org/dist/v24.22.1/node-v24.22.1-win-x64.zip から取得。
  公式SHASUMS256.txtと実ファイルSHA-256一致：
  d2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5
  node.exeのAuthenticodeはValid、署名者OpenJS Foundation。検証後に実行した。

## 監査と変更ファイル

更新前：critical3 / high13 / moderate11 / low1、合計28件。最終：全severity0件。
React/DOM/sharpを含む全依存を監査。初回16.4.2導入後に残った間接依存2件は
pnpm-workspace.yamlのoverrideで修正した。元のallowBuilds: sharp: trueを保持し、
他packageのbuildを包括許可していない。最終監査metadataは61依存、更新前59依存。
pnpm-lock.yamlはOS別native optional依存も更新。詳細GHSAと完全な監査応答は併記JSONに保存。

変更はfortune-next-appのpackage.json、pnpm-lock.yaml、pnpm-workspace.yaml、
Nextが生成するnext-env.d.ts、.node-version、.nvmrc、next.config.mjs、
tests/security_isolated_preload.cjs、およびこの記録と証跡JSON。
next.config.mjsは独立API試験用にFORTUNE_API_ORIGINを受け付ける1行だけ変更し、
未設定時の既存127.0.0.1:8765を維持する。本番用buildではこの変数を外す。
占術・認証・権限・DB・履歴・帳票のPython本体とテンプレートは変更なし。

## 試験方法と途中エラー

- Next production buildとnext startで試験。AはWeb13001/API18765、BはWeb13002/API18766。
  専用TEMP/TMPと合成DBを使用。既存3000/8765は変更・停止なし。
- preloadは既存UIスイートのlocalhostポートとPython実行パスだけを差し替え、
  同じbackend appをuvicornの別ポートで起動する。productionモードを拒否する。
  NODE_OPTIONSで子テストにも伝播し、期待値・assertion・timeoutは緩めない。
- 再現時は専用NodeをPATH先頭にし、FORTUNE_TEST_PYTHON、PLAYWRIGHT_MODULE、
  FORTUNE_SECURITY_WEB_PORT、FORTUNE_SECURITY_API_PORT、専用TEMP/TMP、
  NODE_OPTIONS=--require=<preload絶対パス、スラッシュ表記>を指定して既存スイートを実行。
  ブラウザは既存Edge/headless。UI backendはdevelopment、production Cookie/CSRF等はPythonで別検証。
- 初回PythonはWindows sandboxの一時DBアクセス拒否で停止/失敗。
  専用一時領域と適切な実行権限で再実行し、全suiteが終了0となった。
- pnpm11はpackage.json内pnpm.overridesを無視したため対応するworkspace形式へ修正。
  検証ランチャーの単一ファイルsplatとNODE_OPTIONSのWindowsパス表記も修正して再実行。
  アプリ本体の互換修正は不要だった。lintの既存next lintは今回実行しておらず、lint成功とは報告しない。
- 初回main UIのPDFは150秒download timeout。初回worker診断はなく原因未確定。
  同じ合成Excelの変換単体は成功。その後、条件を変えない全UI再試験で
  PC/スマホの未保存/保存PDF計4件すべてHTTP200・download成功。B2Bも4件成功。
  初回失敗を消したり「一度も失敗していない」とは扱わない。
  B2B出力テスト内503は元々の異常時復帰を検証する合成応答である。

## Windows / 本番の適用状態

Windows全体はNode24.19.0のまま。24.22.1は専用フォルダだけに配置。
正規Repositoryは元branchのままclean、既存3000/8765は継続稼働。
検証13001/13002/18765/18766は終了確認済み。

VPSはUbuntu24.04.4 LTS/x86_64。main HEAD：
569d1494202782099e6b8197f7825750f5d463fb、Git変更なし。
ローカルmainとの差は配備記録等docs5ファイルだけで、本体差分はない。
Next16.2.9、React/DOM19.2.7。sharpはトップレベル未配置で本番の実解決版は未確認。
Nodeは/usr/local/bin/node → /opt/nodejs/node-v24.17.0-linux-x64/bin/node、dpkg管理外。
Corepack0.35.0は同じ旧Node配下。pnpm単体はログインPATH上にない。

Web unitはExecStart=/usr/local/bin/corepack pnpm start、
WorkingDirectory=/opt/apps/fortune-app/fortune-next-app。
Corepack shebangは/usr/bin/env node、Web PATHは/usr/local/bin:/usr/bin:/bin。
PID826の実行ファイルも旧Node24.17.0。別Nodeを置くだけでは適用にならない。
API unitは/opt/venvs/fortune-app/bin/pythonによるbackend/server.py、PID26030。
両サービスは監査前後active/running、PID不変。
DBは/var/lib/fortune-app/history.sqlite3、0600、307200bytes。production/PDF disabled。
DB内容・利用者・password・production.envの内容は表示/変更していない。

バックアップディレクトリは権限拒否。sudo -nもpassword要求だったため、その監査を停止。
パスワード入力なし。バックアップ鮮度/整合性/復元可能性は未検証。
本番Node交換・systemd変更・再起動・Git更新・配備はすべて未実施。

## 配備・rollbackの具体的手順（未実行、承認後に担当Codexが実施）

対象はAのコードcommit bdc6de9906557ccc0c0083d53d1fb4a8fb713b9aだけ。
B2Bは配備しない。mainへのmergeと既存Repositoryのcheckout/pullは不要。
Linux staging/buildは今回未実施。以下のゲートを省略しない。
他セッションの変更、sudo/認証入力が必要、重大試験失敗、rollback不成立なら停止。

### 1. 新しいバックアップと旧経路の保持

- 本番HEAD/clean、全unit/drop-in、PID、実行経路を再監査。
- 旧Node24.17.0、旧Corepack、/opt/apps/fortune-appとその.nextをそのまま保持する。
- sudo承認後、/var/backups/fortune-app/security-20261022-<UTC時刻>/を0700で新規作成。
  現行Web/API unitと既存drop-in、production.envを権限保持で退避し、内容を表示しない。
- SQLiteのread-only接続からbackup APIで上記へDBコピー。
  本番DBへの書込み/migrationは行わず、コピー側のintegrity_check/foreign_key_checkとSHA-256を確認。
- 旧unitと旧Node/.nextを使う復旧経路を確認。未成立なら切替しない。

### 2. 公式Nodeを新しいバージョン付きフォルダへ

公式Linux x64アーカイブの確認済みSHA-256：
6c172a9ab6718f7b801fb5a7bd486af2ee5e32758086a04b84fcce2aa77095e6

作業専用ディレクトリで取得する例：

~~~bash
curl --fail --proto '=https' --tlsv1.2 -O https://nodejs.org/dist/v24.22.1/node-v24.22.1-linux-x64.tar.xz
curl --fail --proto '=https' --tlsv1.2 -O https://nodejs.org/dist/v24.22.1/SHASUMS256.txt
curl --fail --proto '=https' --tlsv1.2 -O https://nodejs.org/dist/v24.22.1/SHASUMS256.txt.sig
grep '  node-v24.22.1-linux-x64.tar.xz$' SHASUMS256.txt | sha256sum -c -
~~~

取得ハッシュは上記固定値とも照合する。署名検証ではNode公式
[release keys](https://github.com/nodejs/node#release-keys)のfingerprintを照合したkeyringを使い、
gpg --verify SHASUMS256.txt.sig SHASUMS256.txtを行う。未確認の鍵を自動信頼しない。
今回Linuxアーカイブの取得・実行・署名検証は未実施。
新規/opt/nodejs/node-v24.22.1-linux-x64へ展開し、共通/usr/local/binのsymlinkは交換しない。

~~~bash
NEWNODE=/opt/nodejs/node-v24.22.1-linux-x64
export PATH="$NEWNODE/bin:/usr/local/bin:/usr/bin:/bin"
"$NEWNODE/bin/node" --version
~~~

### 3. A専用releaseの構築・Linux検証

作成先が未存在であることと権限を確認する。存在すれば上書きせず調査する。

~~~bash
RELEASE=/opt/releases/fortune-app/security-20261022-A-bdc6de9
git clone --no-checkout https://github.com/bunchu678-sketch/fortune-app-mvp.git "$RELEASE"
git -C "$RELEASE" checkout --detach bdc6de9906557ccc0c0083d53d1fb4a8fb713b9a
test "$(git -C "$RELEASE" rev-parse HEAD)" = bdc6de9906557ccc0c0083d53d1fb4a8fb713b9a
TOOLING="$RELEASE/.tooling"
"$NEWNODE/bin/node" "$NEWNODE/lib/node_modules/npm/bin/npm-cli.js" install \
  --prefix "$TOOLING" --ignore-scripts --no-audit --no-fund corepack@0.36.0
CP="$TOOLING/node_modules/corepack/dist/corepack.js"
export COREPACK_HOME="$RELEASE/.corepack"
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0 NEXT_TELEMETRY_DISABLED=1
cd "$RELEASE/fortune-next-app"
"$NEWNODE/bin/node" "$CP" --version
"$NEWNODE/bin/node" "$CP" pnpm --version
"$NEWNODE/bin/node" "$CP" pnpm install --frozen-lockfile
"$NEWNODE/bin/node" "$CP" pnpm audit
"$NEWNODE/bin/node" "$CP" pnpm exec tsc --noEmit
~~~

sharp native画像生成とPythonの正式回帰/認証/履歴/出力テストをLinuxで実行する。
production.envと本番DBを使わず、専用合成DB・独立13011/18775でAPIとnext startを起動。
APIはuvicorn server:app --app-dir "$RELEASE/fortune-next-app/backend" --host 127.0.0.1 --port 18775。
試験用buildだけFORTUNE_API_ORIGIN=http://127.0.0.1:18775。
SMTP disabled、合成ログイン/logout、履歴/再鑑定/Excel、匿名拒否、PDF unavailableを確認。
起動PIDを記録し、検証後に自分のプロセスだけを終了する。
試験用.nextを削除せず別名退避し、API指定を外して本番build：

~~~bash
cd "$RELEASE/fortune-next-app"
# 試験サーバー終了と退避先未存在を照合した後だけ実行
mv .next .next.staging-only
unset FORTUNE_API_ORIGIN
"$NEWNODE/bin/node" "$CP" pnpm build
~~~

.next/routes-manifest.jsonのrewriteが127.0.0.1:8765、Next16.4.2/React19.3.1/sharp0.35.5、
lockfile SHA-256を確認。この段階まで既存3000/8765サービスには触れない。

### 4. 承認された保守時間にWebのみ切替

以下の新規drop-inが未存在であることを確認する。既存なら停止して調査する：
/etc/systemd/system/fortune-app-web.service.d/90-security-20261022.conf

~~~ini
[Service]
WorkingDirectory=/opt/releases/fortune-app/security-20261022-A-bdc6de9/fortune-next-app
Environment="PATH=/opt/nodejs/node-v24.22.1-linux-x64/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=
ExecStart=/opt/nodejs/node-v24.22.1-linux-x64/bin/node /opt/releases/fortune-app/security-20261022-A-bdc6de9/fortune-next-app/node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3000
~~~

NodeとNext CLIを実パス指定し、旧CorepackやPATHから旧Nodeへ戻らないようにする。
承認後のみsystemctl daemon-reload、systemctl restart fortune-app-web.serviceを実行。
Webの短時間停止が必要なため今回は未実施。API/nginxは再起動せず、schema変更なし。
/proc/<WebPID>/exeと子プロセス、unitの経路、Web release HEAD、HTTPS /と/loginの200、
API health、匿名履歴401、HTTP→HTTPS、ログと両サービス稼働を確認する。
実利用者のDB書込み試験は別途承認する。PDF disabledを維持。
API Git HEADは569d149のまま、Webは専用release HEADになることを配備記録へ明記する。

### 5. rollback

1. 新規作成した90-security-20261022.confだけをバックアップ先へ移動して退避する。
   退避元・先の絶対パスを照合する。既存unit/drop-inは上書きしない。
2. systemctl daemon-reload → systemctl restart fortune-app-web.service。
   元unitの/usr/local/bin/corepack pnpm start、元WorkingDirectoryへ戻る。
   共通symlink・旧Node24.17.0・旧.nextは保持している。
3. 実行Node24.17.0/Next16.2.9とAPI/HTTPS正常を確認。旧版の既知脆弱性は残るため一時復旧と扱う。
4. 今回DB schema/APIを変えないので、通常rollbackで本番DBは復元しない。
   切替中の利用者データを巻き戻さない。DB復元が必要なら別途停止・承認する。
5. 新Node/release/合成DBは調査用に保持し、削除やGit履歴書換えを行わない。

## 未解決事項・翌朝の確認

本番は未承認/未適用。sudoバックアップ検証、Linux stagingとrollbackゲートが残る。
Windows初回PDF timeout原因は未確定、再試験は成功。Windows共通Nodeへの適用と
正規作業branchへの統合も別工程であり、無断で行わない。Linux PDFは従来どおりdisabled。
ユーザーはこの記録と完了報告を確認し、Aの本番配備を進めるか判断する。
承認前にユーザーがコマンド入力・サービス操作をする必要はない。

グローバルAGENTS.md v1.3と開発元AGENTS.mdを確認。公開RepositoryにAGENTS.mdなし。
今回の明示指示で独立cloneと安全なcommit/pushが承認されており、その範囲で実行。
その他の未解決な指示競合なし。Notionの判断・表現原則DBの関連する有効/本人確認済み例と
Phase5/VPS監査記録を参照したが、現在事実は今回のSSH監査を優先した。
Notionの作成・更新なし。
