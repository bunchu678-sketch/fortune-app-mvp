# Fortune Next App

四柱推命アプリの本番向けUI移行版です。

## 目的

- 既存のPython計算ロジックを残す
- 画面はNext.js / Reactで作る
- Xserver VPSへ移す前にローカルで確認できるようにする
- 将来はWordPressブログから `app.example.com` などへ誘導する

## ローカル起動

### かんたん起動

`start-local.cmd` を実行すると、APIとNext.js画面を起動し、ブラウザで `http://127.0.0.1:3000` を開きます。

止めるときは `stop-local.cmd` を実行します。

### 手動起動

1. Python APIを起動します。

```powershell
& "C:\Users\bunch\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\backend\server.py
```

2. 別のターミナルでNext.jsを起動します。

```powershell
& "C:\Users\bunch\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd" dev
```

3. ブラウザで開きます。

```text
http://127.0.0.1:3000
```

## 構成

- `app/`: Next.js画面
- `backend/server.py`: ローカル確認用Python API
- 既存の計算ロジック: 親フォルダの `calendar_logic.py` などを参照

## 注意

Xserver VPS契約後は、この構成をVPS上で動かす想定です。
現時点ではWordPress連携、VPS自動デプロイ、独自ドメイン設定は未実装です。
