# 公開版セキュリティ更新のmain統合準備（実行承認待ち）

2026-10-23夜間指示、検証実施は2026-10-24 JST。**mainのmerge/push、本番配備・再起動は一切実施していない。** B2B修正とは別ブランチ・別worktreeで資料だけを追加する。

## 固定した対象と結論

- 正規repository: `C:\Users\bunch\Documents\Codex\fortune-app-public`、origin: `bunchu678-sketch/fortune-app-mvp`。
- main / origin/main: `e8b53082775744a74f66502e8fb8f3cef72974c1`。
- 検証候補 origin/security-main-next-node-20261022: `241dd57e39e451ad1c626414d93290b875d027fc`。
- 記録上の本番Webコード: `bdc6de9906557ccc0c0083d53d1fb4a8fb713b9a`。今夜VPSへ接続して再測定したものではない。
- merge-baseがmainと一致。現時点では**fast-forward可能**。mainから候補まで3コミット（bdc6de9 → a05683a → 241dd57）。
- bdc6de9と241dd57の差は`docs/security-20261022-evidence.json`と`docs/security-nextjs-nodejs-20261022.md`だけ。アプリのコード・依存内容は一致する。
- この資料のブランチは候補241dd57から分岐。B2Bブランチを親にしていない。

## mainとの差分（10ファイル）

```text
docs/security-20261022-evidence.json
docs/security-nextjs-nodejs-20261022.md
fortune-next-app/.node-version
fortune-next-app/.nvmrc
fortune-next-app/next-env.d.ts
fortune-next-app/next.config.mjs
fortune-next-app/package.json
fortune-next-app/pnpm-lock.yaml
fortune-next-app/pnpm-workspace.yaml
tests/security_isolated_preload.cjs
```

`git ls-tree`にB2B/teacher/operationsページ・API routeなし。buildのroute一覧にも混入なし。公開版のmainへB2B修正を含める計画ではない。

## 隔離検証

既存pnpmキャッシュから`pnpm install --offline --frozen-lockfile`。共通環境やrepositoryのlockを更新せず、物理的に分離した検証コピーに依存を展開した。初回のnode_modules junction方式はTurbopackが外部workspaceへのリンクを拒否したため不採用。これは検証配置条件Cで、実装回帰ではない。

|項目|結果|
|---|---|
|Node / pnpm|24.22.1 / 11.7.0（専用runtime）|
|実installされたNext / React / ReactDOM / TypeScript|16.4.2 / 19.3.1 / 19.3.1 / 6.0.3|
|lock固定install|成功、実行前後のlock不変|
|production build（通常Turbopack）|成功|
|TypeScript `tsc --noEmit`|成功|
|Node既存テスト|5/5 PASS|
|Tier A / Tier B|524/524 PASS / 38/38一致|
|Python unittest|8スイート中checkを除く7スイート、186/186 PASS（harness16、認証44、履歴32、Excel46、PDF21、production設定7、deploy blocker20）|
|公開版auth UI/E2E|PC/mobile計34/34 PASS、未保存・保存Excel/PDF実ダウンロード、owner分離、ログアウト後の遅延応答破棄|
|参照用Tier C|6件を継続、正式判断を独断変更しない|

依存ファイルはGit objectのLFとWindows作業コピーのCRLFを正規化すると一致する。raw byte hashの相違を依存変更と混同しない。Git object SHA-256:

- package.json: `97af4341c81db6de0263b62175e7c2a3b60e94800b845b89c243b21ef05823b3`
- pnpm-lock.yaml: `aaf107a86de2a01575e0ab5460cdf05c16b054c0df65e9c7060990ebce8ca872`
- pnpm-workspace.yaml: `94bc5f21599d1bb6f94b70c433cbbf92891ffdf9ccb98b6388af0e3df4bbb1d1`

ローカル証跡: 開発元`outputs/phase10-overnight-20261023/`の`security-history.json`、`main-native-*.log`、`main-*.log`、`main-python-results.json`。検証ソースは`isolated/main-native`、画面と実帳票は`ui-temp-main-native-auth_ui/auth-screenshots`。全て合成データ。

## 承認後のGitHub main統合手順（今夜は実行していない）

統合はGitHubの履歴合わせだけで、本番切替とは別の承認・作業とする。担当者は既存B2B作業treeを切り替えず、新しい専用worktreeを使う。下記PowerShellは**本人がmain統合を明示承認した後**に限る。停止条件は例外にせず、強制更新やresetで回避しない。

```powershell
$repo='C:\Users\bunch\Documents\Codex\fortune-app-public'
$candidate='241dd57e39e451ad1c626414d93290b875d027fc'
$oldMain='e8b53082775744a74f66502e8fb8f3cef72974c1'
Set-Location -LiteralPath $repo
git fetch origin
if ($LASTEXITCODE -ne 0) { throw 'fetch失敗' }
if ((git rev-parse origin/main).Trim() -ne $oldMain) { throw 'mainが変化。再監査が必要' }
if ((git rev-parse origin/security-main-next-node-20261022).Trim() -ne $candidate) { throw '候補が変化。再検証が必要' }
if ((git merge-base origin/main $candidate).Trim() -ne $oldMain) { throw 'fast-forward条件不一致' }
git diff --name-only origin/main $candidate
# ここで上記10ファイルと一致すること、B2B混入なしを確認。
# worktree先は未存在であること。既存の同名パスを消して使わない。
$integration='C:\Users\bunch\Documents\Codex\fortune-app\outputs\main-integration-approved-20261024'
if (Test-Path -LiteralPath $integration) { throw '作業先が存在。未使用の作業先を決める' }
git worktree add -b approved-main-integration-20261024 $integration origin/main
if ($LASTEXITCODE -ne 0) { throw 'worktree作成失敗' }
git -C $integration merge --ff-only $candidate
if ($LASTEXITCODE -ne 0) { throw 'fast-forward失敗' }
if ((git -C $integration rev-parse HEAD).Trim() -ne $candidate) { throw 'HEAD不一致' }
if (git -C $integration status --porcelain) { throw '未commit変更あり' }
git -C $integration push --dry-run origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'push予行失敗' }
git -C $integration push origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'push失敗。forceせず報告' }
git fetch origin main
if ((git rev-parse origin/main).Trim() -ne $candidate) { throw 'remote確認不一致' }
```

通常pushの直前にremoteが進んだ場合もnon-fast-forwardで停止する。mainの保護ルールがPRを要求する場合はその手順に従い、保護解除・force pushはしない。ローカルmainはこの方法では更新せず、次回作業時に明示的に整合を確認する。

## 本番運用・rollbackへの注意

最新のローカル配備記録は開発元`docs/security-vps-retry-20261023.md`。古い`docs/vps-deployment.md`の「本番HEAD569d149」だけで稼働Webの世代を決めない。

同記録上、Web cwdは`/opt/apps/fortune-security-preflight-20261023/release/fortune-next-app`、release HEADはbdc6de9、専用Node24.22.1をsystemd `90-security-20261023.conf`から絶対pathで使用する。旧repository `/opt/apps/fortune-app`は569d149のまま退避資産として保持され、共通Nodeリンクも旧版のまま。API/nginx・DB schemaは変更していない。今夜これらを操作していない。

GitHub mainの更新だけで稼働cwdやsystemd設定が変わるとは限らない。将来のdeploy/runbookは**実効WorkingDirectory・ExecStart・runtimeの版**を読み取り確認して設計する。Git統合が想定外だった場合、直ちに旧Webへ戻す理由にはならない。Git履歴の破壊、旧依存lockの復活、DB巻戻しをしない。

旧Node24.17.0/Next16.2.9へのWeb rollbackは既知のセキュリティ問題を再導入する。緊急復旧は本人の別承認と最新の運用記録に従い、原因と再更新計画を記録する。本番rollbackは今夜未実施。Linux PDF disabledを維持し、B2B配備・追加migration・実SMTPは別工程。
