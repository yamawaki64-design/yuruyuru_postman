# Groqモデル移行時の注意事項

Groqのモデルを変更する際は以下を確認すること。ゆるゆるシリーズ共通。

---

## 廃止予定モデル（要注意）

以下のモデルは廃止予定のため、新規採用・フォールバック先としても使わないこと。

- `llama-3.3-70b-versatile`
- `llama-3.1-8b-instant`

軽量・低コスト用途の代替としては `openai/gpt-oss-20b` を検討する（reasoning_effort="low"指定で高速・低コストに寄せられる）。

---

## 推論モデル（reasoning model）固有の挙動

`openai/gpt-oss-*` などの推論モデルは、通常モデルと **レスポンス構造が異なる**。

| 項目 | 通常モデル（llama等） | 推論モデル（gpt-oss等） |
|---|---|---|
| 思考プロセス | なし | `message.reasoning` フィールドに出力 |
| 最終回答 | `message.content` | `message.content`（同じ） |
| トークン消費 | `max_tokens` = 回答分のみ | `max_tokens` = 推論＋回答の合計 |

---

## max_tokens の設定（重要）

推論モデルは `max_tokens` を推論と回答の両方で消費する。
**小さい値（200 等）では推論だけでトークンを使い切り、`content` が空になる。**

```python
# NG: 推論モデルでは推論だけで消費してしまい content が空になる
max_tokens=200

# OK: 推論 + 回答分を確保する
max_tokens=1024
```

---

## 症状と診断方法

`content` が空のまま返ってきてフォールバック文言しか出ない場合は以下をログで確認する。

```python
choice = resp.choices[0]
print(f"finish_reason: {choice.finish_reason!r}")
print(f"message fields: {vars(choice.message)}")
print(f"raw content: {choice.message.content!r}")
```

| ログの内容 | 原因 | 対処 |
|---|---|---|
| `finish_reason: 'length'` かつ `content: ''` | max_tokens 不足 | max_tokens を増やす（1024以上） |
| `reasoning` フィールドに思考が入っている | 推論モデル確認 | max_tokens を増やす |
| `finish_reason: 'content_filter'` | コンテンツフィルタ | プロンプトを見直す |

---

## reasoning_effort（重要・実例あり）

`openai/gpt-oss-*` はプロンプトが複雑だと、思考（`reasoning`）だけで `max_tokens` を使い切ることがある。
実例：文字数制限（200文字以内など）を守らせようとして、モデルが**1文字ずつ数える思考ログ**を延々出力し、`max_tokens=1024` でも `finish_reason: 'length'` で `content` が空になった。

対処として `reasoning_effort` を指定し、思考の冗長さ自体を抑える（`max_tokens` を増やすより効果的な場合が多い）。

```python
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[...],
    max_tokens=1024,
    reasoning_effort="low",  # gpt-oss-20b/120b は low / medium(既定) / high
)
```

短いセリフ生成・単純なJSON整形など「最終出力が短くタスクも単純」な用途では `"low"` を第一候補にする。
複雑な推論が必要なタスクでは `"medium"`（既定）や `"high"` を検討する。

---

## レスポンスのクリーニング

モデルによって JSON 以外のテキストが混入する場合がある。以下の除去処理を入れておくこと。

```python
# thinkingブロック除去
cleaned = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", raw, flags=re.DOTALL)
# バッククォートブロック・jsonプレフィックス除去
cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
cleaned = cleaned.replace("```", "").strip()
# JSONを抽出
m = re.search(r"\{.*\}", cleaned, re.DOTALL)
```
