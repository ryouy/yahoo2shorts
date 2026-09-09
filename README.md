# yc2ys

Yahoo!ニュースの記事とコメントから、AIで原稿を作り、縦型のYouTube Shortsを自動生成するアプリです。記事探索 → コメント取得 → 原稿生成 → 動画・サムネイル生成までを1つのアプリで行います。

![アプリのスクリーンショット](docs/images/screenshot-dashboard.png)

## できること

- テーマ検索・URL指定・「THE GOLD ONLINE」記事からの自動選定
- Yahoo!ニュースのコメントを元にした「匿名掲示板風」原稿の自動生成
- 通常モード（60秒）／Goldモード（本文解説＋コメント、尺長め）
- サムネイル・動画のプレビュー、YouTube用タイトル・ハッシュタグ・概要欄の自動生成
- BGMのアップロード＆ランダム割り当て
- 記事選択から動画生成までワンボタンで実行する「一気通貫」モード

![原稿編集画面](docs/images/screenshot-script-editor.png)

## 必要環境

- Python 3.11以上
- Node.js 20以上（初回ビルドのみ）
- Google Chrome
- ffmpeg（`pip install -r requirements.txt` で同梱バイナリが入ります）
- インターネット接続（Yahoo! / OpenAI / edge-tts）

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..
```

## 起動

```bash
python3 run.py
```

ブラウザで `http://127.0.0.1:8000` が自動的に開きます。

### デスクトップアプリとして使う

```bash
cd frontend
npm run desktop:dev       # 開発モードで起動
npm run desktop:package   # 配布用アプリをビルド（frontend/release/ に出力）
```

## 初回設定

1. 「設定」ページで OpenAI API Key を登録する
2. 「接続テスト」で疎通確認する
3. （任意）チャンネル名・BGM用フォルダなどを設定する

## 使い方

1. 「新規作成」で記事の探し方（テーマ検索 / URL指定 / Gold検索）と動画モードを選ぶ
2. 記事候補を確認し、承認する（または「一気通貫」で最後まで自動実行）
3. 原稿を確認・編集して承認する
4. 動画を生成し、プレビューして保存する

![動画生成画面](docs/images/screenshot-video-generation.png)

## 保存先

生成物は `data/runs/<project_id>/` に保存されます。保存先は「設定 → 成果物フォルダ」で変更できます。BGM用の音楽ファイルは `data/bgm/` に置いてください。

## テスト

```bash
pytest
cd frontend && npm run build
```

## トラブルシューティング

- **Chrome が見つからない**: Chrome を標準の場所にインストールしてください
- **ffmpeg が見つからない**: `pip install -r requirements.txt` を再実行してください
- **Yahoo の地域制限**: 日本国内からアクセスしてください
- **動画時間の上限エラー**: 原稿を短くするか、Gold モードに切り替えてください

---

