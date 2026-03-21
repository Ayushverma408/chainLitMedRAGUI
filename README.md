# Medical RAG — Chainlit UI

A Chainlit-based chat interface for querying 4 surgical textbooks simultaneously. Built on top of a multi-book HyDE RAG pipeline — answers are grounded in retrieved passages and cited with book name + page number.

**Backend repo:** [AdvancedRAG](https://github.com/Ayushverma408/AdvancedRAG)

---

## Running

```bash
# Start everything (recommended) — kills existing, starts API + UI, opens browser, starts Cloudflare tunnel
cd ../advanced-rag-poc
./medrag.sh

# Stop everything
./medrag.sh stop

# Or run UI manually
cd surgery-rag-ui
venv/bin/chainlit run app.py --port 7860
```

- **Local:** http://localhost:7860
- **Public:** https://medrag.shuf.site (Cloudflare tunnel)

---

## Pipeline Modes

Click the **⚙️ settings gear** in the sidebar to switch modes at any time. You can switch freely between modes mid-session — your conversation context is never lost.

### 🏆 HyDE — Best Quality (~8-12s)

The default mode. Before searching the books, GPT-4o writes a short hypothetical passage the textbook *would* contain to answer your question. That hypothetical passage is then embedded and used to find the most relevant chunks — bridging the gap between how you ask questions and how textbooks write answers.

**When to use:** Any clinical or exam question where accuracy matters. Highest faithfulness score in evaluation (0.97).

### ⚡ Fast — Nearly as Good, Less Wait (~4-6s)

Skips the HyDE generation step. Your query is embedded directly and retrieval runs immediately. Based on evaluation across 10 surgical questions, Fast mode is only **~3-4% less accurate than HyDE** on faithfulness — for most questions you won't notice a difference.

**When to use:** When you're quickly looking something up and don't need the extra ~4s. Solid choice for revision sessions.

### 🔓 Free — No Textbook Grounding (~3-5s)

Bypasses RAG entirely. GPT-4o answers directly from its own training knowledge, with no retrieval from the books. Answers will not include page citations and are not guaranteed to reflect what's written in the textbooks.

**When to use:** Questions that fall *outside* the scope of the 4 books — general medical knowledge, anatomy refreshers, exam strategy, quick definitions, or anything you just want a fast broad answer on. Not suitable when you need textbook-grounded clinical accuracy.

> You can switch between all three modes freely mid-session. The conversation history is preserved regardless of which mode you use.

---

## Highlight Features

### 📄 PDF Page Preview

After every answer, a **📄 button appears for each retrieved chunk** — labelled with the book name and page number (e.g. `📄 Fischer's Mastery of Surgery, p.842`).

**What happens when you click:**
- The exact PDF page for that chunk loads as an image
- The chunk text is **highlighted in yellow** directly on the page — so you can see exactly where in the page your answer came from
- Pages for **all other retrieved chunks** load simultaneously in the same gallery — you see every source in one place, no need to close and reopen
- ±1 surrounding pages load for the selected chunk so you have full context

This is the fastest way to go from an answer to the original textbook page — one click, no manual searching.

### 🖼️ Show Figures

At ingest time, all figures, diagrams, and illustrations are extracted from the PDFs and indexed by page. After an answer, if any retrieved pages contain figures, a **`🖼️ Show figures (N)`** button appears.

Figures are hidden by default to keep the answer clean. Click the button to load them on demand. Useful for anatomy questions, surgical technique steps, or any topic where a diagram is worth more than text.

### 📚 Sources Panel

Every answer includes an expandable **📚 Sources** panel showing the full text of every retrieved chunk, labelled by book and page. Useful when you want to read the surrounding passage rather than just the answer.

---

## Answer Format

Every answer ends with a performance footer:

```
🟡 9.2s total  ·  📥 retrieval 4.1s (↳ HyDE 3.2s · embed 0.4s · search 0.3s · rerank 0.2s)  ·  🤖 LLM 5.1s  ·  🏆 HyDE

📄 Fischer's Mastery of Surgery p.842  ·  Sabiston Textbook of Surgery p.1204
```

- Speed indicator: 🟢 under 3s · 🟡 3-7s · 🔴 over 7s
- Sub-timing breakdown for each retrieval phase
- Book + page citations for every source

---

## Books Indexed

| Book | Chunks |
|---|---|
| Fischer's Mastery of Surgery, 8th ed | ~36k |
| Sabiston Textbook of Surgery, 22nd ed | ~25k |
| Shackelford's Surgery of the Alimentary Tract, 9th ed | ~19k |
| Blumgart's Surgery of the Liver, Biliary Tract and Pancreas | ~21k |

~101,000 chunks total across all books.

---

## Changelog

### v2 — March 2026

- **Pipeline mode selector** — HyDE / Fast / Free, switchable mid-session without losing context
- **Sub-timing breakdown** in perf footer (HyDE · embed · search · rerank)
- **Gallery page preview** — all retrieved chunks open concurrently in one message
- **Yellow text highlight** on the exact chunk location within the PDF page
- **Extracted figures hidden by default** — appear only via `🖼️ Show figures` button on demand

### v1

- Multi-book search across all 4 surgical textbooks simultaneously
- Streaming SSE responses from FastAPI backend
- Page preview buttons per retrieved chunk
- Inline sources panel with full chunk text
- Free mode toggle
