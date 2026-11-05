# 無津呂麻理先生版：鑑定専用化・UI・セキュリティ更新

2026-11-05の総合改修指示書に対応。最終確認日：2026-11-06 JST。本番配備は未実施。本人による今回の最終受入は未実施。

## A. 全体概要と開始状態

実装・隔離環境での検証・本人確認用環境の準備を完了した。先生版を「ログイン → 基本情報入力 → 鑑定結果」に整理し、履歴・帳票・マイページ・先生/生徒管理を先生版のWeb/APIで停止した。既存データを物理削除していない。

正規Git：`C:/Users/bunch/Documents/Codex/fortune-app-public`。指定された `mari-presentation-20261105` の `f5000950fec2c74fbedbe4a2a73b4134e560b34a` をローカル/GitHubで照合し、cleanを確認した。元public checkoutは引き続きPhase10の `578b429` であり、今回の正本へ読み替えなかった。

新規branch：`mari-reading-only-20261105`。新規worktree：開発元 `outputs/mari-reading-only-20261105/worktree`。既存branch/worktree、前回の受入環境13406番、博士版、組織版を上書きしていない。

確認した規約は共通AGENTS v1.3、親WORKSPACE_RULES、プロジェクトAGENTS。Notionでは有効/本人確認済みのW正本原則とGitで戻れる変更の保全原則を確認した。今回の明示指示を前回の多機能仕様より優先し、未解決の規約競合はない。Notionの書込み・schema変更は行っていない。

## B. 新しい画面と認証

- ログイン後は `/` の基本情報入力へ直接移動する。旧管理画面をnext URLに指定しても経由しない。
- 結果の「入力に戻る」は入力を保ち、「新しく鑑定する」は次の入力を開始する。
- ログアウトとテーマ切替は残した。マイページ・履歴・帳票・管理への操作部品と未保存状態の表示を取り除いた。
- 旧 `/history`、`/member`、`/mypage`、`/teacher`、`/b2b`、`/operations`、`/product` の直接アクセスも入力へ戻る。未認証ならログインへ進む。
- 全員が同じ鑑定画面を使う。既存DBのteacher/student役割、先生の協働契約と生徒の利用契約の違いを一括変更していない。現在の認証・契約判定は既存 `OperationsRepository.member_access` を利用する。
- 運営者の発行・停止・招待経路は独立した既存adminプロセスに保全する。一般利用者に運営権限を付けない。

適用先はAPIの既存 `FORTUNE_DEPLOYMENT_SURFACE=teacher` とWebの新規 `FORTUNE_UI_SURFACE=teacher` で分離する。Webの `FORTUNE_API_ORIGIN` は対応する先生APIへ固定する。利用する教室はサーバー設定のslug（標準 `mari-mutsuro`）と本人の既存所属から決め、リクエストのowner/organization/roleで変更させない。複数所属でも配備先の教室を使い、管理画面へ分岐しない。

先生Webを旧combined APIへ誤接続した場合は接続設定エラーとして止める。博士版とadminは先生用の境界を有効にせず従来経路を使う。これらの本番設定は今回変更していない。

## C. 履歴・帳票の停止と保全

先生APIは `/api/auth/*`、`GET /api/reading/bootstrap`、`POST /api/reading/fortune`、`POST /api/reading/theme` だけを許可する。履歴の取得/保存/候補検索/再鑑定/復旧、Excel/PDF、出力可否、account summary、b2b管理、operations、旧汎用鑑定APIを直接呼んでも404/no-storeになる。

新しい鑑定APIは実セッション・利用権・CSRFを確認し、既存の計算関数を呼ぶ。計算中の失効を防ぐため、結果を返す前にも認可を確認する。履歴、成功回数用の入力fingerprint、出力tokenを新しく作らない。正常な鑑定の前後で合成DBの全テーブルが同一であることを検証した。

入力・結果は鑑定中のReactメモリ内だけに持ち、localStorage/sessionStorage/IndexedDBへ新しく保存しない。ログアウトや利用者変更時の既存状態破棄を維持した。サーバーのエラーに氏名・生年月日・命式等を出力しない。専用bootstrap/themeのレスポンスも表示名・配色・選択テーマ・割合表示設定だけに限定し、役割・管理用設定・回数等を返さない。

既存履歴表・snapshot・帳票テンプレート・整形/変換/認可コード・関連試験は保全した。停止は古い個人情報やバックアップを消したという意味ではない。物理削除、保存期限、既存の削除ジョブ、バックアップ内のコピーの扱いは別の判断として残す。今回これらの本番設定には接続していない。

復元対象・API・ファイル・DB・試験・復元時の注意は [復元手順](reading-only-restoration-20261105.md) に記録した。現在のAPIを有効にする隠し機能はない。

## D. UI修正8件

| 指摘 | 実装・確認 |
|---|---|
| 1. 初期テーマのちらつき | ブラウザー取得後に色を変える方式から、サーバーで本人の保存テーマを取得して初回HTMLへCSS変数を設定する方式へ変更。匿名は白/黒/金。4テーマすべてでJavaScriptを無効にしても正しい色と実際の入力欄が表示されることを確認。覆い隠すCSSは使っていない |
| 2. 五行図の灰色の輪 | 裏側の半径可変円が表側の円を超えた部分だった。先生版だけ装飾円を描かず、数値・関係線・正式計算を保持。先生は各図5円、博士版は従来の10円を確認 |
| 3. キーワードの余白 | 先生版のカードpadding、段落間隔、不要な最低高さを整理。文字はおおむね15～16px以上で維持 |
| 4. 人生4時期 | 既存の幼年期/青年期/成熟期/老年期と元データの年齢範囲を使って2列×2行。既存の「社会に見せている自分」「本来の自分」「本来の自分らしさ」を維持。独立した正式keywordsのない通変星に新語を追加していない |
| 5. 十二運星 | 右から年→月→日→時。柱名・既存見出し・星名・割合・keywordsを縦に整理。スマホは文字を縮めず、年柱側から横スクロール |
| 6. 3グループ色 | 地球 `#a9cbed`、月 `#f4df8c`、太陽 `#edaeaa` のパステル調。構造・分類・計算ファイルを変更せず、年15/月30/日50/時5、時刻不明の未算入5%を維持 |
| 7. 大運 | 名称・干支・通変星・十二運星を上段、年齢/年・周期・既存keywordsを下段へ。PCでは通常2行で、スマホは折返し。空亡・接木運の情報を残す |
| 8. 今年の流れ | 月名・干支・星・keywordsと対象期間をコンパクトに整理。日時・順番・計算結果を保持。「今年一年の総合運勢」は削除していない |

`ThinkingBars()` の関数本体と5分類、正式な3グループ分類/重み、日干・十二運星のkeywordsデータは不変。元の基本情報入力・出生時刻不明・利用者分離・博士版の表示を、今回の構造変更に必要な範囲で維持した。

PC1440pxとスマホ320pxで4テーマを確認し、画面全体の横はみ出しがないことを検証した。十二運星の横スクロールは意図した表示。画像は開発元 `outputs/mari-reading-only-20261105/latest.json` が示すセッションの `screenshots/` に保存する。4テーマのPC/スマホ、2×2・柱・月運のスマホ、大運のPCを含む12枚を保存し、主要画像を目視確認した。Gitには画像や合成DBを含めない。

## E. セキュリティ・依存更新

| 部品 | 更新前 | 更新後 | 理由 |
|---|---|---|---|
| Next.js | 16.4.2 | 16.4.5 | 11/03の公式セキュリティリリース |
| pnpm | 11.7.0 | 11.11.0 | OSVで検出されたインストール時のパス/リンク等の問題。11系を維持 |
| certifi | 2026.6.17 | 2026.10.18 | 侵害された中間CAに関係するルート証明書の問題 |
| GitPython | 3.1.51 | 3.2.1 | 信頼できないrepository/config/checkout等を扱う経路の複数問題 |
| Pillow | 12.3.0 | 13.0.0 | 画像/PDF等のデコーダー・パーサーの資源消費等の問題 |
| urllib3 | 2.7.0 | 2.8.0 | HTTPS proxy TLS、圧縮/チャンク処理等の問題 |
| pip | 25.0.1 | 26.2 | インストール時のアーカイブ展開・パス等の問題 |
| Streamlit | 1.59.2 | 1.66.1 | Pillow 13に必要な依存互換性。新しい公式依存条件はPillow<14を許容 |
| React/React DOM | 19.3.1 | 維持 | 今回取得した監査で該当なし |
| Node.js | 24.22.1 | 維持 | 既に10/21修正を含む24系LTS。メジャー更新しない |

Next/pnpmの版をpackage.jsonへ正確に固定し、pnpm-lock.yamlを整合させた。Pythonは元の環境へ上書きせず、新規venvに `requirements-reading.lock` の66配布を固定導入した。変更は上表のPython6配布だけで、計算に関係する既存のeacal/ephem/pytz/jdcal/numpy等の版は維持。元public Pythonの66配布が更新前と完全一致することも確認した。元の `requirements.txt` は変更していない。先生版の将来の環境構築には新しいlockを使用する。

pnpm配布物は公式npmメタデータのSHA-512と照合してから専用領域へ展開した。既存Node/pnpmのグローバル設定や他プロジェクト環境は更新していない。

### Next.jsの公式情報と適用条件

[公式16.4.5リリース](https://github.com/vercel/next.js/releases/tag/v16.4.5) が挙げる7件を確認した。

| 公式アドバイザリー | 現構成との関係 |
|---|---|
| [GHSA-mfr8-8qww-v76h](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h) | `use cache` と `unstable_cache` の組合せを使っていない |
| [GHSA-vc7v-qv4w-wrv8](https://github.com/vercel/next.js/security/advisories/GHSA-vc7v-qv4w-wrv8) | Cache Componentsや入れ子の `use cache` を使っていない |
| [GHSA-vvgp-ww4w-46vf](https://github.com/vercel/next.js/security/advisories/GHSA-vvgp-ww4w-46vf) | Cache Componentsを有効化していない |
| [GHSA-rhh4-g77r-r9qj](https://github.com/vercel/next.js/security/advisories/GHSA-rhh4-g77r-r9qj) | binary引数を渡す `use cache` がない |
| [GHSA-pc58-hwjq-p385](https://github.com/vercel/next.js/security/advisories/GHSA-pc58-hwjq-p385) | fetchしたResponseをそのまま返すApp Router handlerがない。bootstrapはJSONとして読み、HTMLを生成する |
| [GHSA-7qx7-33qx-rqx2](https://github.com/vercel/next.js/security/advisories/GHSA-7qx7-33qx-rqx2) | 先生画面で未使用の画像最適化入口を閉じ、通常/エンコード/末尾slashを確認。博士版のPNG最適化は維持 |
| [GHSA-f3mh-rxg3-f5g2](https://github.com/vercel/next.js/security/advisories/GHSA-f3mh-rxg3-f5g2) | Edge routeでcookieを発行しない。既存PythonのHttpOnly/host専用cookieとCSRFを維持 |

上の適用条件は、公式説明と実装を照合した判断である。取得した個別アドバイザリーの一部には修正版欄がNoneのままという、リリース説明との不整合もあった。16.4.5だけで全条件の問題が無条件に解消したとは認定せず、未使用機能と入口閉鎖、実装上の条件を併記した。

[Node.jsの10/21公式情報](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases) でも24.22.1を修正配布として確認。Python/pnpm等は [OSV公式API](https://google.github.io/osv.dev/post-v1-querybatch/) のパッケージ/版照合と個別アドバイザリーで確認した。

### 監査・試験結果

| 検証 | 最終結果 |
|---|---|
| Next.js production build / TypeScript | 成功（16.4.5、Node24.22.1） |
| Nodeテスト | 84/84成功 |
| Python関連回帰 | 重複を除く213項目が成功。新仕様API19、認証、教室/運営境界、履歴・帳票保全等 |
| 固定計算 | Tier A556/556、Tier B38/38一致、既知C6件を維持 |
| 計算試験中のsource hash | 188ファイル、changes=0 |
| 実Chrome | 82/82成功。入力直行・旧URL・初回SSRテーマ・4テーマ・PC/320px・5分類・入力/結果保持・時刻不明・ログアウト/戻る・博士版・画像入口閉鎖等 |
| Python依存整合 | `pip check` 成功 |
| 更新後OSV | Python66配布＋React/React DOM/pnpmの計69照合で該当0 |
| npm依存監査 | 報告された脆弱性0。更新前の監査も0だったため、Next更新の判断には公式情報も使用した |
| 元環境/保護対象 | 元Python66配布が同一。計算・辞書・認証・DB/契約・帳票・テンプレート・旧CSS等37パスにGit差分なし |

Pythonは最初の233実行に既存API25件の重複読込みが含まれたため、現在のID一覧で重複を除いた213項目を報告する。追加の期限/試用/最小レスポンス検証は最終API19件として再試験済み。途中の14/19/72/81件や再実行を足し合わせていない。復元時用に保全した旧teacher履歴/帳票の試験を現在の成功件数へ含めない。

最初の型検査は依存の入替途中でmoduleを解決できず失敗し、導入完了後に再検査して成功した。ブラウザーの最終試験ではログアウト後の戻ると自動転送が競合し、テストのナビゲーション待機を修正して再成功した。アプリの認証を緩めていない。ログには帳票の意図的な失敗系検証も含まれる。実機Excel COMによるPDF再出力、Linux、本番の実利用者ログイン・実データ移行・本番セキュリティスキャンは今回未実施。

残る注意：監査DBの未登録・未知の問題までゼロと保証する結果ではない。本番へ適用する場合は専用設定・DB・公開境界・保持運用を別途確認する。既知の計算上のC項目を今回解消したとは扱わない。

## F. Git・変更ファイル・配備

| 分類 | コミット |
|---|---|
| 鑑定専用化・認証済み初回描画 | `d3d977c` |
| UI間隔・配列・パステル色 | `3cd73c8` |
| 依存セキュリティ更新 | `892d7f4` |
| 記録 | 本文と復元手順を別コミットで保全 |

初回テーマ、カード内部の表示組立て、五行図の表示切替は再構成に必要な接続を含むため最初のコミットにあり、カードの2×2/4列・間隔・色のCSSを次のコミットへ分離した。

変更/追加ファイルは次のとおり。計算・辞書・テンプレート・認証秘密情報は含まない。

- `deployment_boundary.py`、`reading_only.py`、`fortune-next-app/backend/server.py`。
- `fortune-next-app/app/{auth.tsx,gogyo-figure.tsx,layout.tsx,page.tsx,main-fortune.tsx,teacher-theme.tsx,teacher-theme.css,reading-bootstrap.ts,reading-mode.tsx,theme-tokens.ts}`、`app/login/page.tsx`、`fortune-next-app/proxy.ts`。
- `fortune-next-app/package.json`、`fortune-next-app/pnpm-lock.yaml`、`requirements-reading.lock`。
- `tests/{reading_only_cases.py,admin_domain_cases.py,security_scope_cases.py,security_regression_suite.py}`。
- `docs/{mari-reading-only-20261105.md,reading-only-restoration-20261105.md}`。

専用branchだけを通常commit/pushする。終了時のHEAD・GitHub照合・clean状態は開発元 `outputs/mari-reading-only-20261105/git-final.json` に記録する。main統合、既存branchの切替、reset、force push、無関係な変更の消去は行っていない。

本番VPS・本番DB・DNS/nginx・公開サービス・本番アカウント・既存バックアップ・組織版への変更は行っていない。実メールも送っていない。

## G. 本人受入

**確認入口：http://127.0.0.1:13416/**

ボタンからパスワード入力なしで、新しい基本情報入力へ進める。本人用として起動維持する。アプリ13415/API18875、博士版比較13418/内部13417/API18876はすべて127.0.0.1で、合成DBを使う。従来の13406番とは別環境。

入力例は1988-08-12、09:00、東京都、男性。実情報は入力しない。右上で4テーマを選び、結果で次を確認する。

1. ログインから入力へ直接進み、不要な管理・保存・出力操作がない。
2. 初回表示の配色、日干keywords、2×2の人生4時期、右から年/月/日/時の十二運星。
3. 五行図に灰色の輪がなく、3グループがパステル色で、既存5分類も残る。
4. 大運・月運が短く整理され、必要な日時やkeywordsと年間総合運が残る。
5. 「入力に戻る」「新しく鑑定する」、別利用者、時刻不明、テーマ保存・ログアウト。

確認用ボタンはメモリ内の合成資格情報で既存のログインAPIを使う。password/cookie/tokenをファイルや画像へ保存していない。画像は認証表示をマスクして保存する。本人確認用の試験アカウントにのみテーマを設定し、実利用者の設定は変更していない。

次の作業候補は本人による色・余白・操作性の受入と、別の明示指示がある場合の本番切替計画。現在のローカル成功を本番配備済みとは報告しない。
