# 無津呂麻理先生版：十二運星名の共通サイズ化・最終UI調整

2026-11-06の最終UI指示に対応。最終確認日：2026-11-07 JST。開始branch `mari-typography-20261106` / HEAD `b555e020e47cff24acbae04a387f30173cd1fc2b` をローカル/GitHubで照合し、既存cleanを確認。新branch `mari-star-size-20261106` / 新worktree `outputs/mari-star-size-20261106/worktree` で実装した。

共通AGENTS v1.3・プロジェクトAGENTS・WORKSPACE_RULES・最新引継ぎを確認。今回の「十二運星も主要情報と同じサイズ」を、前回28px例外より優先した。規約の未解決競合なし。Notionの有効なW正本/保全原則はこのチャットで参照済み。今回のNotion書込み・共通規約変更なし。

## 修正前後

| 表示 | 変更前 | 変更後 |
|---|---:|---:|
| 十二運星名・PC | 28px | 20px |
| 十二運星名・700px以下 | 28px | 18px |
| 通変星・蔵干通変星名・PC | 20px | 20px（維持） |
| 通変星・蔵干通変星名・スマホ | 18px | 18px（維持） |

`fortune-next-app/app/teacher-theme.css` の `--reading-star:1.75rem` を削除し、pillarStarのfont-sizeを `var(--reading-major)` へ変更した。主要情報用の既存変数はPC1.25rem/スマホ1.125remのままで、別の箇所のサイズは再調整していない。CSS差分はこの2か所だけであることを、開始版からの期待置換との完全一致で確認した。

## 表示と検証

- TypeScript --noEmit --incremental false 成功。
- Next16.4.5 production build 成功。依存lock・版の変更なし。
- Chrome400/400、pageerror0。4テーマの1440/390/320pxでcomputed font-sizeを取得し、全十二運星名と通変星/蔵干通変星名の値がPC20/スマホ18で一致することを検証。
- 320/360/390/430/700/701pxも含め、スマホ2×2・横スクロールなし、PC横4列、説明文2行分の領域、星名/割合等の整列、グループ色/正式分類/keyword色を維持。
- その他の共通文字サイズ、命式22/20px・基本情報20/17pxの例外、大運の十二運星非表示、通変星→蔵干の上下順、日干文章を維持。
- 博士版の十二運星見出しは従来16px・既存星名の文字列を維持し、先生用CSSが適用されないことを確認。従来の大運/帳票/説明/人生段階/図/字サイズも検証。組織版にファイル書込みなし。
- 認証/旧URL・旧API停止/利用者分離/テーマ保存とSSRも既存ブラウザー回帰で確認。APIの計算/辞書結果10sectionが旧版13456と同入力で一致。
- 保存画像40枚。標準のPC1440とスマホ320pxを目視し、星名が共通サイズにそろい、整列と可読性を維持することを確認。

受入入口の実ボタン→通常認証→入力表示も別の2項目で確認した。

CSSのみの限定変更のため、Node単体・Python関連・計算回帰は今回再実行せず、前回の86/267/556+38を今回の成功件数へ加算しない。計算/辞書/認証/API/復元コード/依存を含め、他のtrackedコードが全て未変更であることはGitで照合した。証跡は同outputsのpreservation.json、typography-*.json、各ログに保存。

## 変更ファイル・Git

コード変更は `fortune-next-app/app/teacher-theme.css` のみ。新規文書 `docs/mari-star-size-20261106.md`。開発元に `research/run_mari_star_size_{fixture,review,entry}_20261106.*`、詳細メモ、outputs内のログ/画像を保存しhandoffを更新する。元の計算・辞書・データ・認証・DB・他版のsource・過去報告を改変していない。

専用branch `mari-star-size-20261106` へcommit・通常pushし、終了時HEAD/GitHub一致/cleanと旧worktree保全は同outputsのgit-final.jsonと開発元詳細メモ/引継ぎに記録する。main統合・force push・reset・既存branch切替・本番配備・本番DB変更なし。

## 本人受入

新しい入口 **http://127.0.0.1:13466/**（アプリ13465/API18925、博士比較13468）。①で合成アカウントの通常認証を通り、入力へ進む。パスワード不要。旧13456は前回版として維持。画像はlatest.jsonのsession内、`screenshots/type-default-1440-juuni.png` / `type-default-320-juuni.png` 等。実情報・本番・実メールは使用しない。

**UI改修は本人最終受入待ち、性格キーワードは正式定義待ち。** 通変星・蔵干通変星10種類の性格keywordsを作成・抽出・補完・転用していない。本人最終受入前に「全UI受入済み」とはしない。
