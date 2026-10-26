# fortune-app 再開用引継ぎ（2026-10-26夜間）

## 正本と最新Git

- 正規W repository：`C:\Users\bunch\Documents\Codex\fortune-app-public`。開発元：`C:\Users\bunch\Documents\Codex\fortune-app`。Git remoteはbunchu678-sketch/fortune-app-mvp。
- GitHub main：241dd57e39e451ad1c626414d93290b875d027fc（公開security更新、10/26に正式統合/push済み）。ローカルmainは旧e8b5308のまま意図的に保持。勝手にreset/switchしない。
- 本人受入済みB2B基準：phase10-history-navigation-20261026 / 578b429c03694a6d85d47fbb677fb9fd0c1cbab5。正規repositoryの既存作業treeはこのbranchで維持。
- 新規統合/先行開発branch：`phase11-b2b-integration-preflight-20261026`。専用worktree：開発元`outputs/phase11-overnight-20261026/integration-git`。最終HEADはoriginの同branchと照合し、開発元版総合報告の「最終実測」を参照。
- 統合commit：30f7a44e0bde8f651a0819b0ab476a8c899d370a（第一親main241dd57/第二親B2B578b429）。先行lab/追加test：2e809aa216845314026ad7866e6d08d632f764f8。後続は判定/運用/総合資料のcommit。

## 完了したこと

統合候補を実mergeし総合回帰。競合はsecurity証跡2資料のみで公開原文＋B2B別名保存。受入済みB2Bの既存非docs185ファイルは内容同一、Node24.22.1/Next16.4.2/React19.3.1維持。正式占術文・計算・帳票・画面・契約/保持・権限は今回新規変更なし。

TS/build成功、Node69、Python既存495＋追加19=514、Tier A556/B38、実ブラウザー536、合成移行8成功。追加は合成DBしか選べないWAL/メモリ復元lab17件と初回配送失敗/期限切れ2件。fileDB purge/restore、本番backup機能は有効化していない。

**本人受入済み**：帳票3件（4列表、説明後keyword、五行対称）、画面6件（B2C除去、ヘッダー、運営専用、日本語エラー、履歴→所属先入力、先生フッター削除）。同じ受入を再要求しない。細かな名称整理は延期。

## 次に読む資料

1. `docs/phase11-overnight-20261026.md`：A〜I総合記録・検証/保存先/Notion参照。
2. `docs/phase10-completion-readiness-20261026.md`：13領域、K01〜K06、A/B/C/Dと本人判断。
3. `docs/phase11-predeployment-20261026.md`：配備/migration/backup/SMTP/Linux PDF/URL/運用/rollback準備。
4. 開発元`docs/security-vps-retry-20261023.md`と`docs/security-main-integration-20261026.md`：本番記録とGitHub main統合。古いvps-deploymentの569d149だけで現在の稼働コードを決めない。

## 重要な未確定事項と停止条件

Phase10正式完了、mainへのB2B統合、Phase11本番運用開始、本番配備/migration・実メール・実アカウント・請求・削除は未承認。今夜の実行許可は専用branchと合成隔離開発だけ。

外部backup先・鍵/復旧担当・独立最新checkpoint、B2C/C/D保持根拠、SMTP/URL/運営担当、K02/04/06商品範囲、2027正式原稿は本人判断。Linux PDFはdisabled、ローカルLinux環境がなく未試験。必要なら別の隔離環境を先に確定する。secretをチャット/Git/Notionへ保存しない。

VPSは今夜未接続。10/23記録上の本番Webはbdc6de9のsecurity release/専用Node24.22.1で、cwdは`/opt/apps/fortune-security-preflight-20261023/release/fortune-next-app`。現在の実効cwd/PID/schema/設定は未確認。mainの更新だけで本番へ配備されたと扱わない。

## 起動中環境と再開方法

受入済み578b429版の本人確認はhttp://127.0.0.1:13335/（合成/役割ボタン）を維持。旧13325・3000/8765と関連プロセスも停止/上書きしていない。今回の統合候補の試験は13423/18886、所有するtestサーバーだけ終了。既存本人確認環境へ統合版を反映したとは扱わない。

再開時は共通/親/該当AGENTS、Git fetch/HEAD/status/worktrees、対象branch・既存起動環境を再確認。既存出力/未commit差分を破棄せず、本人が次の工程を明示承認してから進める。今回の安全な既存許可内工程に未実行の実装・回帰は残していない。
