# Yahoo Shorts Studio

Yahooニュースの記事探索、コメント取得、OpenAIによる原稿生成、人による編集・承認、TTS、縦型動画・サムネイル生成までをローカルブラウザで行う制作アプリです。元の `yafucome2shorts_v3.ipynb` のStage A/B/Cを、FastAPI・React・SQLiteの再開可能なワークフローへ移植しています。

## 必要環境

- Python 3.11以上
- Node.js 20以上（Frontendの初回ビルドのみ）
- Google Chrome または Chromium
- ffmpeg / ffprobe（`tools/bin` にアプリ専用バイナリを置くこともできます）
- 日本語フォント（Noto Sans JP、ヒラギノ、游ゴシック、Meiryoのいずれか）
- インターネット接続（Yahoo、OpenAI、edge-tts）

macOSではHomebrewを使う場合、`brew install python node ffmpeg`、必要に応じて `brew install --cask google-chrome font-noto-sans-cjk-jp` で準備できます。WindowsではPython、Node.js、Chromeを公式インストーラーから入れ、`winget install Gyan.FFmpeg` を利用できます。Linuxでは各ディストリビューションのパッケージマネージャーを使ってください。アプリ自身は `apt-get` や実行時pip installを行いません。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

環境変数を変更する場合は `.env.example` を参考に、シェルまたは `.env` ローダーから設定してください。`.env` はGit対象外です。

## 起動

```bash
./start.sh
```

Windowsまたは共通の起動方法:

```bash
python run.py
```

### デスクトップアプリ

ブラウザを使わず、ローカルPC上のウィンドウアプリとして起動する場合:

```bash
cd frontend
npm install
npm run desktop:dev
```

配布用のmacOS / Windowsパッケージを作る場合は、Python依存関係を入れたあとに次を実行します。生成物は `frontend/release/` に出力されます。

```bash
python3 -m pip install -r requirements.txt
cd frontend
npm install
npm run desktop:package
```

デスクトップ版は内部で `127.0.0.1` のみを使い、データはOSのアプリデータ領域に保存します。従来の `./start.sh` / `python run.py` によるブラウザ版もそのまま利用できます。

Windows用インストーラーは、GitHub Actionsの **Build Windows desktop app** を手動実行するとArtifactsから取得できます。Windows上で直接ビルドする場合も、同じ `npm run desktop:package` を実行してください。

ビルド済みFrontendがあれば `http://127.0.0.1:8000` を開きます。開発時は別ターミナルで次のようにも起動できます。

```bash
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

アプリはMVPでは `127.0.0.1` のみで利用してください。

## 初回設定

1. 「設定」を開きます。
2. OpenAI API Keyを入力して保存します。
3. 「接続テスト」を押し、設定モデルへアクセスできることを確認します。
4. 「システム」でChrome、ffmpeg、ffprobe、edge-tts、日本語フォントを確認します。

APIキーはOS Keychain / Credential Managerを最優先で使用します。利用できない環境では `data/secrets/openai_api_key` に所有者のみ読み書きできる権限で保存します。SQLite、Frontend、ログ、APIレスポンスにはキーを保存・返却しません。元Notebookに記載されていたキーは使用せず、OpenAI側で必ずローテーションしてください。

## 基本操作

1. 「新規作成」でURL指定、自然言語指定、AI自動選定のいずれかを選びます。
2. 候補カードのスコア・理由・コメント数を確認し、記事を承認します。
3. 本文、Yahooコメント、返信の取得と原稿生成が終わるまで進捗を確認します。
4. 原稿画面で見出し、説明、コメント、返信先、順番を編集して承認します。
5. 動画生成を実行し、ブラウザ内でMP4とサムネイルを確認します。
6. フォルダを開くか、Project全体をZIPで保存します。

記事・コメントの再取得なしで原稿だけ再生成できます。1記事が失敗しても同じProjectの残りの記事は継続し、失敗した記事だけ再試行できます。承認済みの複数原稿は一括で連続動画生成できます。履歴から途中状態を再開できます。

## 保存先

初期値は `data/runs` です。「設定 → General → 成果物フォルダ」から変更できます。

```text
data/
├── app.db
└── runs/<project_id>/
    ├── article_proposals.csv
    ├── approved_articles.json
    ├── draft_records.json
    ├── run.log
    └── <記事タイトル>_<article_id>/
        ├── article.json
        ├── comments.csv
        ├── draft_thread.json
        ├── approved_thread.json
        ├── rendered_thread.json
        ├── audio/
        ├── frames/
        ├── thumbnail.png
        └── output.mp4
```

## テスト

```bash
pytest
cd frontend && npm run build
```

## トラブルシューティング

- `Chrome / Chromium が見つかりません`: Chromeを標準パスへインストールするか、実行ファイルをPATHへ追加してください。
- `Yahooの地域制限`: Yahoo! JAPANを利用できる地域・ネットワークから実行してください。
- `コメントページを読み込めません`: Yahoo側DOM変更やコメント非対応記事の可能性があります。`run.log` を確認してください。
- `ffmpeg / ffprobe が見つかりません`: 両コマンドをPATHへ追加して「システム」を再チェックしてください。
- `日本語フォントが見つかりません`: Noto Sans JPなどをOSへインストールしてください。
- `APIキーが無効 / rate limit / timeout`: 設定画面の接続テスト、OpenAI Projectの権限・利用上限・ネットワークを確認してください。
- 59.5秒を超える: 重要度の低い返信関係を壊さないレスから自動削減します。それでも超える場合は原稿を短くしてください。削除レスは `run.log` とジョブログに残ります。

OpenAI連携はResponses APIのStructured Outputsを使い、APIレスポンスの保存は無効化しています。OpenAI APIの仕様は[公式Responses APIリファレンス](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)を参照してください。
