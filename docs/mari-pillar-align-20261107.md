# 無津呂麻理先生版：通変星・蔵干通変星4柱カード整列

2026-11-07。開始branch `mari-personality-keywords-20261107` / HEAD `1bd086388b9567cca47e282230379f0e5b332b8c` をローカル/GitHubで照合しcleanを確認。新branch `mari-pillar-align-20261107` / 新worktree `outputs/mari-pillar-align-20261107/worktree` でCSSだけを修正した。

共通AGENTS v1.3、プロジェクトAGENTS、WORKSPACE_RULES、最新引継ぎを参照。NotionのW正本/保全原則はこのチャットで有効・本人確認済みを確認済み。今回のNotion書込み/共通規約変更なし。規約の未解決競合なし。

## 1. 原因

以前は各カードのdl/dt/ddが独立した通常の縦フローで、dd内のkeyword段落の行数に応じて高さが変わった。その結果、上段が2行/3行になったカードでは下段ラベルが下がり、日柱「－」などでkeyword段落のないカードでは下段が上へ詰まった。カード外枠の高さだけをそろえても、内部の対応位置は一致しない構造だった。

## 2. 採用構造

既存の星名取得、共通lookup/component、dl/dt/ddのHTMLは一切変更せず、先生用.personalityPillarsだけをCSS Gridのsubgridにした。カードを7つの内容に応じた共有行へ配置する。

1. 柱名
2. 通変星ラベル
3. 通変星名
4. 通変星keyword領域
5. 蔵干通変星ラベル
6. 蔵干通変星名
7. 蔵干通変星keyword領域

dlは後半6行、各ddは星名/keywordの2行を共有する。上段3行と下段3行の2領域が、各段で最も高い内容へ自動でそろう。段落のmarginを整理し、星名/keywordの行を明示した。ピクセル固定高や文字数ごとの条件分岐は使っていない。

PCでは4カードが7行の高さを共有。スマホでは上段2カードと下段2カードが、それぞれ独立して7行を共有する。長いkeywordを省略/縮小せず、幅に応じて全文を自然に折り返す。「－」「不明」のkeyword段落を新しく埋めず、他カードと共有する空のgrid行で下段位置を保つ。両カードともkeywordがない段では行が内容に応じて縮むため、不必要な固定空白を作らない。

## 3–5. 整列結果と状態別確認

Chromeで各項目のgetBoundingClientRect()を取得。320/390/430/700/701/1440px × 4テーマで、実際の鑑定表示と、正式語句の長短・欠落を混在させた描画専用ケースを確認した。後者は元カードを一時的にcloneして正式表の語句/「－」「不明」を与えたレイアウト試験であり、実際の鑑定計算・辞書・アプリ状態は変更しない。

| 測定 | 結果 |
|---|---:|
| レイアウトケース | 75 |
| 比較した同じ段の組数 | 125 |
| 対応項目の上端/カード高さの最大差 | 0px |
| 実keyword上端と共有keyword行上端の最大差 | 0.0px |
| 合格基準 | 1px以内 |

柱名、両ラベル、両星名、両keyword領域と、同じ段のカード外枠の高さが一致した。keyword段落のない状態は空の共有行の開始位置を星名要素/実際のgrid gapから求め、存在する段落の上端とも照合。実際の出生時刻不明でもPC1440/スマホ390/320pxで確認した。

PCは左から時/日/月/年の横4列、スマホは上段時/日・下段月/年の2×2を維持。長い正官/正財等の語句と、短い食神等を含み、全文/字サイズ/色/横はみ出しなしを確認した。

## 6. 関連試験・保全

- TypeScript --noEmit --incremental false 成功。
- Next16.4.5 production build 成功。固定依存lock/版は無変更。
- Node89/89、失敗/skip0。正式10種の完全一致、未知状態の非表示、同星の両用を維持。
- Chrome1597/1597、pageerror0。整列測定に加え、4テーマのaccent、星名20/18px・keyword18/17px、原文と対応、十二運星の整列/配色/スマホ2×2、大運/月運、認証/旧機能停止等も確認。
- 新入口の実ボタン/案内/スマホ画像は別の5項目成功。
- 保存画像68枚。標準PC1440、スマホ320、長いkeywordと欠落を混ぜた320pxケースを目視確認した。
- 正式計算/API/辞書/取得関数/表示component/文字サイズ変数/色/他セクションのsourceは無変更。旧13476の同入力APIとの結果一致も確認。
- 博士版は先生CSSが適用されず、従来の説明/帳票/図/字サイズ/星名を維持。組織版へのファイル書込みなし。

CSSのみの修正のため、Python267件と計算回帰556/38件は今回再実行していない。前回の成功を今回の件数へ混ぜず、該当コードの無変更をGit差分で確認した。実機Excel COM/Linux/本番ログイン・実DBは今回試験していない。

## 7. 変更ファイル・Git

コード変更は `fortune-next-app/app/teacher-theme.css` のpersonalityPillarsレイアウト部分だけ。`main-fortune.tsx` と `mari-personality-keywords.ts` は未変更で、正式語句/共通辞書/参照元/順序を保持する。新規文書 `docs/mari-pillar-align-20261107.md`。

開発元に `research/run_mari_pillar_align_{fixture,review,entry}_20261107.*`、詳細メモ、outputsのverification-summary/preservation/alignment-summary、session内pillar-alignment.json/画像/ログを保存し、handoffを更新。専用branch `mari-pillar-align-20261107` へcommit・通常pushし、最終HEAD/GitHub一致/clean/旧版保全をgit-final.jsonと詳細メモ/引継ぎへ記録する。main統合・force push・reset・既存branch切替・本番配備なし。

## 8. 本人受入

新入口 **http://127.0.0.1:13486/**（アプリ13485/API18945、博士比較13488）。①の合成アカウントで通常認証し、パスワード不要で入力へ進む。旧13476は前回版として維持。入力例1988-08-12/09:00/東京都/男性、時刻不明も確認可能。画像はlatest.jsonのsession内 `screenshots/aligned-default-1440.png` / `aligned-default-320.png` 等。

**正式キーワードの定義待ちは解消済み。整列修正を含む先生版UIは本人最終受入待ち。** 実情報・本番VPS・本番DB・実メールを使用していない。本番適用は別の明示指示を要する。
