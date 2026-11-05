# 先生版：停止機能の保全と将来の復元

2026-11-05指示分（2026-11-06 JST記録）。今回の先生版は鑑定専用。これは将来の復元のための記録であり、現在の停止機能を有効にする指示ではない。本番配備・実データ削除は未実施。

## 復元の基準

- 停止前の実装：`f5000950fec2c74fbedbe4a2a73b4134e560b34a`（`mari-presentation-20261105`）。GitHubとの一致を作業開始時に確認済み。
- 新仕様：`mari-reading-only-20261105`。再構成、UI、セキュリティを別コミットとして管理する。
- 固定された占術計算・正式辞書・帳票テンプレート・既存の履歴スキーマは変更していない。
- 既存User/Membershipの役割・ID・認証秘密情報を書き換えていない。先生・生徒の区分を画面からなくすことと、既存の契約判定を変更することを区別する。
- 復元時も、今回更新したNext.js等の修正版を保持する。停止前コミットへ一括で戻して依存を古くしない。

## 現在の停止境界

APIの既存設定 `FORTUNE_DEPLOYMENT_SURFACE=teacher` で、APIの入口を次だけに限定する。

- `/api/auth/*`：既存ログイン・ログアウト・本人確認・パスワード設定。
- `GET /api/reading/bootstrap`：初回描画に必要な本人・配色・所属先設定だけ。
- `POST /api/reading/fortune`：認証・現在の利用権を確認した一時的な計算。
- `POST /api/reading/theme`：本人のテーマ選択保存。

履歴・出力・account summary・b2b・operations・従来の汎用鑑定API・出力可否APIは、先生プロセスで404/no-storeになる。隠しメニューやフロントエンドの状態変更ではこの境界を回避できない。

Webの `FORTUNE_UI_SURFACE=teacher` で、`/history`、`/member`、`/mypage`、`/teacher`、`/b2b`、`/operations`、`/product` とそれらの下位URLを `/` へ戻す。未認証の `/` は `/login` へ進む。先生画面で未使用の `/_next/image` も閉じる。博士版と運営専用プロセスには、先生用の停止条件を適用しない。

運営者の発行・停止・招待等は既存のadminプロセスに残る。一般利用者へ運営権限を付けない。教室の選択はリクエストのIDではなく、サーバー設定のslug（標準 `mari-mutsuro`）と本人の既存Membershipから解決する。

## 機能別の保全場所

| 復元候補 | 保全したコード・データ | 復元時の接続箇所 |
|---|---|---|
| 履歴一覧・検索・詳細・再鑑定・復旧 | `history_repository.py`、`history_service.py`、`reading_snapshot.py`、`history_versions.py`、`fortune-next-app/backend/history_api.py`、`fortune-next-app/app/history/`、history-client/controls/new-reading | API allowlist、旧URLのWeb境界、入力/結果のボタンと候補検索 |
| 履歴の教室・本人分離 | `b2b_content_access.py`、既存のreading scope、契約/アカウントの認可 | 現在の利用権と本人scopeを維持して既存APIへ接続 |
| Excel | `templates/`、`report_data.py`、`report_xlsx.py`、`report_export_service.py`、`fortune-next-app/backend/export_api.py`、report-export部品 | 出力APIの明示許可、結果画面の操作部品、認証済み・教室scope付き一時出力token |
| PDF | 上記Excelソース、`report_pdf.py`、`pdf_converter.py`、`adapters/` | 承認されたconverter設定・可否API・出力操作 |
| マイページ・先生画面・利用者区分 | `member-navigation.ts`、member-start、member/mypage/teacher各page、`product_api.py`、`operations_repository.py` | 復元する画面だけのWeb境界解除、対応APIの認可付き開放、必要なナビゲーション |
| 運営管理 | operations関連page/API、招待・認証・契約関連コード | adminプロセスを維持。先生側で管理API全体を開放しない |

ソースファイル・テンプレートを削除していない。現在の結果画面からは履歴保存・出力操作・未保存状態の表示・永続メモ操作を外している。Reactのメモリ内に鑑定中の入力と結果を持ち、ブラウザーの永続ストレージへ新しく保存しない。

## データの扱い

- `persons`、`reading_groups`、`readings`、`reading_organization_scopes` 等の既存表を破壊していない。既存snapshotやメモはそのまま保全する。
- 新しい先生版の計算は履歴を作らず、成功回数用の入力fingerprint・export tokenも新しく保存しない。認証セッション・ログイン動作・テーマ保存は必要な既存動作として残す。
- 機能停止は、既存の氏名・生年月日・相談・命式・メモやバックアップ内のコピーを消したという意味ではない。
- 既存データの保存期限、物理削除、バックアップ世代からの消去は別の判断が必要。今回は本番の削除ジョブ・保存期間・バックアップへ接続しておらず、設定を変更していない。
- 復元時に旧データを別利用者・別教室へ自動割当てしない。旧本人IDと教室scopeを保ったまま、現在の利用権と過去データの閲覧方針を改めて確認する。
- 本番へ適用する際は、先生プロセスの境界設定、専用DBの接続、Web/API origin、既存の保持・削除ジョブとの整合を別途確認する。現在のローカル結果を本番の停止完了とは扱わない。

## 将来の復元工程

1. 本人の新しい指示で、戻す機能・利用者・過去データの閲覧範囲を確定する。
2. 現在のセキュリティ修正版から新しい専用branch/worktreeを作る。mainや既存worktreeをresetしない。
3. 停止前のGit blobと上表を比較し、必要な接続差分だけを戻す。スキーマやデータを再初期化しない。
4. APIを機能単位で明示許可し、既存の本人・教室・現在の契約・セッション・CSRF検査を維持する。古い `/api/fortune` の匿名経路で先生の鑑定を再開しない。
5. 出力を戻す場合は、教室scope付きtokenと出力直前の認可を再接続する。クライアントにownerや権限を選ばせない。
6. Webの旧URLと操作部品を、許可した機能だけ再接続する。初回テーマのSSR、現在の配色・レイアウト、修正済み依存は維持する。
7. 下記の復元試験と新しい本人受入を行う。本番変更には別の明示指示が必要。

再構成コミットを丸ごと戻すと、初回テーマのSSRまで戻る。依存・現在のUI・認証の改善を残すため、無条件の全体revertは復元手順にしない。

## 復元時に保全した試験

- `history_cases.py`、`history_recovery_cases.py`：本人scope・保存snapshot・復旧。
- `product_api_cases.py`、`product_foundation_cases.py`：教室・本人分離、既存の役割と利用権。
- `report_export_cases.py`、`report_pdf_cases.py`：承認済みテンプレート、既存整形、出力元・token・権限。
- `auth_cases.py`、`password_reset_cases.py`、`admin_domain_cases.py`、invitation関連：認証・CSRF・セッション・運営境界。
- `security_scope_cases.py`：停止前の履歴/帳票に関するteacher matrixを保全。現在は復元時用として明示skipし、復元後だけ `FORTUNE_TEST_RESTORED_FEATURES=1` を使って検証する。これはテスト選択であり、現在のAPIを有効にする設定ではない。
- 現在のteacher権限試験は `reading_only_cases.py` で置換した。新規計算の全表不変、廃止API全methodの拒否、他教室・運営者・未払・停止・終了・試用期限・セッション期限・計算途中の権限失効を確認する。
- `security_regression_suite.py` の現行teacher対象も新仕様へ切り替えた。復元する場合だけ、承認したAPIの期待値を必要範囲で更新する。
- 固定計算のTier A/B/C、Nodeの割合計算、PC/スマホの実ブラウザー検証は復元後も実施する。

今回、これらの復元操作や本番データの消去は実行していない。
