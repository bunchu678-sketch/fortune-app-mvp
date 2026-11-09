# 2名限定・非販売試作版：隔離Linux検証の構成案

2026-11-08。受入元11070be2efd708690fc9d52a1fea887a4dee45f8を保全する専用branch mari-two-user-linux-20261108。先生と生徒1名の計2名のみが継続利用する。販売・課金・募集・拡大は行わない。AurAEは別プロジェクト。以前の販売計画は履歴であり、今回の作業条件ではない。既存Notionを変更しない。

## 確認済みの環境

このPCには利用可能なWSL distribution / Docker / Podmanがない。既存VPSはLinux x86_64、4CPU、RAM約3.8GiB（調査時available約2.85GiB）、空きdisk約129GiB。unshareの一般ユーザー実行は終了1、bwrap/Docker/Podmanなし。旧Linux preflightのreleaseは現在の博士Web実行元なので書込み・再利用しない。

## 追加承認対象となる一時環境

本番VPSに下記の**一時的なsystemd検証unitと新しい専用ディレクトリだけ**を作る案。OS隔離に管理者権限が必要なため、まだ実行しない。本番の既存unit/nginx/DB/アカウントは変更しない。

- ディレクトリ: `/var/tmp/fortune-mari-linux-lab-20261108`。既存であれば上書きせず確認する。合成DB・合成アカウント・新venv・固定依存・Linux向けbuild・テスト結果だけを格納。受入済みソースを改変しない。
- 一時unit候補: `fortune-mari-linux-lab-20261108.service`。systemd-runによるtransient、enableしない、自動再起動なし、最長3時間。検証後は自分のプロセスだけ終了し、生成物は削除せず保全する。
- 実行時に本番の `/opt/apps`・`/opt/venvs`・`/var/lib/fortune-app`・`/var/lib/fortune-mari`・`/var/lib/fortune-admin`・本番env/秘密鍵/SSH home等を参照できないマウント制限を設ける。Node固定版は検証用ディレクトリへコピーし、共有runtimeを更新しない。
- ProtectSystem=strict、ProtectHome=yes、NoNewPrivileges=yes、PrivateDevices=yes、専用作業領域のみ書込み可能。秘密設定を継承しない。必要なパッケージ取得のHTTPS通信とloopback検証だけを利用する。
- MemoryMax=1800M、MemorySwapMax=256M、CPUQuota=100%、Nice=10、IOWeight=10、TasksMax=96を候補とし、開始直前の余力で再判断する。余力不足なら起動しない。
- Web/APIは空き確認済みの127.0.0.1専用portを選び、既存SSHポート転送でこのPCへ接続する。外向けlisten、firewall/DNS/nginx変更、公開URL切替はしない。
- 失敗時は一時unitの所有プロセスだけ停止。本番unitをstop/restartしない。既存PID・設定hash・公開応答を前後で比較する。一時環境は既存unit設定から独立するが、同じホストのCPU/メモリ/ディスクを使うため負荷影響の可能性は残り、上記制限で抑える。

承認しない場合は新Linux実行を保留し、Windows上の合成試験・利用権調査・復旧経路確認・構築手順の完成まで行う。WSL/新VMの導入もOS設定変更や別資源が必要なので自動実行しない。

## 本番変更の境界

今回の一時環境の承認に、本番サービス切替、nginx変更/reload、本番DB変更、実アカウント・利用権変更、新規メール送信、本番復元は含めない。2名に限定する方法と旧課金判定からの独立は調査・最小変更案に留め、受入済みUI/正式計算/語句を変更しない。

## Windows補助検証と候補コード

受入版に2名だけの制限がないため、任意指定のteacher専用profileと指定UUID2件の追加制限をmari_prototype_access.pyへ実装し、reading_onlyへ確認2行だけを追加した。既存session/所属/役割/停止/契約・試用の確認を置換しない。新しい権利を付与せず、本番設定は未適用。専用起動入口deployment/mari-prototype/start_api.pyはprofile欠落/不正/所属不一致/停止等を読取り確認し、2名設定なしに起動しない。管理者/博士の起動入口は変えない。

Windowsの専用worktree/合成DBではNode89、型検査、Next16.4.5 production build、計算556/観測38が成功。既存Pythonは延べ444実行（436成功/Windowsでは8skip）、新profile26件成功。初回の既存契約試験1件は受入版でも同様に失敗した日付依存で、合成履歴setupの時刻だけを固定し、当該suite34件を再確認して成功した。契約判定本体は不変。試験再実行を成功数へ重複加算しない。

Chromeの4テーマ/境界幅/整列/正式語句/未知/戻る/新規/ログアウト/博士表示に加え、新profileの先生/生徒通常ログイン・鑑定・テーマと第三者拒否、合成API障害を確認する。最終件数・画像・commitは開発元docs/mari_two_user_linux_20261108_notes.mdおよびoutputsの最終記録へ保存する。Windows成功はLinux成功と区別する。

本番の先生・生徒には予約exampleアドレス以外の候補が各1件あるが、これが実際の2名かは本人照合待ち。今回実ログイン/権限変更なし。現在の無料試用は初回設定リンク期限を過ぎても設定済み利用者の利用を止めず、契約/請求の新規作成なしを合成再現した。請求/督促/有料移行を有効化しない。

最新既存バックアップ11/08 17時はHDDverified/hash一致、VPSacked。メモリ内だけの既存鍵による復号検証は自動承認審査が具体的な明示承認を確認できないとして拒否し、未実行。追加確認への回答待ちであり、別経路への迂回はしない。平文DB作成・本番復元・鍵変更なし。

**状態：候補コードと手順のWindows補助検証まで。Linux一時環境・実バックアップ復号・実利用者照合の追加確認に回答後、残る検証を実施する。本番切替可と判定しない。**
