# Phase 10 鑑定書レイアウト修正・検証記録（2026-10-20）

## 対象と開始時Git状態

- 正規Repository: C:\Users\bunch\Documents\Codex\fortune-app-public
- 正規W（Next.js + Python API）のExcel/PDF出力整形のみ。
- 開始branch: phase10-member-navigation-20261009
- 開始HEAD: 63e769ea6b62a08e4012ec7c54ab3ec5dc22cbcd
- 開始working tree: clean（staged/unstaged/untrackedなし、optional locks無効）。
- originの開始branchをls-remoteで照会し、同じHEADを確認。fetch/pullは実行していない。
- 指定の新規branch phase10-report-layout-fix-20261020 を作成。作成前に同名local branchがないこと、push前に同名remote branchがないことを確認。
- origin/main: e8b53082775744a74f66502e8fb8f3cef72974c1。開始branchとともに更新しない。
- global AGENTS.md v1.3を共有規則として、同chatで確認済みの開発元AGENTS・親WORKSPACE_RULESを適用。public固有AGENTSはない。最新の明示的な修正・branch作成・commit/push指示の範囲で作業し、追加の規則競合なし。
- 既存Phase 10回帰記録、会員遷移改善記録、テスト計画、Phase 5 Excel出力資料と既存出力テストを参照。Notionは本作業で読み書きしていない（同chatで確認したW正本等の有効原則を維持）。

## 変更ファイル

| ファイル | 内容 |
|---|---|
| report_xlsx.py | 既存OOXML出力整形で、以下7項目を修正 |
| tests/report_export_cases.py | 曲線・配色・文字サイズ・斜線除去・特殊命式の複数行・見出し/キーワード・年運セル配置の契約を検証 |
| tests/k01_k03_cases.py | 年表示の出力先だけL60からL61へ更新。2026正式projectionの固定digest、年別文章/private除去の判定は維持 |
| 本記録 | 修正前後、確認方法、結果、制限 |

templates/kanteisho.xlsx（承認テンプレート原本と固定SHA-256）は変更していない。既存の図形・5グラフを保つため、従来の標準ライブラリによる限定OOXML編集を継続した。依存関係の追加なし。
report_data.py、占術ロジック、正式解釈文、Web UI、認証・B2B/B2C権限、Excel/PDF APIや変換adapter、DBは変更していない。

## 7項目の修正前後

| 項目 | 修正前 | 修正後 |
|---|---|---|
| 五行相生矢印 | straightConnector1の直線 | Web SVGの短い円弧（chord × 1.55）に近い三次Bezier自由曲線。相生5辺と相剋5辺の向き・正式点数を維持 |
| 五行配色 | 灰色/薄橙、白い円 | Webの相生 #9EB9A8、相剋 #D7A96B、円 #232825、文字/輪郭 #F4EFE6。印刷枠内の既存配置を維持 |
| 鑑定日 | 日付部分8pt | C2/D2を11pt、D2:F2の既存結合と左寄せを維持 |
| 日柱通変星 | E10の斜線と「－」が重なる | セルの斜線だけ除去。「－」という表示値・周囲の罫線は維持 |
| 特殊な命式 | 見出し14.1pt、データ行約12.95pt | 見出し20pt、値のある行は最低20pt。明示改行と全角/半角幅に応じて行高を確保し、中央配置・折返し。空き行の高さを再配分し、通常例はページ高さを維持 |
| 十二運星 | 星名が小さいキーワード欄の先頭 | C37/I37/C40/I40の見出し末尾へ「：星名」。C39/I39/C42/I42は「キーワード：本文」のみ。見出し19pt・キーワード行18ptへ既存余白を再配分し、本文図形のサイズ/文字は保持 |
| 年運見出し/対象年 | B60:K60に見出しと注釈、L60:N60に対象年/干/支 | B60:H60に「●年運」、I60:N60に通常10pt・非Boldの注釈。L61=対象年、M61=干、N61=支。テーマの結合をG61:K61へ縮め、数値・内容は維持 |

特殊命式の複数行で元の余白予算を超える場合は、説明を切り捨てず行高を増やし、印刷倍率を元の第1ページ高さに応じて調整する。今回の通常2026/2027は82%、2件とも2行の合成確認は81%。固定の手動改ページ35行目を維持。
図形の行アンカーに加え、キャッシュされた物理座標にも行高差分を反映した。

## 修正前後の内容不変確認

本人確認用の新しい合成環境 fortune-phase10-local-cWmZYc の、手順書にある元の生徒2026/2027履歴IDを指定して、SQLiteを mode=ro&immutable=1 で読み取った。受入操作で増えた履歴と混同しない。パスワード、メールアドレス、cookie等は本記録・成果物の説明・Gitに含めない。
保存済みsnapshotを使い、鑑定の再計算はしていない。

- build_reading_reportのcells/texts/chart_cellsは、2026/2027とも修正前と完全一致。
- XLSXの実際の値の差分は、表示再配置の16セルだけ。
  B60、I60、L60/M60/N60、L61/M61/N61、C37/I37/C40/I40、C39/I39/C42/I42。
- ZIP内の変更パーツは、原本sheet2.xml、styles.xml、drawing2.xmlの3つだけ。他パーツはbyte単位で一致。グラフの元データ/cache、正式本文、命式/年運/五行数値を維持。
- K01既存の2026正式report projectionの固定digestもPASS。期待baselineを更新していない。
- 2026正式文章を保持。2027は「この年の正式解説は未登録です」で、2026向け総合文章を流用していない。

## 実行した確認

| 確認 | 結果 |
|---|---|
| python -X utf8 -B -m unittest discover -s tests -p report_export_cases.py | 49/49 PASS（最終22.875秒） |
| python -X utf8 -B -m unittest discover -s tests -p report_pdf_cases.py | 21/21 PASS |
| python -X utf8 -B -m unittest discover -s tests -p k01_k03_cases.py | 42/42 PASS |
| Windows Excel実開封・既存adapterによるPDF変換 | 最終2026/2027ともPASS、修復要求なし |
| Excel画面確認 | 最終2件を読み取り専用で開き、日付・命式・五行図の表示を目視確認 |
| PDFページ数/用紙 | 各2ページ、全ページ595.2 × 841.44pt（A4縦相当） |
| PDF全4ページの描画/目視 | 曲線矢印、指定7項目、本文/図/表/下罫線に目立つ見切れ・重なり・欠落なし |
| 特殊命式2件とも2行の合成例 | Windows Excel/PDF生成、2ページ、4行すべて本文抽出・目視で表示確認 |
| 既存ローカルdata/history.sqlite3 | 開始/最終SHA-256一致（下記） |
| 既存Web/API | 同じ所有PID 7288/12888、3000/8765の127.0.0.1限定で稼働を確認。停止/再起動なし |
| git diff --check | PASS |

既存DB SHA-256:
9faacb971b429179eba95083a32b81f2c8f7321bb1e538b47665e9b3055d3da1

フル回帰、Webの新規UI試験、本番・Linux PDF、実メール・実課金は実施していない。出力関連と今回の変更に必要な範囲の検証。

## 作業中に検出し解消した問題

- 図形XMLの要素を同じ位置へ並べ替える初期コードでNotFoundErr。先頭にある場合は移動しないよう修正し、再生成成功。
- 独自曲線をcxnSp（コネクタ）へ格納した初期版は、Excelがdrawing2.xmlの回復を要求し、既存PDFadapterはcom_start_failedで安全停止。元ファイルの変換成功とExcelの診断により図形パーツへ限定。
  読み取り専用の診断コピーで回復内容を確認したが、修復されたファイルは最終成果物とせず、保存せず閉じた。
  最終版は標準の自由曲線spとして格納し、修復なしの実Excel開封・PDF生成を両年で確認。API/変換adapterの安全性は緩めていない。
- 複数行テストの初期fixtureが実改行ではなく文字列「\\n」だったため1件FAIL。fixtureだけ実改行へ修正して49件PASS。判定を緩めていない。
- 前回のExcel画面を閉じずに同名ファイルを開こうとして同名ブック制限になったため、最終サンプル名を「-修正版」と区別。旧ファイル・旧ウィンドウは変更しない。
- 開発の技術参照: Microsoft LearnのCustomGeometry/CubicBezierCurveTo資料（https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.customgeometry?view=openxml-3.0.1）。最終可用性の根拠は今回の実Excel/PDF確認。

## 確認用成果物（Git対象外）

C:\Users\bunch\Documents\Codex\fortune-app\outputs\phase10-report-layout-fix-20261020\

最終確認対象:
- 鑑定書-2026-修正版.xlsx / 鑑定書-2026-修正版.pdf
- 鑑定書-2027-修正版.xlsx / 鑑定書-2027-修正版.pdf

同フォルダに修正前Excel/PDF、固定合成snapshot、差分検査JSON、PDF描画画像と複数行の確認用例を保存。認証情報を含めない。公開Repositoryへ出力バイナリやDBを追加していない。

## 残る課題・反映範囲

- 本人による修正版の最終受入と実印刷は未実施。Phase 10全体完了・本番導入承認ではない。
- 稼働中の本人確認用APIは、既存指示に従い停止/再起動していない。Pythonモジュールは起動時に読み込まれるため、現在のWebからの再出力には旧整形が残り得る。今回は最新コードを新しいPythonプロセスで使って生成した上記修正版を確認する。Webからの再出力へ反映するには、別途の確認用API再起動が必要。
- Windows Excelでの正式印刷確認と、長大な特殊命式説明・6行全ての複数行を含む全組合せの目視確認は別途。今回の通常2年分および2件×2行の合成例は確認済み。
- 他の既知Phase 10課題、所属外アクセスの英語表示、B2C追加開発には手を付けていない。
- main merge、VPS接続/配備、実メール/課金、Notion更新なし。
- 差分確認後にこの4ファイルだけを指定branchへcommit・pushする。最終HEADとorigin一致・cleanは完了報告で通知する。
