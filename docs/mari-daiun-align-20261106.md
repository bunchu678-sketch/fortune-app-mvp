# 無津呂麻理先生版：十二運星の整列・大運表示改善

2026-11-06本人受入追加指示への対応。開始branch `mari-ui-pillars-20261106` / HEAD `3e6a7161def665348fb054e8399a21f36cbddcbe` をローカル/GitHubで照合し、cleanを確認。元publicはphase10の578b429のまま保全。新branch `mari-daiun-align-20261106`、worktreeは開発元 `outputs/mari-daiun-align-20261106/worktree`。

共通AGENTS v1.3を最上位として、プロジェクトAGENTS・WORKSPACE_RULES・最新handoffを確認した。今回の明示指示は、前回の「大運の文字サイズ・配置を保つ」を更新する指示として適用。これ以外の規約の未解決競合はない。NotionのW正本/不要な別バックアップを作らない有効・本人確認済み原則はこのチャットで参照済み。今回のNotion書込みなし。

## 1–2. 十二運星4カードの整列

`teacher-theme.css` の `.pillarMeaning` に `min-block-size: 3em; flex-shrink: 0` を設定した。line-height1.5なので、説明文が1行でも2行分を確保する。本文の文字サイズ、説明文章、4柱順、分類色、割合、keywordsは変更していない。領域を固定高で切り取ったり、ellipsisで説明を省略したりしていない。

Chrome実測ではPC1440pxで月柱の「初対面の人と会った時の自分」が2行、他3柱は1行。4枚とも説明領域51px、カード上端を基準に柱名12px、説明文48px、星名106px、割合149.390625px、keyword183.390625pxで一致した。4テーマそれぞれで、全5要素の開始位置を0.5px未満の許容範囲で照合した。説明領域をそろえる以外の過剰な余白を追加していない。

右から年・月・日・時（左から時・日・月・年）、星名のグループ色と割合バーの分類/重み/パステル、考え方5分類は維持。スマホ320pxでも星名・割合の位置がそろい、既存の年柱側からの横スクロールを維持した。補助確認では1024/768/701pxでも星名の高さが一致した。

## 3. 大運・接木運の文字

先生の `#daiun` だけを対象に、PC本文・周期・keyword・年齢/対象年・接木運の本文を18px、主要干支/星名/大運番号/接木運見出しを20px、セクション見出しを24pxにした。スマホ700px以下は本文16px、主要項目18px、セクション見出し22px。既存の基本情報・命式表・日干・通変星カード・月運等の文字サイズは変えていない。

大運の縦の一覧構造は維持し、5列×2行への変更はない。1440pxでカードが必要以上に縦長にならないこと（各通常カード160px未満）と、320pxで文字が小さくならずはみ出さないことを確認した。接木運は見出し、表示年齢、地支の矢印、季節の移行を残し、通常の本文色で表示する。

## 4. 大運の周期・keyword配置

先生用のcompact分岐だけを変更した。

- 見出し行：大運番号、空亡（該当時）、干支/通変星/十二運星、周期 / keyword。
- 次の行：開始～終了年齢 / 目安開始～終了年。

周期・keywordは既存の同じ文字列をそのまま使用し、内容の追加・編集・分割解釈をしていない。見出し行は既存のflex-wrapで、広い画面では横に、狭い画面では自然に折り返す。文字を重ねたり、縮小して押し込んだりしない。空亡の表示判定と接木運の挿入位置は従来どおり。

## 5. 4テーマの色

周期とkeywordを同じ `.flowKeyword` spanへまとめ、既存の `var(--accent)` を使用。標準#806018、赤#ad2837、青#245ba8、ブラック#e2be75。各テーマで、表示中の全大運の周期/keyword色がaccentに一致し、干支/星名/年齢等はaccentに変わらないことをブラウザーで確認した。接木運全体をkeyword色にはしていない。

十二運星名は前回の分類色を維持。全4テーマで分類と実文字色を照合し、背景とのcontrast4.5以上を維持した。

## 6. PC・スマホ画像

画像34枚を、開発元 `outputs/mari-daiun-align-20261106/latest.json` のsessionに保存した。各テーマの十二運星PC/320px、大運PC/320pxを含む。標準/ブラックの実画像を目視し、カード整列、周期・keywordの見出し配置、可読性を確認した。画像に実利用者データはなく、認証バーはマスクする。

主な画像は `screenshots/juuni-default-desktop.png`、`juuni-default-mobile.png`、`daiun-default-desktop.png`、`daiun-default-mobile.png`、`daiun-black-desktop.png`。受入入口にもPC/スマホのリンクを表示する。

## 7. 試験

Python関連は重複を除く267件すべて成功。失敗0・エラー0・skip0（auth/admin/product/teacher/history/report/k01等10suite）。実行ログとID一覧はpython.log / python-summary.json。

| 検証 | 今回の結果 |
|---|---|
| Node | 86/86、失敗/skip0 |
| TypeScript | --noEmit --incremental false 成功 |
| Next production build | 16.4.5で成功。依存lockの版変更なし |
| 計算回帰 | Tier A556/556、Tier B38/38一致、既知C6を維持。source変更0 |
| Chrome本体 | 188/188、pageerror0 |
| 受入入口と補助幅 | 13項目成功。新helper実ボタン、入力、横スクロール、1024/768/701pxの整列を含む |
| 保全 | 他のtrackedファイルに差分なし、main-fortuneの大運以外は末尾改行をそろえて完全一致 |

Chromeでは前回13426の実ボタンから通常認証し、同じ入力/鑑定日で得た新旧APIのdaiun全体が完全一致することを確認した。大運件数/順番/年齢/年/干支/通変星/十二運星/周期/keyword/空亡/接木運の元データを変更していない。対象外のbasic/meishiki/nikkan/tsuhensei/thinking/yearly/overallについても、表示文字列と主要要素の文字サイズ/色を新旧比較して一致した。

Pythonの異常系試験では意図的な認証storageエラー/PDF拒否等のログが出るが、最終の失敗/エラー件数と混同しない。実機Excel COMのPDF出力、Linux、本番の実ログイン/実DB試験は今回行っていない。

## 8. 博士版・組織版と安全境界

博士版は先生テーマを持たず、従来の大運字サイズ16px、旧markup（flowKeywordなし）を維持。従来の人生段階カード/説明文章/帳票ボタン/命式字サイズ/五行図10円もChromeで確認した。変更は新worktree内の先生用分岐と先生限定CSSだけで、組織版へファイル書込みをしていない。

正式計算・辞書・認証・API・テーマ保存・履歴停止・帳票停止・旧URL遮断・DB・復元コード・依存lockは無変更。Chromeでログイン直行/ログアウトと戻る/利用者分離/4テーマSSR/旧URL遮断/旧API非呼出を検証。Pythonの既存teacher19ケースを含む関連回帰も実行した。実情報・本番/VPS・実メールを使用していない。

## 9. 変更ファイル・Git

既存コードの変更は次の2つだけ。

- `fortune-next-app/app/main-fortune.tsx`：先生用大運の周期/keywordをflowHeadingへ移し、flowDetailsを年齢/対象年に整理。
- `fortune-next-app/app/teacher-theme.css`：説明文2行分の領域、先生用大運/接木運の文字サイズ。

新規文書は `docs/mari-daiun-align-20261106.md`。開発元には `research/run_mari_daiun_{fixture,checks,review,entry}_20261106.*` と検証ログ/画像/詳細メモを保存し、handoffを更新する。差分/保全証跡は `outputs/mari-daiun-align-20261106/preservation.json`。

専用branch `mari-daiun-align-20261106`。終了時のcommit/HEAD、GitHubとの一致、cleanと既存worktreeの保全を同outputsの `git-final.json` と開発元の詳細メモ/引継ぎに記録する。main統合・force push・既存branch切替・reset・本番配備は行わない。

## 10. 本人受入

**http://127.0.0.1:13436/**。①のボタンから合成アカウントの通常認証を通り、直接入力を開く。パスワード入力不要。今回のアプリ13435/API18895、博士比較13438。前回13426とそれ以前の確認環境は保全する。

入力例1988-08-12/09:00/東京都/男性、鑑定日2026-11-06。4テーマで十二運星名の横並び、大運の字サイズ、見出し横の周期/keyword、スマホの折返しを本人が確認できる状態にする。今回の残件は本人による画面受入。通変星/蔵干通変星の性格keyword10種類は前回どおり正式定義待ちで、今回作成/抽出/転用していない。本番適用は別の明示指示を要する。
