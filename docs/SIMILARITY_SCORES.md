# Understanding Similarity Scores

## What the score is

When `search_reels(query)` returns results, each hit has a `score` field.

```python
{"text": "...", "topic": "Health", "score": 0.91}
```

This score is the **cosine similarity** between the query vector and the
stored vector. It is a number between -1 and 1, but in practice for
same-language text comparisons it almost always falls between 0 and 1.

---

## The scale

```
  0.0          0.3          0.5          0.7          0.9         1.0
   |------------|------------|------------|------------|------------|
 unrelated    loosely      somewhat     related     very        identical
              related      related                  similar
```

| Score range | What it means | Real example |
|---|---|---|
| `0.95 – 1.0` | Near-identical meaning | Same sentence rephrased slightly |
| `0.85 – 0.94` | Very similar topic and intent | "morning routines" vs "daily habits" |
| `0.70 – 0.84` | Clearly related, same domain | "sleep quality" vs "recovery after exercise" |
| `0.50 – 0.69` | Loosely related | "productivity" vs "time management tools" |
| `0.30 – 0.49` | Weak connection | "nutrition" vs "software engineering" |
| `0.00 – 0.29` | Essentially unrelated | "cooking recipes" vs "quantum physics" |

---

## 0.9 vs 0.5 — the practical difference

### Score: 0.9

```
Query:  "What did I learn about building habits?"
Result: "The transcript covers habit formation, the 21-day myth, 
         and James Clear's approach to small daily improvements."
Score:  0.91
```

This is a strong match. The query and the stored text are about the same
concept. You would return this to the user and it would feel correct.

A 0.9 score means the angle between the two vectors is about 26°.
They are pointing in nearly the same direction in embedding space.

```
    result ↗
           ↗  ← ~26° apart
          ↗
query ↗
```

---

### Score: 0.5

```
Query:  "What did I learn about building habits?"
Result: "This reel explains the history of the Roman Colosseum 
         and its construction techniques."
Score:  0.51
```

This is a weak match — the model found some loose structural similarity
(both are about "building" something, perhaps) but the actual topics
are unrelated. You would not want to return this to a user as a
relevant answer.

A 0.5 score means the angle between the vectors is about 60°.
They are pointing in noticeably different directions.

```
   result ↗
         /
        /  ← ~60° apart
       /
query →
```

---

## Where to set your threshold

In `search_reels()`, Qdrant returns the top `limit` results regardless
of score. It is your code's job to filter by score if needed.

Recommended thresholds for this project:

| Use case | Suggested minimum score |
|---|---|
| Answer a question from saved reels | `≥ 0.75` |
| Show "related reels" suggestions | `≥ 0.65` |
| Loose topic grouping | `≥ 0.50` |
| No threshold (return everything) | not recommended |

Example — filter low-confidence results before replying:

```python
results = search_reels("sleep and recovery", limit=5)
relevant = [r for r in results if r["score"] >= 0.75]

if not relevant:
    reply("I haven't saved any reels closely related to that topic yet.")
else:
    reply(format_results(relevant))
```

---

## Why you almost never see scores below 0.2

Random text in the same language and domain tends to share some vocabulary,
grammatical patterns, and topic overlap even when unrelated.
OpenAI embeddings reflect this — they cluster same-language content
above 0 even when the topics are completely different.

True negative scores (-1 to 0) would require vectors pointing in opposite
directions. This almost never happens with natural language from the same
domain because there's no natural "opposite" of a reel transcript.

---

## One-sentence summary

A score of **0.9** means "these two pieces of text are about the same thing."
A score of **0.5** means "these two pieces of text share a vague connection
but are probably not what the user is looking for."
