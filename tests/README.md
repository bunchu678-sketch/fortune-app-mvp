# fortune-app W 正規版：商品化前回帰テスト

作成日: 2026-09-10。対象はこのリポジトリのW（Next.js + FastAPI + Python）。
基準HEAD: 4b55b933fa4476b7a17ce5dc9641b8073069253c。

本体を修正せず、確定仕様の回帰、現行実装の変化、既知課題を分けて報告します。
Sとの一致はWの正解条件ではありません。通常実行にD、Streamlit、Node、VPS、Notion接続は不要です。

## 実行

Windowsでは tests/check.cmd をダブルクリックします。Pの .venv/Scripts/python.exe を使用し、結果を表示したまま停止します。
環境の新規作成・更新・インストールは行いません。

PをカレントディレクトリとするPowerShellの一括コマンド:

~~~powershell
.\.venv\Scripts\python.exe -B .\tests\check.py
~~~

任意のS/W比較（Dは読み取り専用）:

~~~powershell
.\.venv\Scripts\python.exe -B .\tests\check.py --compare-s ..\fortune-app
~~~

テスト基盤を編集したときの自己検証:

~~~powershell
.\.venv\Scripts\python.exe -B .\tests\test_harness.py -v
~~~

別の既存Python環境でも、同じcheck.pyへ絶対パスでアクセスできます。
EACal/ephem/pytz/FastAPI/Uvicornは本体の既存依存です。不足時は実行不完全で終了します。
pytest/httpx等の新規依存は不要です。確認環境: Python 3.12.14、eacal 0.0.3、
ephem 4.2.1、pytz 2026.2、fastapi 0.139.0、uvicorn 0.51.0。
Node v24.19.0は所在確認のみ。通常実行は数秒。stdoutのみで報告し、ログやfixture更新は行いません。
-Bとsys.dont_write_bytecodeでPythonキャッシュ作成を抑止します。

## 結果の読み方

| 区分 | 意味 | 変更検出時 |
| --- | --- | --- |
| A | 出典を確認した正式仕様 | FAIL。原因を調査し、原則として通過が必要 |
| B | 現行Wの観測・参考比較 | REVIEW。正解の変更か不具合かを人が判断 |
| C | 既知課題・未確認事項 | 非ブロッキング。旧挙動への復帰を要求しない |

終了コード: 0=通常観測まで一致、1=A失敗、2=B要確認、3=環境・fixture・実行不完全またはファイル整合性エラー。
AとBが同時に変われば1。Cが未解決でも0になり得るため、0は「商品化済み・全課題解決」を意味しません。
CのCHANGED / RECHECKは解決認定ではなく再確認の合図、UNVERIFIEDは検出不能です。
S比較を指定しない場合はNOT RUNと表示し、PASS件数に含めません。

## ファイル構成

- check.py: Tier実行、終了コード、実行前後の本体SHA-256照合。
- tier_a.py / fixtures/formal.json: 正式仕様。各caseにID、仕様、入力、期待値、出典、参照位置。
- tier_b.py / fixtures/observed.json: 計算・サービス・APIの限定観測。返却全文・鑑定文は固定しない。
- tier_c.py: K01〜K07。課題が解消してもFAILにしない。
- comparison.py: 任意のS/W純粋関数比較。
- test_harness.py: 意図的なメモリ内変化の検出確認。本体ファイルを書き換えない。
- check.cmd: Windows用一括実行。
- README.md: 出典、資産評価、未確認範囲、運用手順。

本体SHA-256はP、任意比較時は参照フォルダも対象です。
Git内部、仮想環境、node_modules、.next、キャッシュ、バックアップ、tests等は除外します。
VPSの実ファイル、依存ライブラリ全体、既存キャッシュまで不変性を証明する仕組みではありません。

## Tier A：227ケース

| 対象 | 数 | 根拠 |
| --- | ---: | --- |
| 1948〜1951年・十二節 | 48 | ユーザー写真確認済みの万年暦値と、固定JSTへ変換・分丸めしたEACal値との差が60秒以内 |
| 分四捨五入 | 12 | 秒30以上切上げという採用指示。29.999999秒・日/月/年またぎ・aware時刻 |
| 固定JST変換 | 4 | 採用指示から算術的に求めたUTC+09時刻。+10からの実変換・同一瞬間・日またぎ |
| 2020〜2022年の十二節境界 | 108 | 36境界×1秒前/ちょうど/1秒後。採用方式が返す境界を基準に前節/新節を判定 |
| 警告範囲 | 9 | 通常前後180秒を含む。181秒・旧90分範囲は含めない |
| 過去の参照確認済み四柱 | 11 | Dのreference_checkedかつ泰山流資料を出典とするケース。自動計算とWサービスの両経路 |
| 0時・23時の日時ケース | 5 | 確認済み2021年日柱/時柱と正式な0時日替わり・23時時干規則から導出 |
| 23時の時干用日干 | 30 | 10日干×22時/23時/0時。癸→甲も確認 |

境界108件は、絶対日時の独立検証108件ではありません。
絶対日時照合48件と、切替の不等号・前年扱いを検証する境界ケースを分けています。
同一結果の四柱ケースも、旧参照IDを維持し境界に対する位置を追えるようにしています。

### 出典

- [固定JST方式の採用決定](https://app.notion.com/p/39ef414e63af81bbb53dc803e6f244e4):
  実変換→分丸め→naive比較、境界ちょうどは新節、通常3分警告、旧1950年90分警告廃止、48件が±1分以内という必須条件。
- [1951年の午前午後訂正を含む再監査](https://app.notion.com/p/39ef414e63af813d94fce5f6b6325662):
  1951年小寒12:31、立秋17:38、白露20:19。残る45件は確認済み値を維持。
- D/research/run_taizan_sekki_correction_implementation_validation.py:
  CONFIRMED_REFERENCE_TEXTの48値と既存検証を部分再利用。
- D/research/calendar_validation_cases.py:
  確認済みケースを出典・ID付きで選択。実行器自体は使わない。
- D/docs/calendar_validation_notes.mdの「泰山流の23時台時柱について」と今回の明示指示:
  日柱は0時切替、23時だけ時干算出に翌日日干を使用。

Notionのページ検証状態と、本文に記録されたユーザーの採用決定は別概念です。
今回の根拠は採用記録・明示指示・出典付き検証ケースです。原資料の書籍画像そのものは今回再読影していません。

### Pへfixtureを置く理由

Dを実行時依存にすると商品版の再現性が失われるため、48参照値と限定的な四柱をPのテスト専用JSONへ切り出しました。
原本のSHA-256・出典を記録し、DのCSVやコードは変更していません。本体への万年暦表組込みではありません。
既存.gitignoreのCSV・run_*.py除外にかからないJSONを使い、設定変更も回避しました。

旧reference_2021_0203_2358は年=辛丑/月=庚寅ですが、採用済み方式の立春23:59では23:58は年=庚子/月=己丑です。
後から採用した方式と旧固定時刻との差をK06に明示しました。日=壬午・時=壬子と23時規則は別に保護しています。
旧ケースや本体を修正して整合させてはいません。

完全一致22件、最大差がちょうど60秒、MAE32.5秒等の以前の集計結果は固定しません。
48件すべてが60秒以内という採用条件を保護し、差が縮まったときは失敗させません。

## Tier B：通常35項目・任意S比較1325入力

fixture27項目:

- Wサービス4条件: 通常、時刻不明、性別未選択、逆運側。命式・星・五行・大運・接木運・月運・年運の必要部分。
- 通変星100セル、十二運星120セル、空亡60セル。各表を1項目と数える。
- 蔵干204入力: 12支×17日数（1、7〜21、40）。深浅表の全行・境界・末尾丸め。
- 五行8条件: 通常、沖、三合、方合、半会、沖と三合候補の競合、鑑定年作用、時柱欠落。
- 出生地4条件: 東京都、沖縄県、兵庫県、未選択。経度・補正分・前後日へのまたぎ。
- 大運方向20組、起運日付差4条件、鑑定年干支1条件、特定日時23時前後1組。

コードによる8項目:

- レスポンスの主要型・ネスト・JSON化。
- 月運15日正午、総合年運2月15日正午の実呼出し日時。
- 同じ節入り後日数を4柱の蔵干計算へ渡す経路。
- FastAPIのhealth、正常POST 200、範囲外POST 422、存在しないURL 404。

APIは実際のFastAPIアプリをASGIとしてメモリ内実行し、待受ポートを開きません。
nginx、Next.jsのrewrite、ブラウザ、認証、VPS公開状態のE2E検証ではありません。
追加API項目は許容し、private文章の存在を正式API契約にはしません。

任意S比較は14関数1325入力。Sのpersonality_logic.pyから対象関数だけをASTで抽出し、
S自身のfortune_data.py・comments.pyの辞書を使用します。UI全体はimportしません。
W辞書をSへ流用して一致を作りません。関数が削除・変形された場合は、黙ってスキップしません。
35は確認項目数であり、表の全セルを個別に数えて水増ししていません。

## 仕様確認待ち

| 対象 | 判定 | 配置 |
| --- | --- | --- |
| 五行作用用の鑑定年干支 | 西暦年計算を確認。立春前を含む正式採用記録は確認できず | B |
| 月運15日正午 | 現行実装。代表日時の正式採用根拠は確認できず | B |
| 総合年運2月15日正午 | 現行実装。代表日時の正式採用根拠は確認できず | B |
| 起運の日付差 | 現行実装。同一日の節入り前後でも同日数になる。採用根拠は確認できず | B |
| 出生時刻不明 | 不具合修正履歴はあるが、正午仮置き・出生地補正省略・時柱空欄化を一式として承認した根拠は不足 | B |
| 蔵干の全表値・4柱共通日数 | 深浅表使用の記録あり。個別値・共通日数の独立確認資料は取得できず | B |
| 通変星・十二運星・空亡の全対応表 | 辞書とS比較を確認。全表の独立した正式資料は取得できず | B |
| 五行点数と関係判定の優先順位 | 計算を追跡。本人確認済みの期待点数ケースを確認できず | B |
| 大運の列・接木運年齢幅 | 現行計算を観測。正式資料による根拠は不足 | B |

「確認できず」は仕様が存在しないという断定ではなく、ローカル資料と関連Notion記録・検索で取得できなかった範囲です。
他流派の一般知識から補完しません。根拠と期待値が承認されたものだけ後続作業でAへ昇格できます。

## Tier C

| ID | 内容 | 確認方法 |
| --- | --- | --- |
| K01 | 2027年指定に2026年文章 | 対象年と文章内の年を観測 |
| K02 | UIは1〜3件、サービスは4件以上 | 4候補を処理するか観測。UI選択肢はpage.tsxを確認 |
| K03 | 非表示の鑑定者情報をAPI返却 | 実APIのprivate項目を検出。全文は表示しない |
| K04 | 2050年月運の2051年1月が範囲外 | 翌年1月行のerrorを観測 |
| K05 | S/Wの表示差 | 手動確認。差があるだけでFAILにしない |
| K06 | 旧資料23:58と採用方式23:59 | 差を報告。資料誤り・本体バグと断定しない |
| K07 | 修正済み：OFF時の候補解析を回避 | A-K07-off-*で正式な非干渉仕様を保護。未解決Tier Cから除外 |

K05参照:

- S五行SVG: chart_render.pyのbuild_gogyo_relationship_svg（461行付近）、show_gogyo_relationship_chart、render_gogyo_balance。
- W横棒: fortune-next-app/app/page.tsxのGogyoChart（123行付近）。
- 異常干支: Sのapp.pyは日柱中心、Wのspecial_chart_logicは4柱を扱う。
- 接木運、大運空亡、特定日時、private情報: 計算結果の有無と画面表示を区別。見た目の自動合否判定は今回対象外。
- [W正規版方針と五行図移植の未完了決定](https://app.notion.com/p/3d6f414e63af817eaf03f851e2780f48):
  有効・本人確認済み、最終確認日2026-09-09。今回は移植しない。

## 既存資産の評価

| D側資産（特記以外はresearch内） | 分類・扱い |
| --- | --- |
| run_taizan_sekki_correction_implementation_validation.py | 部分再利用。48値・丸め・固定JST・境界。完全一致数やMAEの固定は不採用 |
| calendar_validation_cases.py | 部分再利用。参照確認済み11件をA、2021年23:58をK06。development/todoはAにしない |
| run_calendar_validation.py / run_calendar_todo_report.py / case_template | research専用。旧sekki_data経路や開発ステータスを扱う |
| run_candidate_day_base_validation.py / run_day_pillar_base_probe.py / run_hour_pillar_probe.py / run_month_pillar_probe.py | 日柱基準・時柱・月柱の探索と参照用 |
| run_taizan_sekki_correction_probe.py / run_sekki_correction_profile_probe.py | 候補補正方式の探索用 |
| run_sekki_base_coverage_report.py / run_sekki_base_data_source_probe.py | データ整備と所在の診断用 |
| run_sekki_library_* 3本 / run_compare_eacal_base_with_existing.py | ライブラリ・旧基準比較用。旧timezone処理を含む |
| run_sekki_rounding_rule_probe*.py 2本 / run_sekki_model_comparison_probe.py / run_sekki_residual_linear_probe.py | 丸め・線形等の候補比較。research専用 |
| run_create_sekki_correction_input_batch.py / run_generate_eacal_sekki_base_csv.py / run_merge_sekki_correction_input_batch.py | CSV生成・merge。書き込みを行うため通常回帰には含めない |
| run_sekki_rounding_mismatch_review.py / run_sekki_rounding_pattern_probe.py | 診断CSV書出しがあるため通常回帰には含めない |
| P/D直下meishiki_validation.py | 正式回帰には不採用。仮データ・旧2020年06:03立春が残る。修正しない |
| 一時監査S/W比較 | 任意Bとして再構成。14関数1325入力 |
| D/Pサービス7条件比較 | 継続テストには不採用。Dは凍結されるためW限定観測と任意S比較を優先 |
| 前回70Python構文解析・131ファイルhash | 手法を再利用。今回は現在の対象を列挙し直す |

CSV評価:

- sekki_correction_reference_template.csv 156行、backup版144行: 過去の参照整理。全行を最新の訂正済み正式値とはみなさない。
- sekki_correction_input_2020_2022.csv 36行: 入力バッチ参照。採用方式の正式回帰に直接使用しない。
- sekki_base_eacal_representative.csv 144行: EACal観測データ。独立した万年暦正解ではない。
- taizan_sekki_reference_template.csv 144行: 旧テンプレート。全行を承認済み期待値と認定しない。
- sekki_rounding_pattern_report.csv 36行、sekki_rounding_timeline_comparison.csv 36行、sekki_rounding_mismatch_review.csv 9行: 過去比較の出力のみ。
- いずれも変更・移動・再生成しない。今回48件は訂正済み検証コードを出典とする。

## 失敗した場合

1. AのFAIL、BのREVIEW、環境エラーを区別。本体修正やfixture更新を先に行わない。
2. case IDから出典・入力を確認する。
3. 旧資料、採用方式変更、未確定仕様、真の回帰を切り分ける。
4. Aの期待値変更には確定根拠が必要。Bは変更理由と人の判断を残して更新する。
5. Cは課題が消えた場合も原因を確認し、旧挙動に戻さない。

自動snapshot更新機能はありません。
Git add/commit/push、依存追加、アプリ起動停止、VPS操作はこのテストの責務に含めません。

## K07修正済み回帰（2026-09-11）

根拠：ユーザー指示「回帰テスト基盤の正式保存 → 節入り108件監査 → K07最小修正」第12〜16節。
実装・テスト：fortune_service.py、tests/specific_datetime_guard.py。

- 既存Tier A 227件とformal.jsonは変更なし。OFF非干渉6件を追加し、合計233件。
- A-K07-off-normal / invalid-date / invalid-format / empty / four-candidates：通常鑑定の全返却値を候補なしの場合と比較。サービスと実FastAPIの両方で、候補解析・特定日時計算の未呼出しを確認。
- A-K07-off-no-access：OFF時は候補キーを読み出さないことを確認。
- 既存Tier B 35件を維持。ON正常（1件・4件）とON不正の観測2件を追加し、通常観測37件。
- ON不正日付のValueErrorとAPI HTTP 500は従来観測を維持。エラー設計やK02の上限は今回変更しない。
- 特定日時の占術結果そのものはTier Aへ昇格しない。
- K07は解決済みとして表示し、未解決Tier CはK01〜K06の6項目。OFF回帰はTier AのFAILとして停止対象になる。
- 追加したOFFテスト6件は修正前の本体で失敗し、旧挙動を検出できることを確認した。
