# Yahooニュース → Shorts生成 ローカルWebアプリ化 仕様書

## 1. 目的

現在Google Colab上のNotebookとして動作しているyafucome2shorts_v3.ipynb

**Yahooニュース取得 → Yahooコメント取得 → OpenAIによる原稿生成 → 人間による編集・承認 → TTS → Shorts動画生成**

の一連の処理を、ローカルPC上で動作する対話型Webアプリケーションへ移行する。

Notebookのセルを順番に実行する方式ではなく、ブラウザ上から設定・記事選択・編集・生成・確認まで完結できるようにする。

細かいUI設計や内部実装はエージェント側で適切に判断してよいが、既存Notebookの主要機能は維持すること。

---

# 2. 基本方針

以下の構成を推奨する。

* Frontend: React + TypeScript + Vite
* Backend: Python + FastAPI
* DB: SQLite
* Yahoo取得: Selenium + requests + BeautifulSoup
* LLM: OpenAI API
* TTS: edge-tts
* 画像生成: Pillow
* 動画処理: ffmpeg / ffprobe
* ローカルブラウザ: Chrome / Chromium
* 実行: localhost

Streamlit化ではなく、Frontend / Backendを分離した通常のWebアプリ構成を優先する。

理由は、

* コメント編集UIを作りやすい
* 動画生成の進捗管理をしやすい
* 設定画面をきれいに作れる
* 後から機能追加しやすい
* NotebookコードをPythonサービスとして再利用しやすい

ため。

ただし、より適切な構成がある場合はエージェント判断で変更してよい。

---

# 3. 最重要事項：APIキー管理

現在のNotebookにはOpenAI APIキーが直接コード内に記述されている。

これは廃止すること。

また、現在Notebookに入っているキーは使用継続せず、ユーザー側でローテーションする前提とする。

Webアプリでは設定画面からOpenAI APIキーを登録できるようにする。

## APIキー画面

設定画面に以下を設置する。

* OpenAI API Key入力
* 保存
* 接続テスト
* 登録済み / 未登録表示
* キーの一部だけ表示
* キー変更
* キー削除

例:

```text
OpenAI

API Key
sk-proj-••••••••••••••••8xF3

[ 接続テスト ] [ 変更 ] [ 削除 ]

接続状態: OK
```

APIキーをFrontendへ返さないこと。

保存方法は、

1. OS Keychain / Credential Manager
2. `.env`
3. その他ローカルの安全なSecret Store

などから適切な方法を選択する。

可能ならPython `keyring` 等を利用し、macOS Keychain / Windows Credential Manager等に保存する。

SQLiteへAPIキーを平文保存しない。

---

# 4. アプリ全体のワークフロー

既存NotebookのStage A / B / CをWeb UIへ移植する。

```text
初期設定
   ↓
記事条件入力
   ↓
Yahoo記事探索
   ↓
記事候補一覧
   ↓
人間が記事を承認
   ↓
記事本文取得
   ↓
Yahooコメント取得
   ↓
OpenAI原稿生成
   ↓
原稿編集
   ↓
人間が原稿承認
   ↓
TTS生成
   ↓
Shorts動画生成
   ↓
サムネイル生成
   ↓
動画レビュー
   ↓
保存 / ZIP
```

各工程は可能な限り再実行可能にする。

例えば原稿だけ再生成した場合、Yahooコメントを再取得する必要はない。

---

# 5. メイン画面

左サイドバー形式を推奨する。

```text
Yahoo Shorts Studio

ダッシュボード

新規作成
記事選択
原稿編集
動画生成

履歴

設定
システム
```

画面は過度に派手にせず、制作ツールらしいシンプルなデザインにする。

---

# 6. 初期設定画面

初回起動時にセットアップ画面を表示する。

確認する項目:

### OpenAI

* APIキー
* API接続
* 使用モデル

### Chrome / Selenium

* Chrome検出
* Selenium起動確認
* Yahooニュースアクセス確認

### ffmpeg

* ffmpeg検出
* ffprobe検出

### TTS

* edge-tts動作確認
* 女性音声テスト
* 男性音声テスト

### 日本語フォント

* 利用可能な日本語フォント検出

結果を、

```text
OpenAI       OK
Chrome       OK
Yahoo        OK
ffmpeg       OK
ffprobe      OK
Japanese Font OK
edge-tts     OK
```

のように表示する。

不足しているものについてはインストール方法を案内する。

Notebookのように実行時に `apt-get` する設計にはしない。

---

# 7. 新規プロジェクト作成

動画制作単位を「Project」または「Run」として管理する。

画面上部に、

```text
新しいShortsを作成
```

を配置する。

作成すると一意のIDを発行する。

例:

```text
20260826_121500
```

---

# 8. 記事指定

Notebookに存在する以下3方式を維持する。

## A. URL直接指定

YahooニュースURLを直接登録できる。

複数URL対応。

UI例:

```text
記事URL

https://news.yahoo.co.jp/articles/xxxxxx

[ + URLを追加 ]

[ 記事を取得 ]
```

URL入力時に、

* YahooニュースURLか
* 重複していないか
* 記事が存在するか

をチェックする。

ドラッグ&ドロップ的にURLを複数追加できてもよい。

---

## B. 自然言語で記事指定

Notebookの `DIRECT_ARTICLE_REQUEST` 相当。

例:

```text
石破首相関連の記事を1本
生成AI関連の記事を2本
```

OpenAIで検索条件へ分解し、Yahoo検索を行う。

---

## C. AI自動選定

Notebookの `AUTO_ARTICLE_REQUEST` 相当。

例えば、

```text
直近のYahooニュースから、
コメント欄が活発で、
Shortsで議論になりそうなニュースを選んで
```

のように自然言語で入力できる。

記事本数もUIから指定する。

```text
生成本数

[-] 3 [+]
```

---

# 9. 記事探索設定

詳細設定として以下を変更可能にする。

既存Notebookの設定を初期値として利用する。

```text
Yahoo検索             ON
Yahooトップ           ON
Yahooランキング       ON
Yahooカテゴリ         ON

最大記事経過時間       72時間

AI適合度               40%
コメント活性度         35%
新しさ                 25%
```

通常ユーザーには詳細設定を折りたたんでおく。

---

# 10. 記事候補一覧

記事探索後、NotebookのDataFrame表示ではなくカード形式またはテーブル形式で表示する。

各記事について最低限、

* 選択チェック
* タイトル
* URL
* メディア名
* 公開日時
* 経過時間
* コメント数
* AI Score
* Combined Score
* 選定理由
* 検索元
* 記事をブラウザで開く

を表示する。

例:

```text
[x] ○○問題について政府が発表

Yahooニュース
2時間前
コメント 438件

AI適合度     91
コメント     87
新しさ       96
総合Score    91.0

理由:
意見が分かれやすく短時間で内容を説明できるため

[ Yahooで開く ]
```

最後に、

```text
3件選択中

[ この3記事で進む ]
```

を配置する。

---

# 11. Yahoo記事取得

既存Notebookの以下の処理は基本的に維持する。

* URL validation
* JSON-LD解析
* meta情報解析
* DOM本文抽出
* Seleniumフォールバック
* タイトル取得
* メディア取得
* 公開日時取得
* 本文取得
* Yahoo地域制限検知

結果はDBおよびファイルへ保存する。

---

# 12. Yahooコメント取得

現在のNotebookのコメント取得ロジックを極力そのままPythonモジュールへ移す。

対応するもの:

* 一般コメント
* expertコメント
* 返信コメント
* 「もっと見る」
* コメントページ移動
* コメントID
* 投稿日時
* reply関係
* コメント本文

設定値として、

```text
取得コメント上限       45
返信を取得             ON
最大ページ数           50
最低必要コメント数      6
```

を変更可能にする。

---

# 13. 原稿生成

記事本文とYahooコメントをOpenAIへ渡し、既存NotebookのJSON schemaを基本的に維持する。

概念上、

```json
{
  "title": "",
  "source": "",
  "url": "",
  "intro": {
    "headline": "",
    "explainer": "",
    "narration": ""
  },
  "posts": [
    {
      "text": "",
      "reply_to": null,
      "tone": "",
      "importance": 0,
      "source_comment_ids": []
    }
  ],
  "outro": {
    "text": "",
    "narration": ""
  }
}
```

というデータ構造を維持する。

既存Notebookの原稿ルールも基本的に維持する。

* 6〜9レス
* 基本48文字以内
* 短い一撃レスを最低2件
* 返信レス1〜3件
* 約60秒以内
* Yahoo記事・コメントにない事実を捏造しない
* 元コメントを材料としてShorts向けに再構成する

---

# 14. 原稿編集画面

ここは重要な画面。

Notebookのipywidgets編集機能を通常のWeb UIへ置き換える。

記事ごとに編集画面を用意する。

## 記事説明

```text
見出し

[________________________________]

記事説明音声

[________________________________]
[________________________________]
```

## コメント

カードを縦に並べる。

```text
1

[ いやこれは普通に無理だろ ]

返信先
[ 返信なし ▼ ]

────────────────────────

2

[ これ誰が得するんだ ]

返信先
[ レス1へ返信 ▼ ]
```

機能:

* コメント本文編集
* コメント削除
* コメント追加
* コメント並び替え
* 返信先変更
* 空欄コメント削除
* 推定動画時間リアルタイム更新

可能ならドラッグ&ドロップで並び替え可能にする。

---

# 15. AI再生成

以下を用意する。

```text
[ 全コメント再生成 ]
```

できれば追加で、

```text
[ このコメントだけ書き直す ]
```

も実装してよい。

再生成しても元記事・取得コメントは再取得しない。

---

# 16. 原稿承認

編集終了後、

```text
推定動画時間 52.8秒

[ この原稿を承認 ]
```

を押す。

承認済み原稿のみ動画生成可能とする。

既存Notebookの `approved_thread.json` と同じ考え方を維持する。

---

# 17. 動画生成設定

設定画面または動画生成直前に変更できる。

初期値は既存Notebookを踏襲。

```text
Resolution   1080 x 1920
FPS          30

目標時間      55秒
最大時間      59.5秒

コメント/ページ   3

女性Voice      ja-JP-NanamiNeural
男性Voice      ja-JP-KeitaNeural
Voice Rate     +22%

BGM            ON
BGM Volume     0.052
BPM            158
```

Advanced Settingsとして折りたたむ。

---

# 18. 動画デザイン

現在Notebookに実装されているPOP SHORTS DESIGN v3を基本デザインとして移植する。

維持する要素:

* 1080 x 1920縦動画
* ピンク〜青系グラデーション背景
* 白ベースのカード
* 記事説明専用レイアウト
* コメントカード
* コメントごとのアクセント
* 匿名ユーザー表示
* 返信関係
* ページ送り
* ページドット
* outro
* 縦型サムネイル

現在のNotebookの見た目をまず再現する。

その後テーマ切替等を追加できる構造にしておく。

---

# 19. TTS

既存処理を移植する。

記事説明:

```text
女性音声
```

コメント:

```text
男性 / 女性を交互
```

返信:

```text
可能な限り返信元と異なる音声
```

edge-ttsで音声を生成し、ffprobeで実時間を計測する。

---

# 20. 60秒制御

既存Notebookと同様、

```text
HARD_MAX_VIDEO_SECONDS = 59.5
```

を基本とする。

TTS生成後の実時間を確認し、長すぎる場合、

* importanceが低いレス
* 返信構造を壊しにくいレス

から削除する。

どのレスが削除されたかログに記録する。

---

# 21. 動画生成進捗画面

動画生成は数秒以上かかるため、ボタンを押して無反応になる設計は禁止。

例:

```text
○ 原稿確認
○ TTS生成
○ Intro生成
● コメント映像生成  4 / 8
○ Outro生成
○ 動画結合
○ BGM合成
○ サムネ生成

██████████████░░░░ 72%
```

ログ表示領域も用意する。

```text
詳細ログを表示
```

は折りたたみ式でよい。

Frontendから定期polling、SSE、WebSocket等、方式はエージェント判断。

Redis / Celeryのような外部サーバはMVPでは不要。

---

# 22. エラー処理

1記事が失敗しても他の記事は生成可能にする。

既存Notebookの

```text
CONTINUE_ON_ARTICLE_ERROR = True
```

の思想を維持する。

例:

```text
記事A 生成成功
記事B Yahooコメント取得失敗
記事C 生成成功
```

記事Bのみ、

```text
[ 再試行 ]
```

できるようにする。

---

# 23. 動画レビュー

生成完了後、ブラウザ内で動画を再生できる。

```text
記事タイトル

[ Thumbnail ]

[ Video Player ]

58.3秒

[ 動画を開く ]
[ フォルダを開く ]
[ 再生成 ]
```

複数記事生成した場合はすべて一覧表示する。

Notebookの「全件レビュー」をWeb化する。

---

# 24. 履歴

過去のRunを一覧表示する。

```text
2026/08/26 12:15

3記事
成功 3
失敗 0

[ 開く ]
```

PCを再起動しても履歴が残るようにする。

SQLiteを利用する。

---

# 25. ファイル保存構造

Notebookの `/content/...` は廃止する。

例えば以下。

```text
project/
├── backend/
├── frontend/
├── data/
│   ├── app.db
│   └── runs/
│       └── 20260826_121500/
│           ├── article_proposals.csv
│           ├── approved_articles.json
│           ├── draft_records.json
│           ├── batch_results.csv
│           │
│           ├── 記事タイトル01/
│           │   ├── article.json
│           │   ├── comments.csv
│           │   ├── draft_thread.json
│           │   ├── approved_thread.json
│           │   ├── audio/
│           │   ├── frames/
│           │   ├── thumbnail.png
│           │   └── output.mp4
│           │
│           └── 記事タイトル02/
│
├── .env.example
├── README.md
└── requirements.txt
```

一時ファイルと最終成果物は可能なら分離する。

---

# 26. Backendファイル分割

Notebookの巨大なセルをそのまま1ファイルへコピーしない。

少なくとも機能単位で分割する。

推奨イメージ:

```text
backend/app/

main.py

api/
    settings.py
    projects.py
    articles.py
    scripts.py
    videos.py

core/
    config.py
    security.py
    preflight.py
    exceptions.py

models/
    article.py
    comment.py
    script.py
    project.py
    job.py

services/
    openai_service.py

    yahoo/
        browser.py
        discovery.py
        article_fetcher.py
        comment_fetcher.py
        ranking.py

    script/
        generator.py
        validator.py

    media/
        fonts.py
        renderer.py
        thumbnail.py
        tts.py
        bgm.py
        ffmpeg.py
        video_builder.py

storage/
    database.py
    repository.py
    files.py
```

既存Notebookの関数を責務ごとに移動する。

---

# 27. Frontend構成

例:

```text
frontend/src/

pages/
    Dashboard.tsx
    NewProject.tsx
    ArticleSelection.tsx
    ScriptEditor.tsx
    VideoGeneration.tsx
    ProjectHistory.tsx
    Settings.tsx
    SystemCheck.tsx

components/
    ArticleCard.tsx
    CommentEditor.tsx
    ProgressPanel.tsx
    VideoPreview.tsx
    SettingsField.tsx

api/
    client.ts

types/
    article.ts
    script.ts
    project.ts
```

UIライブラリの選択は任せる。

---

# 28. 設定

Notebookのグローバル定数はWebアプリ上の設定へ移す。

大きく、

### General

* 記事本数
* 出力フォルダ

### OpenAI

* API Key
* Model

### Yahoo

* コメント取得数
* 返信取得
* 最大ページ数
* 記事最大経過時間
* 検索対象

### Script

* レス最低数
* レス最大数
* 最大文字数
* 返信数
* 動画目標時間

### Voice

* 男性Voice
* 女性Voice
* speed

### Video

* resolution
* FPS
* comments per page
* 最大動画時間

### BGM

* ON/OFF
* volume
* BPM

に整理する。

---

# 29. 認証について

このアプリ自体は基本的に、

```text
127.0.0.1 / localhost
```

からのみアクセスするローカルアプリとする。

そのためMVPではユーザーアカウント認証は必須ではない。

ただし将来LAN内公開等をする可能性を考え、必要なら簡易アプリロックを追加できる構造にする。

OpenAIについては設定画面で必ずAPI認証チェックを行えるようにする。

---

# 30. Colab依存の撤去

以下を完全に取り除く。

```python
from google.colab import files
from google.colab import userdata
```

また、

```text
/content/
apt-get
ipywidgets
display(...)
files.download(...)
```

等のColab/Jupyter依存コードもWebアプリから削除する。

Notebook内で行っていたpip installも実行時には行わない。

依存関係は `requirements.txt` または `pyproject.toml` で管理する。

---

# 31. ローカル起動

最終的にはREADMEに従えば簡単に起動できること。

理想形:

```bash
./start.sh
```

または、

```bash
python run.py
```

でBackendとFrontendをまとめて起動する。

自動的に、

```text
http://localhost:8000
```

等をブラウザで開いてもよい。

開発モードについてはFrontend / Backend別起動でも構わない。

---

# 32. macOS / Windows / Linux

可能な限りクロスプラットフォーム化する。

特に、

* Chrome path
* ffmpeg path
* 日本語フォント
* 保存フォルダ
* OSでURL/フォルダを開く処理

についてOS依存コードを直接各所に書かず、専用utilityへまとめる。

---

# 33. システムチェック

設定画面とは別に、

```text
System Status
```

画面を用意してもよい。

表示例:

```text
Python          3.x       OK
Backend                    OK
OpenAI                     OK
Chrome                     OK
Selenium                   OK
Yahoo News                 OK
ffmpeg                     OK
ffprobe                    OK
edge-tts                   OK
Japanese Font              OK
Output Directory           OK
```

問題がある場合は原因を表示する。

---

# 34. 状態管理

NotebookではPythonのglobal変数、

```python
ARTICLE_PROPOSALS_DF
DRAFT_THREAD_RECORDS
THREAD_EDITOR_STATE
BATCH_RESULTS_DF
```

などで状態を保持している。

Webアプリではこれを廃止する。

Project / Article / Script / Job等をSQLiteで管理する。

生成された本文、コメント、原稿、動画等はファイルとして保存し、DBにはパスと状態を保存してよい。

---

# 35. Projectの状態

最低限以下の状態を管理する。

```text
created
searching_articles
waiting_article_approval
fetching_content
generating_scripts
waiting_script_approval
ready_for_video
generating_video
completed
partial_error
error
```

これにより途中から作業を再開できるようにする。

---

# 36. ログ

各処理のログを保存する。

例えば、

```text
data/runs/<run_id>/run.log
```

ユーザー向けには簡潔なメッセージを表示する。

```text
Yahooコメントを取得できませんでした。
```

詳細ログには、

```text
TimeoutException
WebDriverException
ffmpeg stderr
OpenAI API error
```

などを残す。

---

# 37. OpenAIエラー

最低限、

* API Key無効
* rate limit
* timeout
* structured output failure
* connection error

を区別する。

一時エラーは既存Notebook同様数回retryする。

---

# 38. Yahoo側変更への耐性

YahooのDOM変更で全体が壊れないよう、

```text
article_fetcher
comment_fetcher
discovery
```

を独立させる。

CSS Selector等を動画生成ロジックと混在させない。

---

# 39. README

完成後READMEを作成する。

最低限、

* このアプリについて
* 必要環境
* Pythonセットアップ
* Nodeセットアップ
* Chrome
* ffmpeg
* 起動方法
* 初回設定
* OpenAI API Key登録
* 基本操作
* 保存先
* トラブルシューティング

を書く。

---

# 40. 最終的なUX

ユーザー側から見ると、基本操作は以下だけで済む状態を目標とする。

```text
1. アプリ起動

2. ニュース条件またはURLを入力

3. 「記事を探す」

4. 候補記事を選択

5. 「この内容で進む」

6. AI原稿を確認・編集

7. 「原稿を承認」

8. 「動画生成」

9. ブラウザ上で確認

10. MP4 / PNG / ZIPを利用
```

NotebookやPythonコードをユーザーが直接触る必要がない状態にする。

---

# 41. 実装時の優先順位

Phase 1では見た目より、既存Notebookの機能を正確にモジュール化して移植する。

```text
既存Notebook解析
↓
Backendモジュール化
↓
単体で既存処理が動くことを確認
↓
FastAPI API化
↓
Frontend作成
↓
設定画面
↓
履歴・途中再開
↓
UI改善
```

Yahoo取得ロジックや動画生成ロジックを、Web UI作成と同時に不用意に全面書き換えないこと。

まず既存動作を維持し、その後リファクタリングする。

---

# 42. 完成条件

以下がすべてできればMVP完成とする。

* ローカルWebアプリとして起動できる
* Notebook不要
* OpenAI APIキーを画面から設定できる
* APIキーがFrontendやソースコードに露出しない
* OpenAI接続確認ができる
* YahooニュースURLを登録できる
* 自然言語からYahoo記事を探せる
* AIによる自動記事選択ができる
* 記事候補を画面で承認できる
* Yahoo記事本文を取得できる
* Yahooコメントと返信を取得できる
* OpenAIでShorts原稿を生成できる
* ブラウザ上で原稿編集できる
* reply先を編集できる
* 原稿を再生成できる
* 原稿を承認できる
* edge-ttsで音声生成できる
* 現Notebook相当の縦型動画を生成できる
* 59.5秒制御が機能する
* サムネイルを生成できる
* ブラウザ上で動画を再生できる
* 複数記事を連続処理できる
* 1記事失敗しても他の記事は継続できる
* 過去のProjectを開き直せる
* 途中から作業を再開できる
* 成果物フォルダを開ける
* ZIPを生成できる
* エラー内容を確認できる

---

# 43. エージェントへの指示

添付されている `yafucome2shorts_v3.ipynb` を既存実装の正として扱うこと。

まずNotebook全体を解析し、

1. Yahooアクセス
2. 記事探索
3. 記事取得
4. コメント取得
5. OpenAI
6. 原稿validation
7. 原稿編集
8. TTS
9. 画像レンダリング
10. 動画生成
11. BGM
12. サムネイル
13. ファイル保存

に分離する。

既存Notebookで正常動作しているスクレイピング、原稿schema、動画生成処理は可能な限り再利用する。

一方、

* Colab固有処理
* ipywidgets
* global state
* Notebookセル間依存
* ハードコードされたSecret
* `/content` 固定パス

は廃止する。

最終的には「NotebookをWeb画面で包む」のではなく、Notebookの処理を適切なPythonアプリケーションへ再構成すること。

ユーザーが通常操作でPythonコード・JSON・CSV等を直接編集する必要がないアプリにする。

実装上の細かいライブラリ選定、UIコンポーネント、APIパス等は、この仕様を満たす範囲でエージェント側に任せる。
