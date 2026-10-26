# 特殊な命式：2件1行の4列表へ修正（2026-10-23 JST）

## 開始状態と参照

- 正規Repository: `C:/Users/bunch/Documents/Codex/fortune-app-public`。
- 実際の開始branch: `phase10-special-two-column-20261022`。
- 開始HEAD: `5854eed16b71671fc6c6f1d33ae30b238e8552d9`。working treeはclean、同名originと一致。
- 通常権限のGitはwork treeへのアクセスエラーになったため、許可された権限で読み直して確定。
- `git fetch origin security-b2b-next-node-20261022` で基準候補を取得。HEADは指定の `03ac311f550de7e447861f918798a0a1cad38144` と一致。開始HEADを継承し、差分はNext/Nodeセキュリティ対応の10ファイルで、鑑定書Pythonは同じ。
- この基準から専用branch `phase10-special-table-20261023` を作成。依存関係の導入やWeb/API再起動はしていない。
- mainは `e8b53082775744a74f66502e8fb8f3cef72974c1` のまま。merge・本番配備なし。
- 上位共通ルール `C:/Users/bunch/.codex/AGENTS.md`、開発元AGENTS.md、`handoff_notes.md`、公開用docsの前回2列実装記録を確認。正規Repositoryに固有AGENTS.mdはない。
- ローカル引継ぎ書冒頭は7月時点のため、現在地はNotionの10/22〜23のPhase10/B2Bセキュリティ引継ぎ2件と実Gitを確認して判断。Notionの鑑定書Excel/PDF判断ログも参照。関連原則DB・Lessonsを検索し、今回に追加適用する確認済み原則は見つからなかった。Notionの作成・更新なし。
- 前回の「名前／説明を上下2行にする左右3段」実装は、今回の明示指示で不採用。本記録の4列表が今回の採用要件。未解決の指示矛盾なし。

## 原因と実装箇所

旧実装は `report_xlsx.py` の `presentation_cells` / `acceptance_layout` により、各項目を上下2行のカードとして再配置していた。さらに `report_data.py` には6件超の出力エラーがあった。

### report_xlsx.py

- `layout_special_table` が `[命式名][説明][命式名][説明]` の同一行に配置する。左はC:D / E:H、右はI:J / K:N。既存列幅を使い、名前と説明の幅はおよそ1:2。
- 入力順を保ち、行数は `ceil(件数 / 2)`。0件は見出しと表を非表示。奇数件の最後の右側2セルは空欄で白地。
- 原本の既存6行は再利用し、余りを非表示にする。6行は件数制限ではない。12件を超えて足りなくなれば完成出力へ行を挿入するため、行数・件数に3段/6件の上限はない。
- 罫線、11pt、名前の薄灰色と太字、説明の白地、折り返しを適用。行高は左右両方の名前/説明の改行数と全角/半角幅を見て確保し、最低22pt。文字縮小は無効。
- 行を増やす場合、後続セル、結合範囲、図形の行アンカーと物理座標、グラフの参照、補助データ、定義名、印刷範囲、改ページを連動して移動。
- 通常のA4縦82%と既存の小幅な80%調整を継承。収まらない場合は文章を削らず、見出しと本文のブロック単位で改ページする。PDF配置処理は複製せず、完成Excelを既存adapterで変換。

### report_data.py

- 判定済みデータの「判定」「結果」を、既存 `text()` の検査・制御文字除去を通して表示専用 `special_entries` に全件保持。
- テンプレート由来の6件超エラーだけを解除。従来の正式 `cells` / `texts` / `chart_cells` と占術計算・判定・文章を変更しない。従来の6つのC/E投影は互換用に維持。

### テスト

- `tests/report_export_cases.py`: 件数0〜8、13、16、25を検証。配置、順序、名前/説明対応、奇数空欄、罫線/文字/折り返し、全後続セルの値、印刷範囲、図形の行座標/物理座標、グラフ参照を確認。
- `tests/k01_k03_cases.py`: 新表示フィールドを別途正式入力と照合し、残る従来フィールドは既存の凍結ハッシュを変更せず比較する。

## テスト結果

| テスト | 最終結果 |
| --- | --- |
| `.venv/Scripts/python.exe -B tests/report_export_cases.py` | 55件成功 |
| `.venv/Scripts/python.exe -B tests/report_pdf_cases.py` | 21件成功 |
| `.venv/Scripts/python.exe -B tests/k01_k03_cases.py` | 42件成功 |
| `git diff --check` | 成功 |

途中で検出し修正した事項:

1. 7/8件で既存の80%印刷調整が働くため、82%固定の試験期待値を修正。
2. 表示フィールドの追加により、従来の `asdict()` 全体ハッシュ試験が1件不一致。新フィールドを別検査し、従来ハッシュの検査は維持。
3. 16件PDFの目視で拡張グラフラベルのずれを検出。通常の `c:f` だけでなく `c15:f` も移動するよう修正し、全名前空間の参照検査を追加。16件Excel/PDFを再生成し、ラベル全文を再照合。
4. 合成出力スクリプトの最初の起動はプロジェクトvenvにpypdfがなく停止。導入済みCodex同梱Pythonへ切り替え成功。ライブラリ追加・環境変更なし。

PDFテストログの変換失敗/timeout等は異常系を注入する既存テストの期待ログ。最終失敗なし。全体回帰やフロントエンドbuildは今回の変更対象外のため実施していない。

## 確認用出力

保存先: `C:/Users/bunch/Documents/Codex/fortune-app/outputs/phase10-special-table-20261023`。
合成データだけを使用し、既存DBはアクセスしない。各basenameに `.xlsx` / `.pdf` がある。

| basename | 件数 | 表の行数 | PDFページ | 印刷倍率 |
| --- | ---: | ---: | ---: | ---: |
| special-0 | 0 | 0 | 2 | 82% |
| special-1 | 1 | 1 | 2 | 82% |
| special-2 | 2 | 1 | 2 | 82% |
| special-3 | 3 | 2 | 2 | 82% |
| special-6 | 6 | 3 | 2 | 82% |
| special-7 | 7 | 4 | 2 | 80% |
| special-8 | 8 | 4 | 2 | 80% |
| special-16 | 16 | 8 | 3 | 82% |
| 2026-two | 2 | 1 | 2 | 82% |
| 2027-two | 2 | 1 | 2 | 82% |
| example-two | 2 | 1 | 2 | 82% |
| long-two | 2 | 1 | 2 | 80% |
| long-six | 6 | 3 | 3 | 82% |

- `example-two` は今回指定された異常干支/冲の文言をそのまま使う合成配置例。判定結果としての主張ではない。
- 13ケースすべて実Excelで読み取り専用として開き、既存の専用adapterからPDF化に成功。pypdfで全特殊命式・正式本文・全グラフラベルの存在とA4縦を確認。特殊命式以外の正式投影は固定入力の値と一致。
- Popplerで全PDFをPNG化。0/1/6/8件、指定2件例、長文2件/6件、16件とその後続ページを目視確認。最終16件のグラフラベル修正を確認。表の同一行4列、奇数空欄、折り返し、図形/後続本文の位置は良好。
- Excel編集画面を別途UIで目視する確認は行っていない。実Excelによる読込・PDF変換とその印刷結果を確認した。
- 長文6件と16件は3ページ。全件を2ページへ固定する仕様ではなく、文字を省略せず件数と内容に応じてページが増える。任意の極端な文章長・別フォント/別PDFエンジンでの表示までは保証していない。本人による受入確認は未完了。
- `verification.json` にケース別結果、`pages/` にPNG、`excel-tests.log` / `pdf-tests.log` / `k01-k03-tests.log` に最終テストログ。

ローカル補助スクリプト（Git対象外）:
`research/run_special_table_acceptance.py`、`research/run_special_table_verify.py`。
修正前4ファイルの控え: 開発元 `_backups/public/special-table-20261023`。

## 保護・Git

開始前後で同じSHA256:

- `templates/kanteisho.xlsx`: `289b5d1093061487ba2e0e18bf6cd1c5c6056609daa31cbe0629e21489fa3b22`
- `special_chart_logic.py`: `26a94b84164b7ecab1c488af9fff225157bd07788f1a385672b31ff0247e7b76`
- `data/history.sqlite3`: `9faacb971b429179eba95083a32b81f2c8f7321bb1e538b47665e9b3055d3da1`

占術計算、判定、正式文章、原本、既存DB、PDF converter、他セクションの文言は未変更。試験DBはテスト専用一時領域のみ。mainへのmerge、サーバー再起動、配備、Notion書込みなし。

変更4ファイルと本記録の合計5ファイルのみを専用branchへcommit/pushする。成果物・補助スクリプト・バックアップは公開Repositoryの外に保持。commit hashとpush後のstatusは完了報告で示す。
