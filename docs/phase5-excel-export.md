# Phase 5 鑑定書Excel出力

## 出力経路

- 博士版の結果画面と履歴詳細画面の「鑑定書を出力」→「Excelで出力」。PDF出力は同じ完成Excelを変換する（[PDF出力](phase5-pdf-export.md)参照）。
- `POST /api/export/excel` は `{"export_token":"…"}` または `{"reading_id":"…"}` のどちらか一方だけを受け付ける。任意の鑑定文、テンプレートパス、user_id等は受け付けない。
- 未保存鑑定：既存 `/api/fortune` が正式結果を計算した時点でサーバー側に入力と結果の独立コピーを保持し、ランダムな `excel_export_token` を返す。出力時には再計算しない。
- 保存済み：サーバーのownerスコープで削除されていない履歴を取得し、保存当時のinput/result/display snapshotを使用する。現在のコメント辞書から取り直さず、再計算しない。
- `report_data.py` は顧客向けデータを明示的に選択する。`report_xlsx.py` は承認版のコピーをメモリ上で限定更新する。出力結果はレスポンスで返し、サーバーのディスクへ顧客鑑定書を保存しない。

## テンプレート

`templates/kanteisho.xlsx` は配備時に一緒に運べるようrepo直下の専用フォルダに配置した。元承認版とバイト単位で同一。

SHA-256: `289b5d1093061487ba2e0e18bf6cd1c5c6056609daa31cbe0629e21489fa3b22`

出力ごとにハッシュを検証し、不一致なら503で停止する。元テンプレートへ書き込むコードはない。Python標準ライブラリのZIP/XMLのみで編集し、Linuxでも同じ処理を使える。Excel COM・openpyxl・LibreOfficeへの実行時依存はない。

生成する顧客用コピーでは、古い計算用シートの値・数式・参考画像、印刷範囲外の旧辞書・古い鑑定文、不要な共有文字列と計算チェーンを除去する。非表示シートの枠、用神領域の非表示設定、印刷設定は保持する。可視シートの図形・矢印・5グラフ・テキストボックス・アンカーは保持する。

## データ対応

| 項目 | 正式データ | 出力場所 |
| --- | --- | --- |
| 基本情報 | input snapshotの姓・名・生年月日・出生時刻、当時の基本情報／display snapshot、正式年齢 | D3、G3、J3、L3、M3、N3 |
| 命式／空亡 | meishiki、star_data、kubou | D7:G12、E13 |
| 五行A | gogyo_variants.A.gogyo.chart_order／scores | K6、M8、L12、J12、I8 |
| 今年／大運差分 | A→B／B→Cの正式点数差 | C15、C16 |
| 特殊命式 | special_meishiki.rowsの判定／結果だけ | C19:D24、E19:N24 |
| 日干 | personality.nikkan.description／keywords | Phase5_Nikkan、B25 |
| 人生4段階 | life_stage_tsuhenseiのouter／inner／公開コメント | Phase5_Stage0〜3 |
| 本来の自分らしさ | current_life_stage_pair.public_comment、当時のcurrentStageName | B34、Phase5_CurrentStage |
| 十二運星 | juuni_unsei.rowsの見出し／星名／公開コメント／keywords | 行37〜42、Phase5_Juuni0〜3 |
| 考え方 | juuni_unsei.thinking | Q/R/T/U/W/X列の元セルと5グラフの表示キャッシュ |
| 大運／接木運 | daiun.rowsの年齢帯／通変星／天干／地支／次の大運との間が接木運 | C56:L59、該当境界の太罫線 |
| 年運 | yearly_overallの対象年／年干支／通変星／theme | L60:N60、E61、G61 |
| 月運 | yearly_flow.rowsの2月〜翌1月、空亡 | C63:N66、空亡月を赤字 |
| 総合アドバイス | yearly_overall.comment全文 | 既存テキストボックス（drawing id=3） |

五行差分は変化した五行のみ、符号付きで表示する。無変化と取得不能／境界待ちは既存UIに合わせた状態表示にする。特殊命式の現行実装は最大5種類を行ごとにまとめるため6行以内。将来7行以上になった場合は省略せず出力を停止する。大運の固定試作境界は取り除き、正式な境界フラグに合わせて設定する。

考え方の棒グラフはグループの正式合計に対する比率、仕事4分類は正式点数を用いる。出生時刻不明で合計が95点の場合も100点と仮定しない。文字列は数式として解釈されないinlineStrで書く。

メモ・過去メモ・privateコメント・支援情報・内部計算詳細・利用者／人物／グループ／履歴ID・管理versionはデータ層の出力項目に含めない。用神の未実装値は作らない。

## 現時点の利用者設定とトークン

Phase 4と同じ `FORTUNE_ENV=development` と `FORTUNE_HISTORY_DEV_USER_ID` の明示設定を利用する。本番認証の代用にしない。認証設定がない場合は履歴／Excel出力を503で無効にする。

未保存結果のトークンは同一APIプロセス内で1時間、最大256鑑定保持する。期限切れ・再起動・別プロセスへの接続の場合は、保存済み履歴から出力するか再鑑定する旨を表示する。複数worker／本番認証を導入する工程で、共有保持先と認証済みownerの取得方法を確定する。

## 検証

- `python -B tests/report_export_cases.py`：構造、正式値、境界ケース、秘密情報除外、利用者分離、削除済み拒否、保存当時snapshot再現。
- `tests/report_export_ui.cjs`：専用の一時履歴DBを設定したローカルAPI/UIで実行する。PC 1280px／スマホ375pxの未保存・保存済みダウンロード、出力時に鑑定APIを再実行しないこと、Excel／PDFの形式選択、失敗表示と復帰、横幅を検証。
- 正式な架空テスト入力から完成Excelを生成し、Excel本体で読み取り専用で開いて全セル・グラフ元データ・テキストボックス・A4縦2ページを検証。

Windows開発環境のPDF出力は[PDF出力](phase5-pdf-export.md)参照。Linux本番変換エンジンと本番配備は次工程。既存の正式コメントに年固有文言が残るTier C課題は今回の出力層で改変・補完しない。
