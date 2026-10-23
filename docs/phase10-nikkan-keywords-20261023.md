# 「干支から読み取れるもの」キーワードの本文内移動

## 開始状態（2026-10-23 JST）

- 正規Repository: `C:/Users/bunch/Documents/Codex/fortune-app-public`。
- 開始branch: `phase10-special-table-20261023`。
- HEAD: `95d6430f5a573f19c69ac3e850df78a6615cc87c`。working treeはclean、同名originと一致。
- ユーザーの今回の指示で、特殊命式の4列表を受入済みと確認。このcommitを継承し `phase10-nikkan-keywords-20261023` を作成。
- 共通 `C:/Users/bunch/.codex/AGENTS.md` を上位として開発元AGENTS.mdを確認。公開用に固有AGENTS.mdなし。引継ぎ書と前回 `docs/phase10-special-table-20261023.md` を参照。未解決の指示矛盾なし。
- 前工程で読んだNotionの鑑定書判断ログを継承し、今回も対象セクションの関連検索を実施。Notionの作成・更新なし。

## 調査結果と変更

元の出力データは `report_data.py` の `build_reading_report` が作る。見出しとキーワードは `cells['B25']` に連結され、説明は `texts['Phase5_Nikkan']` に保持されていた。本文はセル本文ではなく、`xl/drawings/drawing2.xml` の同名テキスト枠。原本の行26〜28にまたがり、45pt、11pt文字、13pt行間。

今回の変更対象は以下の3ファイルだけ。

1. `report_xlsx.py`
   - `presentation_cells`: 出力見出しを `● 干支から読み取れるもの` だけにする。
   - `presentation_texts`: 正式投影のB25からキーワードを取り出し、説明の後へ明示改行で追加。`write_shapes` はこの表示用コピーを使用。
   - `acceptance_layout`: 折り返し幅・改行数から必要高さを見積もり、既存45ptに収まらない場合だけ行28を広げる。拡張時はExcelの末尾クリップを避けるため1行分の余裕を加える。既存の行高差分処理が枠の高さと後続図形の座標を同期する。
2. `tests/report_export_cases.py`
   - 見出し単独、本文の説明→キーワード順、10干の正式辞書全文、キーワード空欄、明示改行、11pt維持、正式投影非変更、他の本文枠のサイズ維持を確認。
   - 特殊命式拡張テストの後続見出し期待値だけを新表示に合わせる。既存の0〜8/13/16/25件の表配置・移動検査を維持。
3. `docs/phase10-nikkan-keywords-20261023.md`（本記録）。

`report_data.py`、コメント辞書、判定・計算、承認済み原本、特殊命式の配置関数、PDF converterは未変更。正式説明とキーワードの文字列はそのまま使用。既存のデータ構造は変更していない。

## テストと実出力確認

| コマンド（公開用Repository、既存venv） | 最終結果 |
| --- | --- |
| `python -B tests/report_export_cases.py` | 56件成功 |
| `python -B tests/report_pdf_cases.py` | 21件成功 |
| `python -B tests/k01_k03_cases.py` | 42件成功 |
| `git diff --check` | 成功 |

実Excelの既存専用adapterを使用し、合成データ2ケースのXLSXを読み取り専用で開いてPDF化。Codex同梱Python/pypdfで本文全文・キーワード順序・全正式文章・グラフラベル・特殊命式全文・A4縦を照合。Popplerで全5ページをPNG化して目視確認。

| 確認用basename | 内容 | 本文枠 | PDF |
| --- | --- | --- | --- |
| nikkan-normal | 既存の2026合成例、己の正式説明、特殊命式2件 | 45pt維持 | 82%、2ページ |
| nikkan-longest | 正式辞書の最長説明「辛」と特殊命式8件を組み合わせた表示検証用合成例 | 69ptへ拡張 | 82%、3ページ |

最初の長文PDF検査では、56ptの見積もり枠で末尾キーワードが欠けることを検出。拡張時に13ptの余裕を追加し、再生成した最終PDFで全文と表示を確認した。通常例は45ptのまま。PDF異常系テスト内の失敗注入ログは期待されるもので、最終テスト失敗なし。

前回受入済み出力の通常2件/特殊命式8件と比較し、特殊命式領域19〜24行はセル・スタイルを含むXMLが同一。B25以外の全セルもXML同一。後続の文章・グラフは全文照合と目視で確認。最終出力に見切れ・重なりなし。長文＋8件では既存改ページ処理により3ページとなり、最終ページは総合アドバイス。2ページ固定は今回の要件ではない。

自己評価: 今回の表示構造・全文表示は良好。実Excelでの読み込み・PDF変換とその印刷結果を確認した。Excel編集画面の別途UI目視、他PDFエンジン、フロントエンドbuild、全体回帰は未実施。本人による今回の表示受入は未完了。

## 成果物と保護対象

保存先: `C:/Users/bunch/Documents/Codex/fortune-app/outputs/phase10-nikkan-keywords-20261023`。

- `nikkan-normal.xlsx` / `.pdf`、`nikkan-longest.xlsx` / `.pdf`。
- `verification.json`、`pages/` のPNG、`excel-tests.log` / `pdf-tests.log` / `k01-k03-tests.log`。
- ローカル補助スクリプト: `research/run_nikkan_keywords_acceptance.py`（Git対象外）。修正前2ファイルの控えは `_backups/public/nikkan-keywords-20261023`。

開始後と確認後でSHA256が同じ:

- `report_data.py`: `65aefdc8d40860797537bd1893d44358c859c7b6d3921e0ced9e7347dd608031`
- `templates/kanteisho.xlsx`: `289b5d1093061487ba2e0e18bf6cd1c5c6056609daa31cbe0629e21489fa3b22`
- `special_chart_logic.py`: `26a94b84164b7ecab1c488af9fff225157bd07788f1a385672b31ff0247e7b76`
- `data/history.sqlite3`: `9faacb971b429179eba95083a32b81f2c8f7321bb1e538b47665e9b3055d3da1`

試験DBは既存テストの専用一時領域のみ。既存DB変更、mainへのmerge、本番配備、稼働中アプリ再起動、環境変更、Notion書込みなし。mainは `e8b53082775744a74f66502e8fb8f3cef72974c1` のまま。

上記3ファイルのみを専用branchにcommit/pushする。commit hashと最終git statusは完了報告に示す。
