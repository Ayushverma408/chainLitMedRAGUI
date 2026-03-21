# Surgery RAG UI

Chainlit frontend for the Medical RAG stack. Streams answers from the `advanced-rag-poc` FastAPI backend across 4 surgical textbooks simultaneously.

**Backend repo:** [AdvancedRAG](https://github.com/Ayushverma408/AdvancedRAG)

---

## Running

```bash
# Start everything (recommended)
cd ../advanced-rag-poc
./medrag.sh

# Or manually
cd surgery-rag-ui
venv/bin/chainlit run app.py --port 7860
```

- UI: http://localhost:7860
- Public: https://medrag.shuf.site (Cloudflare tunnel)

---

## Features

### Pipeline mode toggle

Settings gear (⚙️) in the sidebar switches between three modes:

| Mode | Description | Latency |
|---|---|---|
| 🏆 **HyDE** | Generates a hypothetical textbook passage first, uses it to retrieve better chunks. Best quality. | ~8-12s |
| ⚡ **Fast** | Skips HyDE, embeds your query directly. Slightly lower recall, much faster. | ~4-6s |
| 🔓 **Free** | No RAG — GPT-4o answers from its own knowledge, no textbook grounding. | ~3-5s |

### Answers

- Grounded in retrieved chunks from all 4 textbooks
- Citations in the form `Fischer's Mastery of Surgery, p.1234`
- Performance footer after every answer:
  ```
  🟡 9.2s total  ·  📥 retrieval 4.1s (↳ HyDE 3.2s · embed 0.4s · search 0.3s · rerank 0.2s)  ·  🤖 LLM 5.1s  ·  🏆 HyDE
  ```
- Speed indicator: 🟢 <3s · 🟡 3-7s · 🔴 >7s

### 📄 Page preview buttons

One button per retrieved chunk. Clicking any button:
- Fetches ±1 pages around the selected chunk (for context)
- Fetches single pages for all other retrieved chunks
- All pages load concurrently in one gallery message
- Selected chunk text is **highlighted in yellow** on the PDF

### 🖼️ Show figures

Book figures extracted at ingest time are hidden by default. If figures exist for the answer, a `🖼️ Show figures (N)` button appears — click to load them on demand.

### Sources panel

Expandable inline text panel with all retrieved chunks, labelled by book and page number.

---

## Changelog

### v2 — March 2026

- **Pipeline mode selector** replacing the free/RAG toggle — HyDE / Fast / Free modes
- **Sub-timing breakdown** in perf footer (HyDE / embed / search / rerank)
- **Gallery page preview** — all retrieved chunks open in one concurrent message instead of one-at-a-time
- **Yellow highlight** on selected chunk text in PDF page preview
- **Extracted figures hidden by default** — shown only via `🖼️ Show figures` button

### v1

- Multi-book search across Fischer, Sabiston, Shackelford, Blumgart
- Streaming SSE responses from FastAPI backend
- Page preview buttons per retrieved chunk
- Inline sources panel with chunk text
- Free mode toggle (bypasses RAG)
