# 旧管理者Web3011のNext.js評価と別更新計画

2026-11-09の読み取り専用調査。実稼働3011はNext.js 16.4.2、新先生候補は16.4.5。OSV検出0件だけで安全とは判定しない。管理者Webの更新・配備は今回実施しない。

[公式16.4.5リリース](https://github.com/vercel/next.js/releases/tag/v16.4.5)に掲載された2026-11-03公開7件を個別に比較した。すべてmoderateで、16.4.2は全7件のバージョン範囲に含まれる。下表はパッケージの影響範囲と実際の使用条件を区別する。

| 公式勧告 | 16系の対象範囲／修正 | 成立条件の要点 | 3011の読み取り結果と評価 |
|---|---|---|---|
| [GHSA-mfr8-8qww-v76h](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h) | 16.3.0～16.4.4／16.4.5 | root paramsを参照するuse cacheを直接/unstable_cache双方から呼ぶcold start競合 | use cache・unstable_cacheの使用を現配置のappソースで検出せず。条件の使用は確認できない。 |
| [GHSA-vc7v-qv4w-wrv8](https://github.com/vercel/next.js/security/advisories/GHSA-vc7v-qv4w-wrv8) | 16.2.0～16.4.4／16.4.5 | Cache Components、入れ子のuse cache、遅延root params情報によるcache key問題 | cacheComponents有効化・use cacheを検出せず。 |
| [GHSA-vvgp-ww4w-46vf](https://github.com/vercel/next.js/security/advisories/GHSA-vvgp-ww4w-46vf) | 16.4.0～16.4.4／16.4.5 | self-host、Cache Components、partialPrefetch未有効、未生成dynamic params/Suspenseのfallback shell cache | self-hostは該当するがcacheComponents有効化を検出せず。 |
| [GHSA-rhh4-g77r-r9qj](https://github.com/vercel/next.js/security/advisories/GHSA-rhh4-g77r-r9qj) | 16.0.0～16.4.4／16.4.5 | use cache関数のbinary引数によるcache key衝突 | use cacheの使用を検出せず。 |
| [GHSA-pc58-hwjq-p385](https://github.com/vercel/next.js/security/advisories/GHSA-pc58-hwjq-p385) | 16.0.0～16.4.4／16.4.5 | upstream応答を返すApp Router route handler/fetch cacheとHTTP/1 reverse proxy queue等 | app内route handlerは0件。reverse proxyは存在。現配置で該当handler使用は確認できない。 |
| [GHSA-7qx7-33qx-rqx2](https://github.com/vercel/next.js/security/advisories/GHSA-7qx7-33qx-rqx2) | 16.0.0～16.4.4／16.4.5 | image optimizerによる攻撃者SVGの処理。dangerouslyAllowSVG=falseでも回避できない | next/image importあり、unoptimized=trueの設定なし。実nginxの管理者URLは `_next/.*` を3011へ許可している。該当機能の入口があり、優先して更新計画が必要。攻撃payloadによる悪用実証は実施していない。 |
| [GHSA-f3mh-rxg3-f5g2](https://github.com/vercel/next.js/security/advisories/GHSA-f3mh-rxg3-f5g2) | 16.0.0～16.4.4／16.4.5 | Edge routeのNextResponseで設定したcookieが内部応答headerへ重複 | Edge runtime指定・app route handlerを検出せず。認証APIは別Pythonサービス。 |

検出なしは、パッケージが修正済みという意味でも悪用不可能の証明でもない。文字列/配置ソースの調査には動的設定・隠れた経路の限界がある。本番へ攻撃payloadを送らず、image optimizerのcacheを書き込む試験も行っていない。

## 管理者版の独立更新計画（未承認・未実施）

1. 3011が管理者と旧先生で共有されていることを維持して、実稼働ソース・build条件・Node・lockfileを固定する。先生専用候補を丸ごと3011へ置かない。
2. 共有Webの機能を維持した別ブランチで、承認時点の公式勧告を再確認し、少なくとも上記7件を修正するNext版へ更新する。今回の16.4.5候補との差を参考にし、無関係なUI/認証変更を混ぜない。
3. 合成管理者/先生アカウントで管理画面、ログイン/再設定、CSRF/session、静的assetと画像、管理者API8772、旧先生API8771との互換を隔離検証する。
4. 新build/hash・専用更新範囲・停止条件・管理者の安全停止/復旧計画を提示し、別の本人承認と実行審査を受ける。共有3011を停止/再配備する承認は今回の先生版是正には含まれない。
5. バックアップ受領・切替前確認後にだけ実施し、先生/管理者双方の経路とDBを確認する。博士3000/API8765は対象外。

先生版を新3012へ分離しても、旧3011の脆弱性は修正されない。管理者更新は残課題として独立に追跡する。
