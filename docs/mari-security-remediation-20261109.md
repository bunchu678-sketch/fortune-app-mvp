# 先生版セキュリティ是正と人数固定撤廃（11-09着手・11-10最終確認）

本番変更は行わない。起点は `bd4fb741f88a2889a7ac7f0a09655a0cfbff11b8`、専用ブランチは `mari-security-remediation-20261109`。受入済みUI・正式計算・正式キーワード・本人照合済みの利用者情報を維持する。

## 本人訂正と利用可能範囲

以前の指示にあった「2名限定」を人数上限として実装していたが、最新の本人判断により撤回した。現在2名が利用することは固定上限の要件ではなく、UUIDリストや人数による起動条件は不要である。所属と利用権限の管理で判定する。

読み取り専用の本番調査では、登録アカウント全体5件、対象教室の所属4件（先生2・生徒2）、有効な既存権限で利用可能4件、停止/非active0件、初回設定未完了0件だった。本人確認済みの実利用者2件以外にテスト用ドメイン候補が2件ある。これらを名称やメールドメインで勝手に拒否せず、不要な試験アカウントなら既存管理機能による通常の停止等を別承認で検討する。今回アカウント・所属・契約・権限は変更していない。個人識別情報は保護されたローカル記録のみ。

未認証は401。正式なセッション、対象教室への有効所属、teacher/student役割、既存の停止・契約・試用利用権判定を維持する。未所属・他教室・停止・失効は拒否する。利用者が3名・10名でも同じ判定で、公開自由登録は追加しない。管理API・履歴・帳票の先生入口での停止も維持する。

## 監査指摘への判断

| 指摘 | 対応と理由 |
|---|---|
| H-1 | 採用。旧先生Web/APIは実効NoNewPrivileges=yes、PrivateTmp=yes、ProtectSystem=full、ProtectHome=read-only。旧新unit原稿の保護欠落は後退だった。新原稿は別の非sudo Web/API UID、ProtectSystem=strict、ProtectHome=yes、空capability等。APIだけDB、Webだけcacheへ書く。 |
| M-1 | 2名固定の強化要求を本人が撤回。`mari_prototype_access.py` とUUID許可リスト/人数起動条件を撤去。既存の認証・所属・役割・利用権判定は削除しない。専用releaseの配備先検査は、博士API接続や管理入口への誤起動を防ぐため維持する。 |
| M-2 | 採用。README・phase2報告と現行準備資料を訂正。障害時は先生URLだけ503。旧版は履歴/帳票/個人情報保護/認可構造が異なるため、人数固定撤廃後も無条件再公開しない。8771は今回停止・削除しない。 |
| L-2 | 採用。専用先生WebはAPI8773を明示し、欠落・8765/8771/8772・外部URLをbuild/start/SSRで拒否する。博士/管理者の通常releaseの既定動作を保つ。 |
| I-1 | 採用。既存サービスの管理用UIDはsudoグループ所属で、backup鍵の所有者でもあり読取り可能だった（内容未読）。新専用UIDには鍵/博士DB/SSH home/設定元を公開しない。既存本番の同一UIDリスク自体は今回変更していない。 |
| I-4 | H-1と併せて検証。root所有releaseの `.next/cache` へ専用CacheDirectoryだけをbindする。 |
| L-3 | 調査。無所属者も共通ログイン自体は可能だが鑑定権限は得ない。通常ログイン/鑑定にはSMTP不要。再設定requestはSMTP未指定で503、既存tokenのcomplete経路は別に残る。共通認証を勝手に変更しない。再設定メール維持用の任意LoadCredential＋専用RuntimeDirectory原稿を作成・合成検証した。root所有0440を直接使う方式は採用せず、既存の所有者検査を維持したAPI所有0600 snapshotを使う。採用は本人判断。 |
| L-1/L-4/L-5/L-6/I-2/I-3/I-5/I-6 | 今回の無条件変更は不採用。締め出し方式、HSTS/CSP、依存縮小、Cookie名、default server、API docs、保存sudo資格情報、IPv6はそれぞれ影響調査と別判断を要する。現状を安全と認定して解消した扱いにはしない。 |

## 実行構造と残る限界

専用releaseにroot所有・書換え不可の `teacher` markerを生成する。unitにも配備先を固定する。これは人数制限ではない。直接uvicorn/Next起動でも配備先/接続先の欠落を拒否する。共通の博士/管理者ソースにはmarkerを作らない。旧固定人数環境設定が残れば明示停止して除去を求め、こっそり無視しない。

DBは既存の同じディレクトリで開き、所有者を保つ加算ACLとdefault ACLで旧writer/API間のWAL/SHM再作成を扱う。DB単体の別ディレクトリbindは使わない。DB親の書込みには削除権限も含まれるため、backup等をnamespaceから隠す。WebはDBを読めない。SMTPを維持する場合も、秘密設定元全体の読取り権限を追加せず、そのunit専用credentialへ必要なsnapshotだけを渡す。

共有DBへ書けるAPIの侵害は、DB内の管理情報・他利用者行にも影響し得る。OSの最小権限は行単位DB分離ではない。既存doctor/adminの同一管理UIDと鍵アクセスの残存も、別途の改善課題。

## 検証記録

Windowsの既存Python444件は436成功/8件POSIX対象外skip。新しい所属・権限21件（有効10名まで追加して許可、未所属/停止/失効/別教室/CSRF/廃止API等）と配備先負試験6件が成功。Node92件、型検査、production build、計算556/556、観測38/38が成功。既知の情報項目C6件は従来の扱いを維持する。

Linuxで以下を完了した。Windowsの成功と区別して記録している。

| 検証 | 結果 |
|---|---|
| 固定依存・Node/型/build | Node24.22.1、Next16.4.5、Python3.12.3。Node92件・型検査・production build成功 |
| 配備設定 | 6件成功。専用releaseの直接uvicorn/Next起動でも環境欠落を拒否 |
| 人数に依存しない所属・利用権 | 21件成功。3名・10名、未所属/別教室/停止/失効/不正セッション/CSRF/廃止APIを確認 |
| Linux専用・合成復元 | POSIX専用8件、合成復元17件成功 |
| 正式計算・観測 | 556/556、38/38成功。既知の情報項目C6件は従来の扱い |
| 実systemd＋HTTPS統合 | 89項目成功。別UID/非sudo、root所有release、実効保護、fake秘密file拒否、WebのDB拒否・cache許可、APIのDB/theme許可、Secure/HttpOnly cookie、CSRF、3名の鑑定、旧経路参照なし、503停止と新候補再開 |
| 共有DB ACL/WAL | 既存writer役とAPI役を別UIDとし、同じ実体DBで双方がWALを作成・接続保持したままAPIと他UIDが書けた。DB所有者は既存writer役を維持 |
| 任意SMTP一時受渡し | 実systemdで既存private_file検査を維持して成功。0600/API所有、symlink/広いmode拒否、安全な更新、停止時のRuntimeDirectory削除。接続/実メールなし |
| Chrome | 322項目成功。4テーマ、320/390/430/700/701/1440px、PC4列・スマホ2×2、公式語句・サイズ・accent色・整列。画像8枚を保存しPC/スマホを目視確認 |
| 入力非保存・整合性 | 実API/画面鑑定後の合成履歴0件、integrity=ok、foreign key違反0 |

Chromeの表示試験はHTTP開発profile、production session/HTTPSは専用の証明書・hostname検証付き試験として別記録した。OS trust storeや証明書検査は変更していない。合格時の両unitの自動再起動回数は0。

検証中、コピー元venvの公開fileが0600で読めない問題を捕捉し、公開release/runtimeだけをroot所有0644/0755に是正した。秘密file/DB/鍵の権限は広げていない。nginx試験のtemp path、停止ログインの期待値（既存仕様401）、共通回帰を走らせるmarkerなしコピーも是正した。初回の失敗記録は保全し、認証の拒否条件やACL検査は弱めていない。

一時VMは承認枠の独立監視で11-10 01:49 JSTに停止記録があり、05時台の再開確認で停止済みだった。所有トンネルも終了し、VMを再起動していない。

## 旧3011の依存評価

実配置はNext.js16.4.2。[公式7勧告の個別比較・管理者版の別更新計画](mari-admin-next-security-20261109.md)を作成した。全7件の対象バージョン範囲に含まれ、image optimizerの利用も確認。cache/Edge条件の使用を検出しなかった項目も、packageが修正済みとは扱わない。管理者Web3011を今回更新・停止・再配備していない。

## 本番反映前の条件と再監査

追加2件の所属者の扱い、SMTP再設定運用、具体的な非公開設定、専用UID/共有DB ACL/秘密保存先の棚卸しを決める。新HEAD・unit・成果物hash・環境原稿で新しい切替承認と実行審査を受ける。旧切替承認は保留で再利用しない。直前の暗号化backup/保存/受領確認、先生URLだけの変更、503停止、実利用者によるログイン確認を承認範囲へ含める。DB migration/復元、アカウント変更、課金、定期backupの新規有効化、実メール、管理者/博士の変更は別事項。

Claude Codeには、人数固定が撤回された前提で、認証/所属/利用権の保持、新unitの実効保護、DB ACLとWAL両方向、backup/SSH/doctor/SMTP設定元の拒否、cache、直接起動とAPI誤指定、503、任意credentialの所有権条件、旧3011の勧告評価を再監査してもらう。元の監査報告本文は書換えない。

## 最終成果物と本番不変確認

新Linux Web bundleは111,299,894 bytes、SHA-256 `82617a3414a45d80e554dc8d4b7f2b9afcc9977e1d748132da69a5851ecfa41a`、build ID `wIw1s4wDx3CI96hNyydPz`。guest→host専用folder→PCのhashが一致した。DB/env/credentialは含めない。試験済みコード207件のhashが現worktreeと一致し、UI/公式語句/計算/認証/役割の主要8ファイルは起点HEADから不変。unit原稿と実効unitのhashは別記録する。

11-10最終の読み取り確認で、本番6serviceのPID・再起動回数とnginx hashが開始時から不変。HTTPS3/health3は全200、DB integrity正常・FK0。全32table/column/migrationが現行モデルと一致（過去記録の31は必須schema集合の件数）。本番の初期化・migration・DB書込み・service操作は行っていない。

現行本番は引き続き旧先生URL→旧サービスであり、今回の新候補は未配備。新候補用の旧API経路閉鎖・503試験を、現在の本番経路を切り替え済みという意味にしてはならない。

旧検証済みHEAD/branchは保全する。新候補はこの報告を含む専用branchのcommitで固定し、最終HEADとsource/archive hashは本人向け完了報告・非公開の成果物manifestへ記録する。main統合・force push・本番配備は行わない。Git管理外の準備資料と引継ぎを更新し、旧承認は保留のままにする。

## 変更ファイル

- `.gitignore`
- `deployment/mari-prototype/README.md`
- `deployment/mari-prototype/api.env.example`
- `deployment/mari-prototype/mark_release.py`
- `deployment/mari-prototype/materialize_mail.py`
- `deployment/mari-prototype/reading-api.service.in`
- `deployment/mari-prototype/reading-web.service.in`
- `deployment/mari-prototype/smtp-credentials.conf.in`
- `deployment/mari-prototype/start_api.py`
- `deployment/mari-prototype/start_web.mjs`
- `deployment/mari-prototype/web.env.example`
- `docs/mari-admin-next-security-20261109.md`
- `docs/mari-security-remediation-20261109.md`
- `docs/mari-two-user-phase2-20261109.md`
- `fortune-next-app/api-origin.d.mts`
- `fortune-next-app/api-origin.mjs`
- `fortune-next-app/app/reading-bootstrap.ts`
- `fortune-next-app/backend/server.py`
- `fortune-next-app/next.config.mjs`
- `mari_prototype_access.py`
- `mari_runtime.py`
- `reading_only.py`
- `tests/mari-api-origin.test.mjs`
- `tests/mari_classroom_access_cases.py`
- `tests/mari_prototype_access_cases.py`
- `tests/mari_runtime_cases.py`
