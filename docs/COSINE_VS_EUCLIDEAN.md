# Cosine vs Euclidean Distance for Text Embeddings

## What is an embedding?

When OpenAI's `text-embedding-3-small` model processes a sentence,
it outputs a list of 1536 numbers — a vector.

That vector is a **point in 1536-dimensional space**.
The model is trained so that sentences with similar meaning
end up at points that are geometrically close to each other.

The question is: what does "close" mean?

---

## Two ways to measure distance between two vectors

### Euclidean distance — straight-line distance

Euclidean distance is the length of the straight line between two points.
It's the distance you'd measure with a ruler.

```
Point A ●
         \
          \  ← Euclidean distance (length of this line)
           \
            ● Point B
```

Formula for 2D: `√((x₂-x₁)² + (y₂-y₁)²)`

This is what you learned in school as "the distance between two points."

---

### Cosine distance — angle between two vectors

Cosine similarity measures the **angle** between two vectors,
not the distance between their endpoints.

Both vectors are drawn from the origin (0, 0, 0...).
Cosine similarity asks: are they pointing in the same direction?

```
          B
         ↗
        /  ← small angle = high cosine similarity
       /
      ↗ A
  origin
```

```
     B
     ↑
     |
     |  ← large angle = low cosine similarity
     |
     +----→ A
  origin
```

Cosine similarity = `cos(θ)` where θ is the angle between the two vectors.

| Angle | cos(θ) | Meaning |
|---|---|---|
| 0° | 1.0 | Identical direction — same meaning |
| 45° | ~0.7 | Similar direction — related meaning |
| 90° | 0.0 | Perpendicular — unrelated |
| 180° | -1.0 | Opposite direction — opposite meaning |

Cosine **distance** = `1 - cosine similarity`
(So distance 0 = identical, distance 1 = unrelated.)

---

## Why cosine is better for text embeddings

### The problem with Euclidean distance: magnitude

Euclidean distance is sensitive to the **length** of each vector, not just its direction.

Consider two transcripts about machine learning:
- Transcript A: a 10-second clip — short summary → shorter vector magnitude
- Transcript B: a 10-minute deep-dive — long explanation → larger vector magnitude

Both are about the same topic. Their vectors point in the same direction.
But Transcript B's vector is much longer.

```
         B (long vector, same topic)
        ↗↗↗↗↗↗
       /
      ↗ A (short vector, same topic)
  origin
```

Euclidean distance sees these as far apart because B is a long way from A
in raw distance — even though they're about identical topics.

Cosine similarity ignores magnitude entirely. It only cares about direction.
Both vectors point the same way → similarity score close to 1.0.
Correct: they're about the same thing.

---

### What determines vector magnitude in text embeddings?

Vector magnitude in raw embeddings loosely correlates with the amount of
semantic content. A longer, more detailed text produces a larger-magnitude
vector than a short one about the same topic.

This is irrelevant to semantic similarity. Cosine similarity removes it.

---

### Cosine distance is what OpenAI embeddings are designed for

OpenAI explicitly states in their documentation that their embedding models
are optimised for cosine similarity. The training objective pushes similar
texts toward the same **direction** in embedding space, not the same
**point**.

Using Euclidean distance with OpenAI embeddings produces worse results —
not because it's wrong in general, but because the model wasn't trained
to make Euclidean distance meaningful.

---

## Concrete example

Suppose you store a reel transcript about "how to build better habits."

Later a user asks: "What did I learn about morning routines?"

The two texts share no keywords. But their embeddings point in a similar
direction (personal development, behaviour change, daily structure).

Cosine similarity: **0.87** → correctly returned as a top result.

Euclidean distance might rank it lower because the question is much shorter
than the transcript, so the vectors have very different magnitudes despite
pointing in the same direction.

---

## Summary

| | Euclidean | Cosine |
|---|---|---|
| Measures | Length of straight line between points | Angle between vectors from origin |
| Sensitive to vector length | Yes | No |
| Good for | Physical coordinates, pixel distances | Text, document, sentence similarity |
| Used in this project | No | Yes — set in `VectorParams(distance=Distance.COSINE)` |

---

## See also

- [`SIMILARITY_SCORES.md`](SIMILARITY_SCORES.md) — what scores of 0.9 vs 0.5 mean in practice
