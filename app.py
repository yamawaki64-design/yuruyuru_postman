import streamlit as st
from groq import Groq, RateLimitError, APIError
from typing import Optional
import re
import json
import time
import concurrent.futures
import random

# ─────────────────────────────────────────────
# キャラクター設定
# ─────────────────────────────────────────────
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

SEND_TRIGGERS = [
    "送っておいて", "送ってください", "送って",
    "おくっておいて", "おくってください", "おくって",
    "これで送る", "送信して", "よろしく",
]

NO_NAME_PATTERNS = ["なし", "なしで", "いらない", "不要", "スキップ", "けっこう", "結構", "いいです", "いいや", "ない"]

REACTION_FALLBACKS = [
    "あ…お手紙、読む前に食べちゃったかも…🐐\nもう一度届けてもらえると嬉しいな。",
    "んんん、お手紙がどこかへ飛んでいっちゃった…\nペンくん、もう一回持ってきてくれると助かるな🐧",
    "ごめんね、ちょっと電波が悪かったみたい…📡\nもう一度送ってみてくれる？",
]

# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────
def is_send_trigger(text: str) -> bool:
    return any(t in text for t in SEND_TRIGGERS)

def is_no_name(text: str) -> bool:
    return any(text.strip().startswith(p) for p in NO_NAME_PATTERNS)

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

def with_honorific(name: str) -> str:
    if re.search(r"(さん|くん|ちゃん|部長|先生|社長|課長)$", name):
        return name
    return f"{name}さん"

def get_reaction_fallback() -> str:
    return random.choice(REACTION_FALLBACKS)

def parse_letter_json(reply: str) -> Optional[dict]:
    # Try 1: remove markdown code blocks and parse directly
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.strip())
    try:
        data = json.loads(cleaned)
        if "body" in data:
            return data
    except json.JSONDecodeError:
        pass
    # Try 2: extract JSON object embedded in prose text
    match = re.search(r'\{.*?"body".*?\}', reply, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if "body" in data:
                return data
        except json.JSONDecodeError:
            pass
    return None

def kata_to_hira(text: str) -> str:
    """カタカナをひらがなに変換（検出用）"""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ン" else c for c in text)

def detect_characters_in_text(text: str) -> list:
    """ひらがな・カタカナ・敬称なし形式も含めてキャラクターを検出"""
    text_hira = kata_to_hira(text)
    found = []
    for c in CHARACTERS:
        name = c["name"]
        name_hira = kata_to_hira(name)
        base_hira = re.sub(r"(さん|くん|ちゃん|部長|先生|社長|課長)$", "", name_hira)
        if (
            name in text
            or name_hira in text_hira
            or (base_hira and base_hira in text_hira)
        ):
            found.append(c)
    return found

# ─────────────────────────────────────────────
# Groq クライアント
# ─────────────────────────────────────────────
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
        except RateLimitError:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except APIError:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    return ""

# ─────────────────────────────────────────────
# システムプロンプト
# ─────────────────────────────────────────────
def build_system_prompt(sender_name, selected_chars: list, draft_letter_body: str = "") -> str:
    recipient_info = (
        "、".join([c["name"] + "（" + c["role"] + "）" for c in selected_chars])
        if selected_chars else "まだ宛先が確定していません。"
    )
    if selected_chars:
        recipient_line = f"宛先は「{recipient_info}」です。"
    else:
        recipient_line = recipient_info

    sender_line = f"送り主の名前：{sender_name}" if sender_name else "送り主の名前：まだ不明"

    draft_section = ""
    if draft_letter_body:
        draft_section = f"\n現在の手紙の下書き（修正・追加の依頼があれば必ずこの文を土台にすること）：\n---\n{draft_letter_body}\n---\n"

    return f"""あなたは「ゆるゆる郵便屋さん」のペンギンの郵便屋さんです🐧
{sender_line}
{recipient_line}
宛先は最大2人です。
{draft_section}
ルール：
- 常に明るく親切に、短めに返答する
- 文面を提案・修正するときは必ず以下のJSON形式のみで返すこと。JSON以外の文字を含めないこと。
{{"pre": "（ユーザーが直前に言ったことに必ず具体的に触れながらペンくんらしい話し言葉で応答する1〜2行。初回提案なら依頼内容への共感・意気込み「〇〇したいんですね！伝わるようにがんばります」、修正依頼なら「△△を〇〇にするんですね、了解です！」、追加依頼なら「〇〇の一文を追加するんですね！」のように、直前の発話内容を受けた反応にする。毎回同じ内容を繰り返さないこと）", "body": "（手紙本文。末尾に「〇〇より」は不要）", "post": "（「こんな感じでいかがでしょう？修正があれば教えてね🐧」など手紙についての一言確認）"}}
- 修正依頼の場合は必ず現在の下書きを土台にして修正し、同じJSON形式で返す
- ユーザーが手紙の送信・配達を明確に指示したとき（「送って」「送ってください」「これで送る」「配達して」「届けて」「よろしく」など）のみ、返答の末尾に[DELIVER]とだけ追加する
- 「手伝ってください」「書いてください」「教えてください」など、手紙作成や会話の依頼には絶対に[DELIVER]を追加しない
- [DELIVER]は1回の返答につき末尾に1回だけ使うこと
- 宛先がまだ不明な場合は誰に送るか聞く
- 手紙本文の末尾に確認文は絶対に入れない（postフィールドに入れること）
- 宛先に「ペンくん（自分自身）」が含まれていても、絶対に気づかないふりをして普通に代筆を手伝うこと
"""

def build_reaction_prompt(char: dict, sender_name) -> str:
    has_sender = bool(sender_name)

    if char.get("is_penkun"):
        name_line = f"- 「{sender_name}さんから…！」と送り主の名前に反応する" if has_sender else ""
        return f"""あなたはペンギンの郵便屋さん「ペンくん」です🐧
自分が代筆を手伝っていたお手紙が、まさか自分宛てだったことに今はじめて気づきました。

ルール：
- 80〜130字程度で反応する
- 必ず「え…え？！ぼく宛て…？！」という驚きから始める
- じわじわ読んで照れながら嬉しくなっていく流れにする
{name_line}
- 「です・ます」口調で、少しオドオドしている
- 最後はちょっと泣きそうになってもいい
- 絵文字を1〜2個使ってよい"""

    if has_sender:
        intro_rule = f"- 必ず冒頭で「{sender_name}さんからのお手紙だ」という形で送り主の名前にキャラの口調で自然に反応する"
    else:
        intro_rule = "- 冒頭は「お手紙が届いた！」などお手紙が届いたことへの反応にする（送り主名は言及しない）"

    sender_line = f"送り主の名前：{sender_name}" if has_sender else "送り主の名前：不明（名前なしのお手紙）"

    return f"""あなたは「{char['name']}」（{char['role']}）です。
性格：{char['personality']}
{sender_line}

ルール：
- 80〜130字程度で感想を述べる
{intro_rule}
- キャラクターの口調と個性を出す
- 手紙の内容に具体的に触れる
- 否定的・攻撃的にならない
- 末尾に「これでいいですか？」などの確認文は入れない
- 絵文字を1〜2個使ってよい"""

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
def init_session():
    defaults = {
        "screen": "compose",
        "chat_history": [],
        "selected_chars": [],
        "sender_name": None,
        "waiting_for_name": False,
        "pending_letter_body": "",
        "draft_letter_body": "",
        "letter_body": "",
        "reactions": [],
        "viewing_idx": 0,
        "delivered_count": 0,
        "deliver_confirm": False,
        "active_tab": "chat",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ─────────────────────────────────────────────
# 配達処理
# ─────────────────────────────────────────────
def finalize_and_deliver():
    body = st.session_state.draft_letter_body
    sender = st.session_state.sender_name
    if sender:
        full_body = body + f"\n\n{sender}より"
    else:
        full_body = body
    st.session_state.letter_body = full_body
    st.session_state.reactions = []
    st.session_state.viewing_idx = 0
    st.session_state.delivered_count = 0
    st.session_state.screen = "delivering"

def generate_reaction(char: dict, letter_body: str, sender_name) -> str:
    prompt = build_reaction_prompt(char, sender_name)
    messages = [{"role": "user", "content": f"お手紙の内容：\n{letter_body}"}]
    try:
        return call_groq_with_retry(messages, prompt)
    except Exception:
        return get_reaction_fallback()

# ─────────────────────────────────────────────
# ユーザー入力処理
# ─────────────────────────────────────────────
def handle_user_input(text: str):
    # 名前待ち中
    if st.session_state.waiting_for_name:
        st.session_state.waiting_for_name = False
        st.session_state.sender_name = "" if is_no_name(text) else extract_sender_name(text)
        st.session_state.draft_letter_body = st.session_state.pending_letter_body
        st.session_state.pending_letter_body = ""
        finalize_and_deliver()
        st.rerun()
        return

    st.session_state.chat_history.append({"role": "user", "content": text})

    # テキストからキャラクター自動検出
    for c in detect_characters_in_text(text):
        ids = [x["id"] for x in st.session_state.selected_chars]
        if c["id"] not in ids and len(st.session_state.selected_chars) < 2:
            st.session_state.selected_chars.append(c)

    # ① SEND_TRIGGERS → 直接配達（ボタンなし）
    if is_send_trigger(text):
        if not st.session_state.selected_chars:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "あれ、宛先がまだ決まっていないよ🐧 誰に送るか教えてください！",
            })
            st.rerun()
            return
        if not st.session_state.draft_letter_body:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "手紙の文面がまだできていないみたい🐧 まずどんなことを書くか教えてください！",
            })
            st.rerun()
            return
        if st.session_state.sender_name is None:
            st.session_state.waiting_for_name = True
            st.session_state.pending_letter_body = st.session_state.draft_letter_body
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "送り主のお名前を教えてください🐧 「なし」でもOKです！",
                "is_notification": True,
            })
            st.rerun()
            return
        finalize_and_deliver()
        st.rerun()
        return

    # AI呼び出し（is_notification メッセージは除外）
    ai_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_history
        if not m.get("is_notification")
    ]
    system_prompt = build_system_prompt(
        st.session_state.sender_name,
        st.session_state.selected_chars,
        st.session_state.draft_letter_body,
    )

    try:
        reply = call_groq_with_retry(ai_messages, system_prompt)
    except Exception:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "あれ、電波が悪かったみたい…📡 もう一度送ってみてくれる？🐧",
        })
        st.rerun()
        return

    # [DELIVER] タグ処理
    deliver_tag = "[DELIVER]" in reply
    reply_clean = reply.replace("[DELIVER]", "").strip()

    # JSON 手紙抽出
    parsed = parse_letter_json(reply_clean)
    if parsed:
        st.session_state.draft_letter_body = parsed["body"]
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": parsed.get("pre", ""),
            "letter_body": parsed["body"],
            "post": parsed.get("post", ""),
        })
    else:
        st.session_state.chat_history.append({"role": "assistant", "content": reply_clean})

    # [DELIVER] → 確認ボタン表示のみ
    if deliver_tag:
        if st.session_state.draft_letter_body:
            st.session_state.deliver_confirm = True
        else:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "手紙の文面がまだできていないみたい🐧 まずどんなことを書くか教えてください！",
            })

    st.rerun()

# ─────────────────────────────────────────────
# HTML ユーティリティ
# ─────────────────────────────────────────────
def he(text: str) -> str:
    """HTML エスケープ + 改行保持"""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
    )


# ─────────────────────────────────────────────
# 固定ヘッダー
# ─────────────────────────────────────────────
def render_fixed_header(selected_chars: list):
    # ヘッダー高さに合わせてpadding-topを動的に設定
    pt = "78px" if selected_chars else "52px"
    st.markdown(
        f'<style>.block-container{{padding-top:{pt}!important;}}</style>',
        unsafe_allow_html=True,
    )
    # 1行目：タイトル＋🐧
    row1 = (
        '<div style="display:flex;justify-content:space-between;align-items:center;">'
        '<div style="color:white;font-weight:700;font-size:17px;">📮 ゆるゆる郵便屋さん</div>'
        '<div style="font-size:26px;">🐧</div>'
        '</div>'
    )
    # 2行目：宛先バッジ（ある場合のみ）
    row2 = ""
    if selected_chars:
        badges = "".join(
            f'<span style="background:rgba(255,255,255,0.22);color:white;'
            f'border:1px solid rgba(255,255,255,0.5);border-radius:20px;'
            f'padding:2px 10px;font-size:12px;white-space:nowrap;">'
            f'{c["emoji"]} {c["name"]}</span>'
            for c in selected_chars
        )
        row2 = (
            f'<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px;">'
            f'{badges}</div>'
        )

    st.markdown(
        f'<div style="position:fixed;top:0;left:0;right:0;z-index:1000;'
        f'background:#2c5282;padding:8px 20px;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.2);">'
        f'{row1}{row2}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# 画面: compose
# ─────────────────────────────────────────────
def render_compose():
    st.markdown(
        '<style>.stApp{background-color:#e4f0fa !important;}</style>',
        unsafe_allow_html=True,
    )
    render_fixed_header(st.session_state.selected_chars)

    tab_chat, tab_book = st.tabs(["✉️ 手紙を書く", "📒 連絡帳"])
    with tab_book:
        _render_address_book()
    with tab_chat:
        _render_chat()


def _render_address_book():
    st.markdown("### 📒 連絡帳")

    if st.session_state.selected_chars:
        st.markdown("**📮 今回の宛先**")
        for c in st.session_state.selected_chars:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f'<div style="background:#e8f0fa;border:2px solid #3d6cb5;border-radius:10px;'
                    f'padding:8px 14px;margin:2px 0;">'
                    f'<span style="font-size:20px;">{c["emoji"]}</span> '
                    f'<strong style="color:#3d6cb5;">{c["name"]}</strong>'
                    f'<span style="color:#888;font-size:12px;"> — {c["role"]}</span><br>'
                    f'<span style="color:#aaa;font-size:11px;">📍 {c["address"]}</span></div>',
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("外す", key=f"remove_{c['id']}", use_container_width=True):
                    st.session_state.selected_chars = [
                        x for x in st.session_state.selected_chars if x["id"] != c["id"]
                    ]
                    st.rerun()
        if len(st.session_state.selected_chars) < 2:
            st.info("もう1人追加できます（最大2人）")
        st.divider()
    else:
        st.info("キャラクターをタップして宛先に追加しよう！（最大2人）")
        st.divider()

    for c in CHARACTERS:
        selected = any(x["id"] == c["id"] for x in st.session_state.selected_chars)
        can_add = len(st.session_state.selected_chars) < 2 and not selected

        bg = "#e8f0fa" if selected else "white"
        border = "2px solid #3d6cb5" if selected else "1px solid #dde6f0"
        name_color = "#3d6cb5" if selected else "#333"
        check = "✓ " if selected else ""

        # カード + ボタンを横並び
        col_card, col_btn = st.columns([5, 1])
        with col_card:
            st.markdown(
                f'<div style="background:{bg};border:{border};border-radius:12px;'
                f'padding:10px 16px;margin:4px 0;box-shadow:0 1px 3px rgba(0,0,0,0.06);">'
                f'<span style="font-size:22px;">{c["emoji"]}</span> '
                f'<strong style="color:{name_color};">{check}{c["name"]}</strong>'
                f'<span style="color:#888;font-size:12px;"> — {c["role"]}</span><br>'
                f'<span style="color:#aaa;font-size:11px;margin-left:4px;">📍 {c["address"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            st.markdown('<div style="margin-top:12px;"></div>', unsafe_allow_html=True)
            if selected:
                if st.button("外す", key=f"char_{c['id']}", use_container_width=True):
                    st.session_state.selected_chars = [
                        x for x in st.session_state.selected_chars if x["id"] != c["id"]
                    ]
                    st.rerun()
            elif can_add:
                if st.button("追加", key=f"char_{c['id']}", use_container_width=True, type="primary"):
                    st.session_state.selected_chars.append(c)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"（{c['emoji']} {c['name']} を宛先に追加しました📮）",
                        "is_notification": True,
                    })
                    st.rerun()
            else:
                st.button("×", key=f"char_{c['id']}", use_container_width=True, disabled=True)


def _render_chat():
    # 初期メッセージ
    if not st.session_state.chat_history:
        st.markdown(
            '<div style="display:flex;justify-content:flex-start;margin:8px 0;align-items:flex-end;gap:8px;">'
            '<div style="font-size:26px;flex-shrink:0;margin-bottom:2px;">🐧</div>'
            '<div style="background:white;border-radius:18px 18px 18px 4px;'
            'padding:10px 16px;max-width:78%;font-size:14px;line-height:1.7;color:#333;'
            'box-shadow:0 1px 4px rgba(0,0,0,0.1);">'
            'こんにちは！郵便屋のペンくんです🐧✉️<br>どなたに、どんな内容のお手紙を送りたいですか？<br>'
            '（2人まで一緒に送れるよ！）'
            '</div></div>',
            unsafe_allow_html=True,
        )

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            content = he(msg["content"])
            st.markdown(
                f'<div style="display:flex;justify-content:flex-end;margin:8px 0;">'
                f'<div style="background:#3d6cb5;color:white;'
                f'border-radius:18px 18px 4px 18px;'
                f'padding:10px 16px;max-width:85%;font-size:14px;line-height:1.7;'
                f'white-space:pre-wrap;word-break:break-word;'
                f'box-shadow:0 2px 6px rgba(61,108,181,0.25);">{content}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            content_text = msg.get("content", "")
            letter_body = msg.get("letter_body", "")
            inner = ""
            if content_text:
                inner += f'<div style="white-space:pre-wrap;">{he(content_text)}</div>'
            if letter_body:
                inner += (
                    f'<div style="background:#fffde7;border-left:4px solid #f9a825;'
                    f'border-radius:0 8px 8px 0;padding:8px 14px;margin:6px 0;'
                    f'font-size:0.88em;white-space:pre-wrap;color:#555;">'
                    f'📄 {he(letter_body)}</div>'
                )
            if msg.get("post"):
                inner += f'<div style="white-space:pre-wrap;margin-top:6px;color:#555;">{he(msg["post"])}</div>'
            st.markdown(
                f'<div style="display:flex;justify-content:flex-start;margin:8px 0;'
                f'align-items:flex-end;gap:8px;">'
                f'<div style="font-size:26px;flex-shrink:0;margin-bottom:2px;">🐧</div>'
                f'<div style="background:white;border-radius:18px 18px 18px 4px;'
                f'padding:10px 16px;max-width:78%;font-size:14px;line-height:1.7;color:#333;'
                f'box-shadow:0 1px 4px rgba(0,0,0,0.1);">{inner}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # 配達確認ボタン
    if st.session_state.deliver_confirm:
        st.markdown("---")
        if st.session_state.draft_letter_body:
            st.markdown(
                f'<div style="background:#f0f7ff;border:1px solid #b0cce8;border-radius:10px;'
                f'padding:10px 16px;margin:8px 0;font-size:14px;white-space:pre-wrap;color:#333;">'
                f'📨 <strong>送る手紙：</strong><br>{he(st.session_state.draft_letter_body)}</div>',
                unsafe_allow_html=True,
            )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✈️ 送る", use_container_width=True, type="primary", key="btn_send"):
                st.session_state.deliver_confirm = False
                if not st.session_state.selected_chars:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "あれ、宛先がまだ決まっていないよ🐧 誰に送るか教えてください！",
                    })
                    st.rerun()
                elif st.session_state.sender_name is None:
                    st.session_state.waiting_for_name = True
                    st.session_state.pending_letter_body = st.session_state.draft_letter_body
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "送り主のお名前を教えてください🐧 「なし」でもOKです！",
                        "is_notification": True,
                    })
                    st.rerun()
                else:
                    finalize_and_deliver()
                    st.rerun()
        with col2:
            if st.button("✏️ もう少し直す", use_container_width=True, key="btn_edit"):
                st.session_state.deliver_confirm = False
                st.rerun()

    # deliver_confirm 中は入力欄を非表示
    if not st.session_state.deliver_confirm:
        if st.session_state.waiting_for_name:
            placeholder = "お名前を教えてください（「なし」でもOK）"
        else:
            placeholder = "ペンくんに話しかけよう…"
        user_input = st.chat_input(placeholder)
        if user_input:
            handle_user_input(user_input)


# ─────────────────────────────────────────────
# 画面: delivering
# ─────────────────────────────────────────────
def render_delivering():
    chars = st.session_state.selected_chars
    idx = st.session_state.delivered_count

    if not chars or idx >= len(chars):
        st.session_state.screen = "received"
        st.rerun()
        return

    current_char = chars[idx]
    is_penkun = current_char.get("is_penkun", False)

    render_fixed_header([])

    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #b8ddf0 0%, #c8e8b8 100%) !important; }
        @keyframes penRun {
            0%   { left: -60px; opacity: 0; }
            8%   { opacity: 1; }
            92%  { opacity: 1; }
            100% { left: 110%; opacity: 0; }
        }
        .pen-run {
            position: fixed; bottom: 40px; font-size: 48px;
            animation: penRun 3.2s linear forwards; z-index: 999;
        }
        @keyframes letterFloat {
            0%   { left: 8%; transform: translateY(0); opacity: 0; }
            15%  { opacity: 1; }
            50%  { transform: translateY(-18px); }
            85%  { opacity: 1; }
            100% { left: 82%; transform: translateY(0); opacity: 0; }
        }
        .letter-float {
            position: fixed; bottom: 90px; font-size: 28px;
            animation: letterFloat 3.2s ease-in-out forwards; z-index: 998;
        }
        </style>
        <div class="pen-run">🐧</div>
        <div class="letter-float">✉️</div>
        """,
        unsafe_allow_html=True,
    )

    status_box = st.empty()
    _DELIVER_STATUS_STYLE = (
        'position:fixed;top:42%;left:0;right:0;'
        'text-align:center;z-index:997;pointer-events:none;'
    )

    def run_animation():
        if is_penkun:
            status_box.markdown(
                f'<div style="{_DELIVER_STATUS_STYLE}">'
                '<span style="font-size:1.5em;font-weight:700;color:#2c7a9a;">配達中... 🐧 ✉️</span><br>'
                '<span style="color:#5a9ab5;font-size:0.95em;">ゆるゆる郵便局へ…</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            time.sleep(1.2)
            status_box.markdown(
                f'<div style="{_DELIVER_STATUS_STYLE}">'
                '<span style="font-size:1.5em;font-weight:700;color:#2c7a9a;">……あれ？ 😱</span><br>'
                '<span style="color:#5a9ab5;font-size:0.95em;">この宛先…ぼく…？！</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            time.sleep(1.0)
            status_box.markdown(
                f'<div style="{_DELIVER_STATUS_STYLE}">'
                '<span style="font-size:1.5em;font-weight:700;color:#2c7a9a;">（こっそりポストへ）</span><br>'
                '<span style="color:#5a9ab5;font-size:0.95em;">///  …受け取りました  ///</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            time.sleep(0.8)
        else:
            status_box.markdown(
                f'<div style="{_DELIVER_STATUS_STYLE}">'
                f'<span style="font-size:1.5em;font-weight:700;color:#2c7a9a;">配達中... 🐧 ✉️</span><br>'
                f'<span style="color:#5a9ab5;font-size:0.95em;">'
                f'{current_char["emoji"]} {current_char["name"]}のおうちへ！</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            time.sleep(2.0)
            status_box.markdown(
                f'<div style="{_DELIVER_STATUS_STYLE}">'
                f'<span style="font-size:1.5em;font-weight:700;color:#2c7a9a;">'
                f'{current_char["house"]} 到着！</span><br>'
                f'<span style="color:#5a9ab5;font-size:0.95em;">'
                f'{current_char["emoji"]} {current_char["name"]} に手紙を届けています…</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            time.sleep(1.5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_reaction = executor.submit(
            generate_reaction,
            current_char,
            st.session_state.letter_body,
            st.session_state.sender_name,
        )
        run_animation()
        reaction_text = future_reaction.result()

    st.session_state.reactions.append({"char": current_char, "text": reaction_text})
    st.session_state.delivered_count = idx + 1
    st.session_state.viewing_idx = idx
    st.session_state.screen = "received"
    st.rerun()


# ─────────────────────────────────────────────
# 画面: received
# ─────────────────────────────────────────────
def render_received():
    st.markdown(
        '<style>.stApp{background-color:#fce8f0 !important;}</style>',
        unsafe_allow_html=True,
    )

    idx = st.session_state.viewing_idx

    if idx >= len(st.session_state.reactions):
        st.session_state.screen = "compose"
        st.rerun()
        return

    reaction = st.session_state.reactions[idx]
    char = reaction["char"]

    render_fixed_header([])

    letter_body_safe = he(st.session_state.letter_body).replace("<br>", "\n")
    letter_display = (
        st.session_state.letter_body
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    st.markdown(
        f'<div style="text-align:center;padding:20px 0 12px 0;">'
        f'<div style="font-size:64px;line-height:1.2;">{char["house"]}</div>'
        f'<h2 style="margin:8px 0 4px 0;color:#333;font-size:1.4em;">'
        f'{char["name"]}のおうち</h2>'
        f'<p style="color:#aaa;font-size:12px;margin:0;">📍 {char["address"]}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    with st.expander("📨 届いたお手紙", expanded=True):
        st.markdown(
            f'<div style="white-space:pre-wrap;font-size:14px;line-height:1.9;color:#555;'
            f'background:#fffde7;border-radius:8px;padding:12px 16px;">'
            f'{letter_display}</div>',
            unsafe_allow_html=True,
        )

    reaction_text = (
        reaction["text"]
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    st.markdown(
        f'<div style="background:#f0f4f8;border-radius:12px;'
        f'padding:14px 18px;margin:10px 0 0 0;font-size:14px;line-height:1.8;color:#333;">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        f'<span style="font-size:28px;">{char["emoji"]}</span>'
        f'<strong style="color:#3d6cb5;font-size:15px;">{char["name"]}の感想</strong>'
        f'</div>'
        f'<div style="white-space:pre-wrap;">{reaction_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    chars = st.session_state.selected_chars
    next_idx = idx + 1
    all_delivered = st.session_state.delivered_count >= len(chars)

    if len(chars) == 2 and all_delivered:
        st.markdown("---")
        col1, col2 = st.columns(2)
        for i, c in enumerate(chars):
            with (col1 if i == 0 else col2):
                btn_type = "primary" if i == idx else "secondary"
                if st.button(
                    f"{c['emoji']} {c['name']}",
                    key=f"tab_char_{i}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    st.session_state.viewing_idx = i
                    st.rerun()
        st.markdown("")
        if st.button("✏️ また書く", use_container_width=True):
            st.session_state.screen = "returning"
            st.rerun()

    elif next_idx < len(chars) and st.session_state.delivered_count == next_idx:
        next_char = chars[next_idx]
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                f"✈️ {next_char['emoji']} {next_char['name']}にも届ける",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.screen = "delivering"
                st.rerun()
        with col2:
            if st.button("✏️ また書く", use_container_width=True):
                st.session_state.screen = "returning"
                st.rerun()

    else:
        if st.button("✏️ また書く", use_container_width=True, type="primary"):
            st.session_state.screen = "returning"
            st.rerun()


# ─────────────────────────────────────────────
# 画面: returning
# ─────────────────────────────────────────────
def render_returning():
    st.markdown(
        """
        <style>
        .stApp { background-color: #ede8f7 !important; }
        @keyframes penReturn {
            0%   { left: 110%; opacity: 0; }
            8%   { opacity: 1; }
            92%  { opacity: 1; }
            100% { left: -60px; opacity: 0; }
        }
        .pen-return {
            position: fixed; bottom: 40px; font-size: 48px;
            animation: penReturn 3.2s linear forwards; z-index: 999;
            transform: scaleX(-1);
        }
        </style>
        <div class="pen-return">🐧</div>
        """,
        unsafe_allow_html=True,
    )
    render_fixed_header([])

    box = st.empty()
    _RETURN_STATUS_STYLE = (
        'position:fixed;top:42%;left:0;right:0;'
        'text-align:center;z-index:997;pointer-events:none;'
    )
    box.markdown(
        f'<div style="{_RETURN_STATUS_STYLE}">'
        '<span style="font-size:1.5em;font-weight:700;color:#6b5b9a;">配達完了！🎉</span><br>'
        '<span style="color:#9a88cc;font-size:0.95em;">ゆるゆる郵便局に帰ります🏣</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    time.sleep(1.5)
    box.markdown(
        f'<div style="{_RETURN_STATUS_STYLE}">'
        '<span style="font-size:1.5em;font-weight:700;color:#6b5b9a;">ただいま〜！🐧</span><br>'
        '<span style="color:#9a88cc;font-size:0.95em;">次のお手紙も待ってるよ✉️</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    time.sleep(1.0)

    prev_name = st.session_state.get("sender_name")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session()
    if prev_name is not None:
        st.session_state.sender_name = prev_name

    st.rerun()


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="ゆるゆる郵便屋さん",
        page_icon="🐧",
        layout="centered",
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Noto Sans JP', sans-serif !important;
        }
        .stApp { background-color: #e4f0fa; }

        #MainMenu { visibility: hidden; }
        header { visibility: hidden; }
        footer { visibility: hidden; }

        /* 固定ヘッダー分の上余白はrender_fixed_headerで動的に設定 */
        .block-container {
            padding-bottom: 5rem !important;
        }

        /* iPhone Safari の「Manage app」ボタン分の余白 */
        .stBottom {
            padding-bottom: 48px !important;
        }

        /* ボタン共通 */
        .stButton button {
            border-radius: 10px !important;
            font-family: 'Noto Sans JP', sans-serif !important;
            font-size: 14px !important;
            transition: all 0.15s ease !important;
        }

        /* チャット入力欄を見やすく */
        [data-testid="stChatInput"] {
            background-color: #ffffff !important;
            border: 1.5px solid #7aadcc !important;
            border-radius: 12px !important;
        }
        [data-testid="stChatInput"] textarea {
            background-color: #ffffff !important;
        }
        .stBottom > div {
            background-color: #e4f0fa !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    init_session()

    screen = st.session_state.screen
    if screen == "compose":
        render_compose()
    elif screen == "delivering":
        render_delivering()
    elif screen == "received":
        render_received()
    elif screen == "returning":
        render_returning()


if __name__ == "__main__":
    main()
