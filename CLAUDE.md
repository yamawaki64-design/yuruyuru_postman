# 🐧 ゆるゆる郵便屋さん — CLAUDE.md

Claude Code向け引き継ぎドキュメント
バージョン: Streamlit実装版（v8 React版より移植・完成）
最終更新: 2026年3月

---

## このドキュメントの使い方

このファイルはClaude Codeへの引き継ぎ資料です。
`yuruyuru-postman-v8.jsx` はReact/Artifacts実装の参考コードとして添付しています（.gitignore済み）。
**実装はStreamlit + Groq APIの単一ファイル `app.py`（約970行）として完成済みです。**

---

## 1. アプリ概要

ペンギンの郵便屋さん「ペンくん🐧」と一緒にお手紙を書いて、キャラクターに届けるAIチャットアプリ。

| 項目 | 内容 |
|---|---|
| フレームワーク | Streamlit |
| AIモデル | Groq API（モデル: `llama-3.3-70b-versatile`） |
| ファイル構成 | `app.py`（単一ファイル、約970行） |
| デプロイ先 | Streamlit Community Cloud |

---

## 2. ファイル構成

```
yuruyuru_postman/
├── app.py                     # メインアプリ（単一ファイル）
├── requirements.txt           # UTF-8で保存すること（重要）
├── .gitignore
├── .streamlit/
│   ├── config.toml            # headless=true, テーマ設定
│   └── secrets.toml           # GROQ_KEY="..." (.gitignore済み)
└── CLAUDE.md                  # このファイル
```

### requirements.txt（UTF-8必須）

```
streamlit>=1.32.0
groq
```

⚠️ **Windowsで `Write` ツールを使うとUTF-16になる場合がある。**
確認・修正コマンド：
```bash
python3 -c "open('requirements.txt','w',encoding='utf-8').write('streamlit>=1.32.0\ngroq\n')"
```

### .streamlit/secrets.toml（gitignore済み）

```toml
GROQ_KEY = "gsk_..."
```

⚠️ **キー名は `GROQ_KEY`（`GROQ_API_KEY` ではない）**

### .streamlit/config.toml

```toml
[client]
showSidebarNavigation = false

[theme]
primaryColor = "#1a6a9a"
backgroundColor = "#f0f8ff"
secondaryBackgroundColor = "#e6f2fa"
textColor = "#333333"
font = "sans serif"

[server]
headless = true
```

---

## 3. 画面構成・フロー

アプリは `st.session_state.screen` で画面状態を管理します。

| screen値 | 内容 | 背景色 |
|---|---|---|
| `compose` | 手紙作成画面（チャット + 連絡帳タブ） | `#e4f0fa`（薄い水色） |
| `delivering` | 配達アニメーション画面 | グラデーション（水色→草色） |
| `received` | 受取人の感想画面 | `#fce8f0`（薄いピンク） |
| `returning` | ペンくん帰宅画面 | `#ede8f7`（ラベンダー） |

### フロー概要

```
compose
  └─ SEND_TRIGGERS検出 または [DELIVER]→確認ボタン→「✈️ 送る」
       └─ 送り主名前の確認（未取得の場合）
            └─ delivering（感想生成と並列にアニメ実行）
                 └─ received（感想表示）
                      ├─ 2人宛てで1人目表示中：「2人目へ届ける」→ delivering → received
                      ├─ 2人配達完了後：タブ切替ボタン（primary/secondary）で感想を切り替え
                      └─ 「また書く」ボタン → returning → compose
```

---

## 4. キャラクター一覧

```python
CHARACTERS = [
    {"id": "purupuru", "name": "プルプル部長", "emoji": "🐼",
     "role": "58歳・昭和気質の部長", "address": "団子が丘7丁目ポコハウス302",
     "color": "#4a4a4a", "house": "🏠",
     "personality": "昭和気質で少し頑固だが根は優しい。「〜じゃないか」「〜だな」という口調。手紙を受け取ると照れながらも嬉しそうにする。"},
    {"id": "hisohiso", "name": "ヒソヒソくん", "emoji": "🐰",
     "role": "ひそやかな情報通", "address": "ナイショ横丁3番地 ミミうさぎ荘101",
     "color": "#c0698b", "house": "🏡",
     "personality": "ひそひそ話が好きで、こっそり嬉しそうにする。「…ねえ、これ、すごくよかったよ（小声）」みたいな感じ。"},
    {"id": "fuwafuwa", "name": "フワフワさん", "emoji": "🐱",
     "role": "ふんわり系OL", "address": "ひだまり通り12番地 ねこやな荘205",
     "color": "#e8956d", "house": "🏘️",
     "personality": "ふんわりやさしく柔らかい口調。手紙を受け取るとほんわかした感想を言う。"},
    {"id": "gabugabu", "name": "ガブガブくん", "emoji": "🐺",
     "role": "体育会系営業", "address": "ガッツ坂5丁目 オオカミタワー8F",
     "color": "#5b7fa6", "house": "🏢",
     "personality": "熱血で元気。「っす！」「マジですか！」みたいな口調。手紙をもらうと素直に大喜びする。"},
    {"id": "mogumog", "name": "モグモグさん", "emoji": "🐹",
     "role": "おっとり経理", "address": "のんびり丘2番地 ハムスターコーポ1F",
     "color": "#7a9e7e", "house": "🏠",
     "personality": "おっとりしていてゆっくり話す。「あら〜、そうなんですね〜」みたいな感じ。"},
    {"id": "pikapika", "name": "ピカピカちゃん", "emoji": "🦊",
     "role": "頭脳派企画職", "address": "キラキラ東通り9番地 フォックスレジデンス501",
     "color": "#c07a2b", "house": "🏙️",
     "personality": "論理的で少しクールだが、手紙には素直に反応する。少し照れながら分析的な感想を言う。"},
    {"id": "pen", "name": "ペンくん", "emoji": "🐧",
     "role": "ゆるゆる郵便屋さん（自分自身）", "address": "ゆるゆる郵便局 局長室",
     "color": "#1a6a9a", "house": "🏣",
     "personality": "自分宛ての手紙を受け取ってびっくり！照れながらも素直に喜ぶ。「え…え？！ぼく宛て…？」から入り、じわじわ嬉しくなる。「です・ます」口調でちょっとオドオドしている。",
     "is_penkun": True},
]
```

宛先は最大2人まで。

---

## 5. session_state 一覧

```python
defaults = {
    "screen": "compose",
    "chat_history": [],          # [{"role": "user"/"assistant", "content": "...", ...}]
    "selected_chars": [],        # キャラクター辞書のリスト（最大2人）
    "sender_name": None,         # None=未取得, ""=なし, "xxx"=確定
    "waiting_for_name": False,   # 送信直前に名前待ち中フラグ
    "pending_letter_body": "",   # 名前待ち中に保持している手紙本文
    "draft_letter_body": "",     # ペンくんがJSONで提案するたびに自動更新
    "letter_body": "",           # 送信確定済みの手紙本文（「より」付き）
    "reactions": [],             # [{"char": {...}, "text": "..."}]
    "viewing_idx": 0,            # received画面で表示中のキャラインデックス
    "delivered_count": 0,
    "deliver_confirm": False,    # AIが[DELIVER]を返したとき確認ボタン表示フラグ
    "active_tab": "chat",
}
```

### chat_historyの構造

```python
# ユーザー発話
{"role": "user", "content": "..."}

# ペンくんの手紙提案（3フィールド）
{"role": "assistant", "content": "pre文字列", "letter_body": "本文", "post": "確認文"}

# 通知メッセージ（AI呼び出し対象外）
{"role": "assistant", "content": "...", "is_notification": True}
```

---

## 6. 主要ロジック

### 6-1. 送信トリガー（確定文字列マッチ）

```python
SEND_TRIGGERS = [
    "送っておいて", "送ってください", "送って",
    "おくっておいて", "おくってください", "おくって",
    "これで送る", "送信して", "よろしく",
]
```

⚠️ **「お願いします」「おねがいします」は除外済み。** 手紙作成依頼（「書いてお願いします」等）でも誤トリガーしやすいため削除。

**二段階方式：**
- SEND_TRIGGERS → 直接配達（確認ボタンなし）
- `[DELIVER]`タグ → 確認ボタン（`deliver_confirm=True`）表示のみ

どちらもAIの発言内容ではなく、スクリプト側が判断する。

### 6-2. 手紙本文の抽出（JSON形式・確定採用）

`---`形式はGroqで不安定なため、**JSON形式を採用**。

```python
def parse_letter_json(reply: str) -> Optional[dict]:
    # GroqがmarkdownコードブロックでJSONを囲む場合に対応
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.strip())
    try:
        data = json.loads(cleaned)
        if "body" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None
```

AIへのJSON指定（3フィールド）：
```json
{
  "pre": "（直前の発話に具体的に触れたペンくんの反応1〜2行）",
  "body": "（手紙本文。末尾に「〇〇より」は不要）",
  "post": "（「こんな感じでいかがでしょう？修正があれば教えてね🐧」など確認文）"
}
```

- パース成功時：`draft_letter_body = parsed["body"]`を更新。`chat_history`に`letter_body`・`post`フィールド付きで追記
- パース失敗時：`draft_letter_body`は前回の値を保持。`reply_clean`をそのまま`chat_history`に追加

**Try 1が失敗した場合のフォールバック（Try 2）：**
Groqが散文テキスト+JSONを混在させて返す（例：「先輩への丁寧なメールになりそうですね！{"pre":...,"body":...}`）場合に対応。
`re.search(r'\{.*?"body".*?\}', reply, re.DOTALL)` でJSON部分を抽出して再パースする。

### 6-3. 送り主名前の取得フロー

1. 送信トリガー時に`sender_name is None`なら名前を1回だけ聞く（`waiting_for_name=True`）
2. 「なし」「いらない」など → `sender_name = ""`（名前なしで配達）
3. 名前がある場合は手紙末尾に「\n\n〇〇より」を自動追加
4. 名前なし：受取人の感想冒頭も「お手紙が届いた！」になる

```python
NO_NAME_PATTERNS = ["なし", "なしで", "いらない", "不要", "スキップ", "けっこう", "結構", "いいです", "いいや", "ない"]

def extract_sender_name(text: str) -> str:
    """「やまぽんです」→「やまぽん」のように末尾の不要な語尾を除去"""
    name = text.strip()
    suffixes = [
        "でおねがいします", "でお願いします", "でおねがい", "でお願い",
        "にしてください", "にしてほしい", "にしてほしいです",
        "といいます", "と申します", "ともうします",
        "でいいです", "でいいや", "でいい",
        "でーす", "だよん", "だよ！", "だよ",
        "です！", "です。", "です",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()
```

**帰宅後（returning画面）は`sender_name`のみ引き継ぐ。** 他のセッション変数はリセット。

### 6-4. 宛先検出（ひらがな/カタカナ対応）

```python
def kata_to_hira(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ン" else c for c in text)

def detect_characters_in_text(text: str) -> list:
    text_hira = kata_to_hira(text)
    found = []
    for c in CHARACTERS:
        name = c["name"]
        name_hira = kata_to_hira(name)
        base_hira = re.sub(r"(さん|くん|ちゃん|部長|先生|社長|課長)$", "", name_hira)
        if name in text or name_hira in text_hira or (base_hira and base_hira in text_hira):
            found.append(c)
    return found
```

### 6-5. [DELIVER]タグによる配達確認ボタン

AIの返答に`[DELIVER]`が含まれていた場合：
1. `[DELIVER]`を除去して表示
2. `deliver_confirm = True`にセット
3. チャット下部に「📨 送る手紙：」プレビュー＋「✈️ 送る」「✏️ もう少し直す」ボタン表示
4. このエリア表示中はテキスト入力欄を非表示（`deliver_confirm`が`False`のときのみ`st.chat_input`表示）

---

## 7. AIへのシステムプロンプト

### 7-1. 通常会話（ペンくん役）

主要なルール：
- 文面提案・修正時は3フィールドJSONのみで返す（JSON以外の文字を含めない）
- `draft_letter_body`が存在すれば「現在の下書き」として含め、修正依頼時は必ず土台にする
- `pre`フィールドは直前の発話に具体的に触れる（毎回同じ内容を繰り返さない）
- 手紙の送信・配達を明確に指示したときのみ`[DELIVER]`を末尾に追加
- 「手伝ってください」「書いてください」など作成依頼には絶対に`[DELIVER]`を追加しない
- ペンくん宛て（`is_penkun`）でも気づかないふりをして普通に代筆を手伝う

### 7-2. 感想生成（受取人キャラ役）

- 80〜130字程度
- 送り主名がある場合：冒頭で`{sender_name}さんからのお手紙だ`という形で反応
- 送り主名がない場合：冒頭は「お手紙が届いた！」等
- キャラクターの口調と個性を出す、絵文字1〜2個
- ペンくん専用：「え…え？！ぼく宛て…？！」から始まる驚き→照れ→感動の流れ

---

## 8. Groqクライアント

```python
@st.cache_resource
def get_groq_client():
    return Groq(api_key=st.secrets["GROQ_KEY"])

def call_groq_with_retry(messages: list, system_prompt: str, retries: int = 2) -> str:
    client = get_groq_client()
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": system_prompt}] + messages,
                max_tokens=1000,
            )
            return response.choices[0].message.content
        except (RateLimitError, APIError):
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    return ""
```

---

## 9. ペンくん宛て特別演出

宛先に`is_penkun=True`のキャラが含まれる場合、配達テキストを3段階で切り替える。
感想生成APIと`time.sleep`アニメを`concurrent.futures.ThreadPoolExecutor`で並列実行。

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    future_reaction = executor.submit(generate_reaction, current_char, ...)
    run_animation()          # time.sleepを含む（3段階テキスト切替）
    reaction_text = future_reaction.result()
```

3段階テキスト：
1. 「配達中... 🐧 ✉️ / ゆるゆる郵便局へ…」（1.2秒）
2. 「……あれ？ 😱 / この宛先…ぼく…？！」（1.0秒）
3. 「（こっそりポストへ） / ///  …受け取りました  ///」（0.8秒）

通常キャラ：「配達中...」（2.0秒）→「{house} 到着！」（1.5秒）の2段階。

---

## 10. エラーハンドリング

### 通常会話でのAPIエラー

```python
error_msg = "あれ、電波が悪かったみたい…📡 もう一度送ってみてくれる？🐧"
```

### 感想生成でのAPIエラー（白ヤギ黒ヤギ風フォールバック）

```python
REACTION_FALLBACKS = [
    "あ…お手紙、読む前に食べちゃったかも…🐐\nもう一度届けてもらえると嬉しいな。",
    "んんん、お手紙がどこかへ飛んでいっちゃった…\nペンくん、もう一回持ってきてくれると助かるな🐧",
    "ごめんね、ちょっと電波が悪かったみたい…📡\nもう一度送ってみてくれる？",
]
```

---

## 11. UIデザイン実装

### 全体設定

```python
st.set_page_config(page_title="ゆるゆる郵便屋さん", page_icon="🐧", layout="centered")
```

グローバルCSS（`main()`で注入）：
- Noto Sans JP（Google Fonts）
- `#MainMenu`, `header`, `footer` を `visibility: hidden`（Streamlitメニュー非表示）
- `.block-container { padding-bottom: 5rem !important; }`（下部余白）
- `.stBottom { padding-bottom: 48px !important; }`（iPhone Safari の「Manage app」ボタン分の余白）
- `[data-testid="stChatInput"]` に白背景 + `#7aadcc`ボーダー（入力欄を見やすく）
- `.stBottom > div` の背景色を `#e4f0fa`に合わせる

**padding-topはグローバルCSSに書かず、`render_fixed_header()`内で動的に注入する：**
- 宛先バッジあり → `78px`
- 宛先バッジなし → `52px`（delivering/received/returning画面も含む）

### 固定ヘッダー（`render_fixed_header`）

`position:fixed; top:0; left:0; right:0; z-index:1000; background:#2c5282`の2行構造：
- 1行目：「📮 ゆるゆる郵便屋さん」タイトル + 🐧（右端）
- 2行目：宛先バッジ（`flex-wrap`で折り返し対応）。宛先なし時は非表示

### チャット吹き出し（カスタムHTML）

```
ユーザー：右寄せ、青（#3d6cb5）背景、白文字、border-radius: 18px 18px 4px 18px、max-width:85%
         アイコンなし（🙂はiPhoneで怖い顔になるため削除）
ペンくん：左寄せ、白背景、border-radius: 18px 18px 18px 4px、🐧アイコン付き
手紙本文：薄黄色（#fffde7）、左側オレンジボーダー（#f9a825）のカード内に📄アイコン付き
postフィールド：グレーテキスト（#555）で本文カード下に表示
```

### 連絡帳（`_render_address_book`）

`st.columns([5, 1])` でHTMLカード（左5）+ 追加/外すボタン（右1）を横並び。住所を必ず表示。

### 配達中画面（`render_delivering`）

- 背景：`linear-gradient(180deg, #b8ddf0 0%, #c8e8b8 100%)`
- CSSアニメ `penRun`：左から右へペンくんが走る（3.2秒、`position:fixed; bottom:40px`）
- CSSアニメ `letterFloat`：手紙が上下に揺れながら右へ移動（3.2秒、`position:fixed; bottom:90px`）
- テキストは `st.empty()` + `status_box.markdown()` で動的更新
- テキストコンテナは `position:fixed; top:42%` で固定（スクロールしても常に画面中央に表示）

### 受取画面（`render_received`）

- 中央に家アイコン（64px）＋キャラ名＋住所のヘッダー
- `st.expander("📨 届いたお手紙", expanded=True)` で手紙を折り畳み可能に
- 2人配達完了後：`st.columns(2)` のタブ切替ボタン（選択中=`type="primary"`, 非選択=`type="secondary"`）

### 帰宅画面（`render_returning`）

- 背景：`#ede8f7`（ラベンダー）
- CSSアニメ `penReturn`：右から左へペンくんが走る（`transform: scaleX(-1)`で反転）
- テキストコンテナは `position:fixed; top:42%` で固定（配達中と同様）
- 帰宅後に全セッション変数をリセット（`sender_name`のみ引き継ぎ）

---

## 12. 動作確認チェックリスト

1. **JSON形式の安定性** — Groqが毎回正しい3フィールドJSONを返すか
2. **`[DELIVER]`タグの検出** — 送りたい意図を示したときに確認ボタンが出るか
3. **`[DELIVER]`の過検出防止** — 「手伝ってください」で`[DELIVER]`が出ないか
4. **手紙修正時の下書き継承** — 修正依頼で前の文を土台にしているか
5. **ペンくん宛て配達演出** — テキスト3段階切り替えのタイミングが自然か
6. **名前なし配達** — 「なし」と答えたときに「より」が付かないか
7. **語尾除去** — 「やまぽんです」→「やまぽん」として保存されるか
8. **2人目配達フロー** — 1人目受取後に2人目への配達が正常に動くか
9. **タブ切替** — 2人配達完了後にprimary/secondaryボタンで切り替えられるか
10. **レート制限エラー** — 高速連打してフォールバックが出るか確認
11. **帰宅後の名前引き継ぎ** — 「また書く」後も`sender_name`が保持されているか

---

## 13. バージョン履歴

| バージョン | 主な内容 |
|---|---|
| v4 | `---`形式による手紙本文抽出。2人目配達後はヘッダーボタンで切り替え |
| v5 | 送り主名前の保持と「〇〇より」自動追加 |
| v6 | 名前取得フロー見直し。ひらがな送信トリガー追加。敬称重複修正 |
| v7 | Groqエラーハンドリング追加。`[DELIVER]`確認ボタン方式。`draft_letter_body`セッション管理 |
| v8 | ペンくんをキャラクターとして追加。配達中3段階テキスト演出。ペンくん専用感想プロンプト |
| Streamlit版 | Groq API + Streamlit単一ファイル実装。JSON手紙抽出（`---`形式から変更）。カスタムHTML吹き出し。固定ヘッダー2行構造。CSSアニメーション（左→右配達、右→左帰宅）。2人配達後タブ切替。`extract_sender_name`語尾除去。`[DELIVER]`過検出防止。`sender_name`帰宅後引き継ぎ。入力欄スタイリング |
| iPhone対応版 | ヘッダー下余白をpadding-top動的制御に変更。入力欄下にManage appボタン分の余白追加。配達中・帰宅テキストをposition:fixed化（スクロール位置非依存）。`parse_letter_json`にTry2（テキスト混在JSON抽出）追加。ユーザーアイコン🙂削除（iPhone Safari表示問題）。SEND_TRIGGERSから「お願いします」「おねがいします」を除外 |
