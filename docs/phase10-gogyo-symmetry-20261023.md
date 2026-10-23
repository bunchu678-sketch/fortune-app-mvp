# 五行図：外枠中心・左右対称・円とラベルの等間隔化

## 開始状態（2026-10-23 JST）

- 正規Repository: `C:/Users/bunch/Documents/Codex/fortune-app-public`。
- 開始branch: `phase10-nikkan-keywords-20261023`。
- HEAD: `3aed9c2c8def8a51a6f5a2c5a0c7fdf4dd2c547c`。working treeはclean、同名originと一致。
- この最新B2B commitを継承し、専用branch `phase10-gogyo-symmetry-20261023` を作成。直前の特殊命式4列表・干支キーワード本文内配置を維持。
- 共通 `C:/Users/bunch/.codex/AGENTS.md` を上位として開発元AGENTS.mdを確認。正規Repositoryに固有AGENTS.mdなし。引継ぎ書と前回の特殊命式/キーワード修正記録、既存帳票コード・テストを確認。未解決の指示矛盾なし。
- 前工程で確認済みのNotion鑑定書判断ログを継承し、今回も「五行図」の関連検索を実施。Notion作成・更新なし。

## 調査と原因

描画箇所は `report_xlsx.py` の `polish_gogyo_layout`。完成XLSXの `xl/drawings/drawing2.xml` にある原本図形を、pt/EMU単位の座標で再配置する。円は正五角形、相生は曲線矢印5本、相剋は直線矢印5本。

1. 左右ラベルの枠は対称だったが、文字は両方とも左寄せ。そのため左側だけ円から離れて見えた。
2. 上段/下段の円とラベルの間隔がそれぞれ3pt/8pt、高さも上段は円の上、下段は円の中央と異なっていた。
3. 正五角形の中心を外枠高さの55%に置く固定値で、上部ラベルまで含めた図全体の中心を計算していなかった。
4. 外枠だけは旧twoCellAnchorで、内部はabsoluteAnchor。外枠のキャッシュ座標と実Excelの表示位置が不一致だった。初回PDFで円の対称軸と実際の外枠中心に8.125ptの横ずれを検出。

## 変更ファイル

### report_xlsx.py

- 外枠・円・矢印・ラベルを同じ絶対座標基準に統一。外枠の原本形状・線・丸角・キャッシュ座標の位置/寸法を維持して、外枠アンカーだけをabsoluteAnchorにする。元のセルアンカー依存による表示ずれを解消。
- 水平軸は外枠中心。上下は、上端ラベル〜最下端の円までの全体矩形を外枠の上下中央へ配置。
- 円の配置半径は外枠高さの36%から35%へ小幅調整。円自体の半径10.3%は維持。矢印は新しい円座標から従来と同じ方式で再計算。
- 左右ラベルは60pt×16pt、円から6pt、円の中心とラベル枠の中心を同じ高さに統一。上部ラベルも円から6pt。
- 左ラベルは右寄せ、右ラベルは左寄せ、上部は中央寄せ。内部余白を0、縦中央、折り返し/自動縮小なしとし、円に近い文字端を基準に配置する。
- 変更範囲を表す `GOGYO_DRAWING_IDS` に外枠ID2を追加。意味・五行点数・対応関係・字体・色・線・矢印の種類は維持。

### tests/report_export_cases.py

- 円とラベルの鏡映対称、等間隔、同じ高さ、図全体の矩形中心、外枠の絶対座標化を1EMU以内で検査。全体矩形の検査では外枠自身を除外し、中心の誤判定を防ぐ。
- 五行の並び5通りと異なる点数で幾何形状が変わらず、入力データも非変更であることを確認。
- 既存の円形、点数中央表示、矢印の接続/余白、色、原本ハッシュ、他の本文/グラフ/特殊命式/キーワード配置の検査を維持。

### docs/phase10-gogyo-symmetry-20261023.md

本検証・引継ぎ記録。

## テスト・実Excel/PDF結果

| テスト | 最終結果 |
| --- | --- |
| `.venv/Scripts/python.exe -B tests/report_export_cases.py` | 58件成功 |
| `.venv/Scripts/python.exe -B tests/report_pdf_cases.py` | 21件成功 |
| `.venv/Scripts/python.exe -B tests/k01_k03_cases.py` | 42件成功 |
| `git diff --check` | 成功 |

合成例2ケースを実Excelで読み取り専用として開き、既存adapterでPDF化。pypdfで全文、五行値、特殊命式、本文内キーワード、グラフラベルを確認。通常例2ページ・長文＋特殊命式8件3ページは修正前と同じ。Popplerで前後全ページを画像化し、変更ページを目視比較。

pdfplumberで最終PDFの実際の円・外枠・ラベル文字位置も測定。両ケースで以下が一致:

- 外枠の水平中心と円の対称軸: ともに407.605pt（計算誤差を除き差0）。
- 知性↔表現: ラベル上端差0pt、円から左4.8556pt / 右5.03pt。
- 行動↔魅力: ラベル上端差0pt、円から左4.8456pt / 右5.04pt。
- XML上の名目間隔は左右とも6pt。PDFは82%印刷、文字幅の端数差を含む実測差は最大0.1944pt（約0.069mm）。

比較用XLSXをZIP展開して照合し、`drawing2.xml` 以外の全ファイルが前回出力とバイト一致。描画XMLでも五行図の外枠・円・矢印・ラベル以外は同一。五行図内の文言・runの字体・線の色/属性も同一。特殊命式4列表と干支本文内キーワードを含む他セクションに影響なし。

途中の検出・対応:

- 測定スクリプトの初回実行は、PDFの灰色がRGB配列ではなく数値で返る図形に対するTypeErrorで停止。測定用の型判定を修正して成功。アプリ側エラーではない。
- 左右ラベル対称化後のPDF測定で、上記の外枠アンカーとキャッシュ座標の横ずれを発見。外枠も絶対座標化し、再生成・58件テスト・PDF実測で中心一致を確認。未解決エラーなし。

自己評価: 座標と実PDFの両方で左右対称・中央寄せ・距離統一を確認し、目視も良好。Excelは実Excel読込とPDF印刷結果を検証した。Excel編集画面を別途UIで目視する検査、別PDFエンジン、フロントエンドbuild、全体回帰は未実施。本人による最終受入は未完了。

## 成果物・保護

保存先: `C:/Users/bunch/Documents/Codex/fortune-app/outputs/phase10-gogyo-symmetry-20261023`。

- `before/nikkan-normal.xlsx` / `.pdf`、`before/nikkan-longest.xlsx` / `.pdf`: 直前の出力コピー。
- `after/nikkan-normal.xlsx` / `.pdf`、`after/nikkan-longest.xlsx` / `.pdf`: 最終出力。
- `pages/`: 修正前後のPNG。`verification.json`: 実測・照合結果。`excel-tests.log` / `pdf-tests.log` / `k01-k03-tests.log`: 最終テストログ。
- ローカル検証スクリプト `research/run_gogyo_symmetry_acceptance.py` と修正前2ファイルの控え `_backups/public/gogyo-symmetry-20261023` はGit対象外。

開始前後のSHA256一致:

- `report_data.py`: `65aefdc8d40860797537bd1893d44358c859c7b6d3921e0ced9e7347dd608031`
- `templates/kanteisho.xlsx`: `289b5d1093061487ba2e0e18bf6cd1c5c6056609daa31cbe0629e21489fa3b22`
- `special_chart_logic.py`: `26a94b84164b7ecab1c488af9fff225157bd07788f1a385672b31ff0247e7b76`
- `data/history.sqlite3`: `9faacb971b429179eba95083a32b81f2c8f7321bb1e538b47665e9b3055d3da1`

mainは `e8b53082775744a74f66502e8fb8f3cef72974c1` のまま。既存DB変更、占術ロジック変更、正式鑑定文変更、mainへのmerge、本番配備、アプリ再起動、環境変更、Notion書込みなし。試験DBは既存テストの専用一時領域のみ。

上記3ファイルだけを専用branchにcommit/pushし、hashと最終statusは完了報告に示す。
