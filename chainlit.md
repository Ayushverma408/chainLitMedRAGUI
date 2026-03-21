# 🏥 Medical Library — RAG Assistant

Not your average AI chatbot. Every answer is **retrieved directly from 4 surgical textbooks** — grounded, cited, and traceable to the exact page. One click away from the original PDF.

---

## 📚 Books Indexed

Searching all four simultaneously on every question:

- **Fischer's Mastery of Surgery** — 8th Edition (~36k chunks)
- **Sabiston Textbook of Surgery** — 22nd Edition (~25k chunks)
- **Shackelford's Surgery of the Alimentary Tract** — 9th Edition (~19k chunks)
- **Blumgart's Surgery of the Liver, Biliary Tract and Pancreas** (~21k chunks)

~101,000 chunks. Every answer draws from whichever book has the best passage for your question.

---

## ⚙️ Choose Your Mode

Click the **settings gear** in the sidebar to switch modes at any time — even mid-session, without losing your conversation.

### 🏆 HyDE — Best Quality (~8-12s)
Before searching, GPT-4o writes a short hypothetical passage the textbook *would* contain to answer your question. That hypothetical is then used for retrieval — bridging the gap between how you ask questions and how textbooks are written. **Highest accuracy. Use this by default.**

### ⚡ Fast — Nearly as Good, Less Wait (~4-6s)
Skips the HyDE step. Your query is embedded directly and retrieval runs immediately. Based on evaluation across surgical questions, Fast mode is only **3-4% less accurate than HyDE** — for most revision questions you won't notice a difference. **Good for quick lookups.**

### 🔓 Free — No Textbook Grounding (~3-5s)
Bypasses retrieval entirely. GPT-4o answers from its own training knowledge — no page citations, no textbook grounding. **Use this when your question is outside the scope of the books** — general anatomy, broad medical concepts, exam strategy, or anything you just want a quick ungrounded answer on. Not suitable when textbook accuracy matters.

> Modes are interchangeable mid-session. Switch freely — your conversation history is always preserved.

---

## 📄 PDF Page Preview — The Highlight

After every answer, a **📄 button appears for each retrieved chunk**, labelled with book and page number.

**Click any button and:**
- The exact PDF page renders as an image instantly
- The **chunk text is highlighted in yellow** on the page — you see exactly where in the page your answer came from
- Pages for **all other retrieved chunks load in the same gallery** — every source, one click, no back and forth
- ±1 surrounding pages load for the chunk you clicked, so you have full context

This is the fastest way to get from an AI answer to the original textbook — one click.

---

## 🖼️ Extracted Figures

Diagrams, illustrations, and figures are extracted from the PDFs at index time. After an answer, if any retrieved pages contain figures, a **`🖼️ Show figures (N)`** button appears. Click it to load them — kept hidden by default so the answer stays clean.

---

## 🔬 How the Pipeline Works

```
Your Question
     ↓
  [HyDE — optional]       ← GPT-4o writes a hypothetical textbook passage
     ↓
  Embed query + HyDE      ← 2 embedding calls, run in parallel
     ↓
  4 books in parallel     ← dense(HyDE) + dense(query) + BM25 per book
     ↓
  Global RRF merge        ← best passages across all books ranked together
     ↓
  Cross-Encoder Rerank    ← ML model picks the top 6 most relevant chunks
     ↓
  GPT-4o Generation       ← answers strictly from retrieved context
     ↓
  Answer + Citations + 📄 Page buttons
```

Every answer includes a timing breakdown so you can see exactly where the time went:
```
🟡 9.2s total  ·  📥 retrieval 4.1s (↳ HyDE 3.2s · embed 0.4s · search 0.3s · rerank 0.2s)  ·  🤖 LLM 5.1s
```

**Model:** GPT-4o · **HyDE:** GPT-4o-mini · **Embeddings:** text-embedding-3-small · **Reranker:** ms-marco-MiniLM-L-6-v2
