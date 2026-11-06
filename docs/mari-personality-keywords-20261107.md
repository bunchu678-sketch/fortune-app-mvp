# 無津呂麻理先生版：通変星・蔵干通変星の正式キーワード登録

2026-11-07。直前の十二運星サイズ修正は完了済みで、開始branch `mari-star-size-20261106` / HEAD `026a7c68874fa6a710952e511fbcb8922baa5082` をローカル/GitHubで照合しcleanを確認した。新branch `mari-personality-keywords-20261107` / worktree `outputs/mari-personality-keywords-20261107/worktree` で実装。PC20px/スマホ18pxの最新星名字サイズを取り込んだ。

共通AGENTS v1.3・プロジェクトAGENTS・WORKSPACE_RULES・最新引継ぎを確認。今回の本人確定表と「通変星・蔵干通変星で同じkeywordsを使う」を実装基準にした。NotionのW正本/保全原則はこのチャットで有効・本人確認済みを参照済み、今回の書込みなし。規約の未解決競合なし。

## 登録内容と出典

出典は本人提示「Diviner Romari 四柱推命鑑定士：中級編」38～41ページ。今回の本人確定表を原文として、表記・語順・区切り・語数を変更せず転記した。説明文章からの抽出/要約/別用途の転用はしていない。

| 星 | 正式キーワード |
|---|---|
| 比肩 | 自我心・頑固・独立・努力家 |
| 劫財 | 協調・社交性・対等・政治力 |
| 食神 | 趣味・自然体・味覚・平和 |
| 傷官 | 神経質・孤独・感受性・芸術 |
| 偏財 | 愛情・現実主義・回転財・奉仕 |
| 正財 | 温厚・堅実・蓄財・常識・不動産 |
| 偏官 | 行動力・責任感・正直・動乱 |
| 正官 | 自尊心・几帳面・自制心・地位名誉 |
| 偏印 | 革新・創造・爆発・自由 |
| 印綬 | 知恵・学問・論理性・母性愛 |

## 単一辞書と共通参照

先生版専用の `fortune-next-app/app/mari-personality-keywords.ts` に `MARI_PERSONALITY_KEYWORDS` を1つだけ置いた。Object.freezeした10種類の表を `mariPersonalityKeywords(star)` が完全一致で参照する。既存のcomments.py/正式計算辞書/説明文章/大運/月運辞書には書き込まない。

main-fortuneの `MariPersonalityStar` は、星名spanと、この同じ関数から得たkeyword段落を描画する。通変星・蔵干通変星の両方が同じcomponent/辞書を使う。各柱の元の `personalityPillars(starData)` の星名取得は無変更。月柱だけの解釈や組合せ解釈はない。

「－」「不明」「未入力」、未登録名、prototype等の非登録プロパティにはundefinedを返し、keyword段落を描かない。日柱通変星の「－」、未知の時柱を推測して星名やkeywordで埋めない。

## 4柱の表示

カードは柱名→通変星名→そのkeywords→蔵干通変星名→そのkeywordsの順。PC左から時/日/月/年、スマホ上段時/日・下段月/年を維持した。日柱の「－」の下にはkeywordなし。未知の時柱も両欄ともkeywordなし。

keywordは既存の.keyword classを使用し、PC18px/スマホ17px・var(--accent)を継承する。星名は20/18px。keyword段落だけfont-weight400へ整えて、親の星名用太字を継承しないようにした。共通サイズ変数/他の文字サイズ/グループ色/十二運星の整列・2行領域・スマホ2×2は一切変更していない。

合成例1988-08-12/09:00/東京都/男性では、時柱：比肩/劫財、日柱：－/劫財、月柱：傷官/劫財、年柱：劫財/偏官にそれぞれの正式keywordが付く。元の命式表と各柱の星名を照合し、2種類の星が同じ場合の共通参照もNode試験で確認した。

## 検証

| 検証 | 今回の結果 |
|---|---|
| Node | 89/89、失敗/skip0。新規3件で10種完全一致、非登録値の非表示、同星の共通参照を確認 |
| Python関連 | unique267件、失敗/エラー/skip0 |
| 計算回帰 | Tier A556/556、Tier B38/38一致、既知C6維持。試験中のsource変更0 |
| TypeScript | --noEmit --incremental false 成功 |
| production build | Next16.4.5で成功、依存lock/版の変更なし |
| Chrome本体 | 最終446/446、pageerror0 |
| 新入口 | 別の5項目成功。保留解消案内、スマホ画像、実ボタン→通常認証→入力 |
| 画像 | 52枚保存。標準PC1440/スマホ320pxの正式keywordsを目視確認 |

Chromeでは全4柱の通変星/蔵干星名とkeywordを独立した本人確定表と照合。4テーマ×1440/390/320pxで原文一致・共通字サイズ・accent・font-weight400・全文の横はみ出しなしを確認。その他の320/360/430/700/701px、PC4列/スマホ2×2、十二運星名と主要星名20/18px、色/割合/5分類/大運等も維持した。

旧13466の同入力APIと、命式/星データ/五行/性格/大運/月運/年間総合/特定日時の計算・辞書結果10sectionが完全一致。追加は先生フロント表示データなので、APIの既存結果へkeywordを混ぜていない。認証/テーマ保存/SSR/旧機能停止の既存試験も維持。

博士版は従来の説明/人生段階/帳票/図/字サイズ/星名を維持し、.personalityKeywordが存在しないことを確認。新しいcommon辞書/描画componentは先生用compact分岐だけで使う。組織版のファイルへ書込みなし。

本体最初の446件成功後、確認入口に残っていた過去の「正式な定義待ち」文言を削除して今回のレビュー環境だけを再起動した。最終446件はその後の完走結果で、再実行を加算しない。以前の受入環境は保全する。Pythonのstorage/PDF拒否等のログは異常系試験の出力を含み、最終失敗/エラー件数と区別。実機Excel COM/Linux/本番ログイン・実DBは今回試験していない。

## 変更ファイルとGit

- 新規 `fortune-next-app/app/mari-personality-keywords.ts`：本人確定表と共通lookup。
- 変更 `fortune-next-app/app/main-fortune.tsx`：先生用の共通星名/keyword componentを両欄から呼ぶ。
- 変更 `fortune-next-app/app/teacher-theme.css`：新しいkeyword段落の字重400のみ。既存CSSはそれ以外完全一致。
- 新規 `tests/mari_personality_keywords.test.mjs`：本人確定表の照合・未知状態・両欄共通参照。
- 新規 `docs/mari-personality-keywords-20261107.md`：本報告。

開発元のresearch/run_mari_keywords_{fixture,checks,review,entry}_20261107.*、詳細メモ、outputs内のログ/画像/verification-summary/preservationに検証結果を保存し、handoffを更新する。正式計算/辞書/説明/認証/API/DB/契約/帳票/復元/依存は無変更。4柱取得とThinkingBars本体も一致した。

専用branch `mari-personality-keywords-20261107` へcommit・通常pushする。終了時HEAD/GitHub一致/cleanと旧worktree保全は同outputsのgit-final.jsonと詳細メモ/引継ぎに記録。main統合・force push・reset・既存branch切替・本番配備・本番DB変更なし。

## 本人受入・保留事項

新入口 **http://127.0.0.1:13476/**（入力/結果13475、API18935、博士比較13478）。①の合成アカウントで通常認証して入力へ進む。パスワード不要。旧13466は直前のUI版。本人確認用には1988-08-12/09:00/東京都/男性、時刻不明も確認可能。画像はlatest.jsonのsession内 `screenshots/keywords-default-1440.png` / `keywords-default-320.png` 等。実情報・本番VPS・実メールは使用しない。

**「通変星・蔵干通変星の性格キーワード10種類は正式定義待ち」という保留事項は、本人確定表の登録と共通表示により解消済み。** 最新の引継ぎも解消済みに更新する。登録を含む今回の画面は本人最終受入待ち。本番適用は別の明示指示を要する。
