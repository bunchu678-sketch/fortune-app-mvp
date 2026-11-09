# 先生版の非販売試作アプリ：未配備の構成資料

2026-11-09の本人訂正により、現在の実利用者が先生・生徒の2名であることと、システムの利用人数上限を分離した。固定人数・UUID許可リストは撤廃する。旧 `two-person-prototype` / `FORTUNE_READING_ALLOWED_USER_IDS` は本候補に使用しない。旧切替準備票・旧成果物・旧承認は本候補に流用しない。

## アクセス制御

通常のセッション認証、対象教室の所属、teacher/student役割、有効状態、既存の契約/試用利用権を各リクエストで検査する。鑑定処理の終了時にも再検査する。未認証・未所属・別教室・停止・失効・無権限は拒否する。有効な所属者が3名・10名になっても判定方式は同じ。公開自由登録を新設せず、今回アカウント・契約・権限を変更しない。

本番の読み取り調査では対象教室の所属4件（先生2・生徒2）が既存判定で利用可能だった。うち実利用者確認済み2件以外の2件はテスト用ドメイン候補。現在の有効所属を自動変更して人数を合わせてはならない。本番反映前にこの追加2件の扱いを本人が判断する必要がある。個人識別情報は公開資料に含めない。

## 専用releaseと安全な接続先

共通ソースを博士/管理者へも提供するため、専用releaseだけに配備先markerを生成する。独立展開後・ビルド前に、そのコピーの `python -B deployment/mari-prototype/mark_release.py --release <絶対パス>` を実行する。API rootとWeb rootの `.mari-reading-release` は `teacher` 1行で、配備時にroot所有・実行UIDは書換え不可とする。共有ソースや博士/管理者releaseにmarkerを作らない。

専用APIは `FORTUNE_DEPLOYMENT_SURFACE=teacher` とunit独立指定 `FORTUNE_REQUIRED_DEPLOYMENT_SURFACE=teacher` を使い、`start_api.py --port 8773` で起動する。起動時は既存DB・対象教室・必要な所属schemaを読取り専用確認する。人数や個人IDを起動条件にしない。markerがある専用releaseでは直接uvicorn起動でも配備先の欠落/誤指定を拒否する。旧固定UUID設定が残っていれば明示エラーで停止し、無視して起動しない。

Webは `FORTUNE_UI_SURFACE=teacher` と `FORTUNE_API_ORIGIN=http://127.0.0.1:8773` をbuild/runtime双方で明示する。専用 `start_web.mjs --app-dir <Web絶対パス> --port 3012` を使用する。欠落・博士8765・旧先生8771・管理者8772・外部URLを拒否する。専用buildのSSRも博士APIへのCookie転送へ切り替わらない。博士/管理者の通常releaseの既定動作は維持する。

## 最小権限のunit原稿

`reading-api.service.in` / `reading-web.service.in` は未配備の原稿。placeholderを具体的な承認済み絶対パスへ置換し、残存を検査する。WebとAPIは別の非sudo専用UID、release/runtimeはroot所有とし、公開ソース/依存fileは0644（実行binaryは0755）、directoryは0755で専用UIDが読めるようにする。env/SMTP/DB/鍵をこの公開コード権限へ変更してはならず、envは非公開root所有0600とする。systemdがenvを読んだ後、サービスから秘密設定領域を不可視にする。

両unitはNoNewPrivileges、PrivateTmp、ProtectSystem=strict、ProtectHome=yes、空capability、SUID/namespace/kernel/control-group保護を使う。WebはDB・SMTP・backup鍵・SSH鍵を読めず、専用CacheDirectoryだけへ書ける。root所有の `.next/cache` を作って専用cacheをbindする。

APIだけが既存共有DBの同じディレクトリを使う。DB単体やWALを別ディレクトリへbindしない。既存所有者を変更せず、専用APIと既存writerの加算ACL・default ACL・DB mode/WAL再作成を両方向で検証する。DB親ディレクトリへの書込みは削除権限も含むため、その下のbackup/秘密fileをInaccessiblePathsで保護する。既存のアクセス権とACL maskへの影響を事前に確認する。本番のuser新設・ACL適用は別承認。

APIにも博士DB・backup暗号鍵・SSH鍵を渡さない。SMTPは通常ログイン/鑑定には不要だが、再設定メール機能の運用判断は別に必要。SMTP未設定では再設定requestが503となり、既存tokenのcomplete経路は別に残る。共有の認証コードを今回勝手に停止/変更しない。再設定メールを維持する場合の任意原稿は `smtp-credentials.conf.in` と `materialize_mail.py`。PID1が既存SMTP config/passwordだけをLoadCredentialで渡す。直接credentialをアプリへ指定するとroot所有0440が既存のprivate_file検査に合わないため、APIのUIDで専用RuntimeDirectory（/run、0700）へ0600のsnapshotを作り、password_file参照だけをそのsnapshotへ向ける。既存のhost/port/TLS/senderと認証コードの所有者検査は維持する。symlink/広いmodeを拒否し、停止時はsystemdが一時領域を削除する。元の秘密領域やbackup鍵をAPIへ公開しない。この任意構成の採用と具体的な非公開参照先は別レビュー/本人承認が必要で、今回は本番で有効化しない。

OS分離をDBの行単位分離と混同しない。共有DBへの書込み権限を持つAPIが侵害された場合、同じDBの他利用者・管理情報への影響リスクは残る。

## 将来の切替手順：今回は実行しない

1. 新候補HEAD、source/build/unit/env原稿のhash、Linux保護実測を固定する。旧承認票は保留のまま、新しい具体範囲で本人承認と実行審査を受ける。mainへ統合しない。
2. 追加2件の所属者の扱い・SMTP運用・専用UID/ACLの具体範囲を決める。今回アカウント変更を先行しない。
3. 既存方式の直前暗号化backupを、別承認後に作成・指定保存先・hash・受領を確認する。旧11月8日17時の復号検証成功は保全し、鍵を作り直さない。
4. 独立release/runtime、専用UID、最小envと共有DB ACLを承認範囲内で配置する。DBのcopy/migration/初期化/復元は行わない。
5. 新API8773のhealth、新Web3012の内部接続・認証・鑑定・テーマを確認するまで先生URLを変更しない。
6. 先生hostだけを新Web/APIへ向ける。旧APIへの迂回と未使用履歴/帳票/管理APIを閉じる。nginx -t後、承認済みreloadと公開HTTPS検証を行う。管理者Web3011/API8772、博士3000/8765は変更しない。
7. 障害時は先生URLだけを503で安全停止する。旧版は履歴・帳票・個人情報の扱いと認可構造が異なるため、人数固定撤廃後も無条件再公開しない。旧先生API8771は今回停止・削除しない。将来停止は利用経路を確認し別承認する。

DB復元は別承認・全writer調整・最新の停止/所属/契約/session状態の確認が必要。コード/接続先の停止をDB復元と混同しない。バックアップ定期ジョブ・課金・実メールを勝手に有効化しない。利用案内は先生の既存アカウントによる鑑定・テーマ変更、履歴/帳票停止、過去データ自体は保持、秘密情報を不具合報告へ含めない点を案内する。送信は別承認。
