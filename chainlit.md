# 📚 Book Intelligence — Advanced RAG Assistant

Not your average AI chatbot. Every answer here is **retrieved directly from the book you select** — grounded, cited, and traceable to the exact page.

---

## 🔬 How It Actually Works

Most AI tools send your question straight to an LLM and hope for the best. We don't.

Your question goes through a **5-stage retrieval pipeline** before a single word of the answer is written:

| Stage | What's happening |
|---|---|
| **1. HyDE** | GPT-4o imagines what a perfect answer from the book would look like, then searches using *that* — not your raw question. This bridges the gap between how you ask and how books are written. |
| **2. Dense Search** | Your question is converted into a semantic vector and matched against every chunk of the book using cosine similarity. Captures *meaning*, not just keywords. |
| **3. Sparse Search (BM25)** | Classic keyword matching runs in parallel. Catches exact terms, proper nouns, drug names, procedure names — things semantic search sometimes misses. |
| **4. Reciprocal Rank Fusion** | Both result lists are merged using a ranking algorithm that rewards chunks appearing highly in *both* lists. Best of both worlds. |
| **5. Cross-Encoder Reranking** | A dedicated ML model reads each (question, passage) pair together and rescores them for true relevance. Far more accurate than embedding similarity alone. |

Only after all five stages does GPT-4o synthesise the final answer — using **only** what was retrieved. No hallucination. No prior knowledge. Just the book.

---

## 🏥 Built for Medical Accuracy

This system was purpose-built for **Fischer's Mastery of Surgery (8th Edition)** and similar high-stakes reference material where a wrong answer is not an option.

Every response:
- Cites the **exact page number** of every claim
- Refuses to speculate beyond what the retrieved text says
- Tells you clearly if the information isn't in the retrieved sections

---

## 🚀 Getting Started

1. **Select your book** from the dropdown at the top
2. **Ask anything** — specific clinical questions, broad concepts, procedure steps
3. Watch the pipeline work in real time as your answer is retrieved and generated
4. Click **📚 Knowledge source** below any answer to inspect the exact passages used

---

## ⚡ Pipeline at a Glance

```
Your Question
     ↓
  HyDE Generation          ← GPT-4o writes a hypothetical answer
     ↓
  Dense + Sparse Search    ← Semantic vectors + BM25 keyword match
     ↓
  RRF Merge                ← Best passages from both lists combined
     ↓
  Cross-Encoder Rerank     ← ML model picks the most relevant 6
     ↓
  GPT-4o Generation        ← Answers strictly from retrieved context
     ↓
  Your Answer + Citations
```

**Model:** GPT-4o · **Embeddings:** text-embedding-3-small · **Reranker:** ms-marco-MiniLM-L-6-v2
