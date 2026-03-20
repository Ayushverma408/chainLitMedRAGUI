"""
Medical RAG Chat UI
Searches across all ingested medical textbooks simultaneously.

Run backend first:
    cd ../advanced-rag-poc
    venv/bin/uvicorn src.api:app --port 8000

Then run this:
    cd ../surgery-rag-ui
    chainlit run app.py
"""

import json
import os
import httpx
import chainlit as cl
from chainlit.input_widget import Switch

API_URL = "http://localhost:8000"


def speed_label(total: float) -> str:
    if total < 3:
        return "🟢"
    elif total < 7:
        return "🟡"
    return "🔴"


def build_perf_footer(t_ret: float, t_llm: float, t_tot: float, chunks: list[dict]) -> str:
    seen = set()
    cites = []
    for c in chunks:
        label = f"{c['source']} p.{c['page']}" if c.get("source") else f"p.{c['page']}"
        if label not in seen:
            seen.add(label)
            cites.append(label)
    sources_str = "  ·  ".join(cites)
    return (
        f"\n\n---\n"
        f"{speed_label(t_tot)} **{t_tot:.2f}s** total  ·  "
        f"📥 retrieval **{t_ret:.2f}s**  ·  "
        f"🤖 LLM **{t_llm:.2f}s**\n\n"
        f"📄 {sources_str}"
    )


def build_sources_content(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page    = chunk["page"]
        source  = chunk.get("source", "")
        content = chunk["content"].strip()
        quoted  = content.replace("\n", "\n> ")
        label   = f"{source}, Page {page}" if source else f"Page {page}"
        parts.append(f"**[{i}] {label}**\n\n> {quoted}")
    return "\n\n---\n\n".join(parts)


@cl.on_settings_update
async def on_settings_update(settings: dict):
    free_mode = settings.get("free_mode", False)
    cl.user_session.set("free_mode", free_mode)
    if free_mode:
        await cl.Message(
            content="🔓 **Free Mode ON** — GPT-4o will answer from its own knowledge. RAG is paused."
        ).send()
    else:
        await cl.Message(
            content="📚 **RAG Mode ON** — answers grounded in your medical textbooks."
        ).send()


@cl.on_chat_start
async def on_chat_start():
    await cl.ChatSettings([
        Switch(
            id="free_mode",
            label="🔓 Free Mode (bypass RAG — GPT-4o answers freely)",
            initial=False,
        )
    ]).send()
    cl.user_session.set("free_mode", False)

    try:
        resp = httpx.get(f"{API_URL}/health", timeout=5)
        info = resp.json()
        pipeline = info.get("pipeline", "unknown")
    except Exception:
        await cl.Message(
            content=(
                "⚠️ **Backend not running.** Start it first:\n"
                "```bash\ncd advanced-rag-poc\n"
                "venv/bin/uvicorn src.api:app --port 8000\n```"
            )
        ).send()
        return

    try:
        resp  = httpx.get(f"{API_URL}/books", timeout=5)
        books = resp.json()
        book_names = " · ".join(f"**{b['display_name']}**" for b in books)
    except Exception:
        book_names = "all medical books"

    await cl.Message(
        content=(
            f"## 🏥 Medical Library\n"
            f"Searching across: {book_names}\n\n"
            f"**Pipeline:** `{pipeline}` · **Model:** `GPT-4o`\n\n"
            f"Ask anything. Answers are grounded in your textbooks with book name + page citations.\n\n"
            f"💡 After each answer, click any **📄 View page** button to see the exact PDF page."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    question  = message.content.strip()
    free_mode = cl.user_session.get("free_mode", False)
    if not question:
        return

    msg = cl.Message(content="🧠  Thinking...")
    await msg.send()

    chunks = []
    data   = None

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{API_URL}/query/stream",
                json={"question": question, "free_mode": free_mode},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])
                    phase = event["phase"]

                    if phase == "retrieving":
                        msg.content = "📖  Searching through the medical library..." if not free_mode else "🧠  Asking GPT-4o..."
                        await msg.update()

                    elif phase == "retrieved":
                        n = len(event.get("chunks", []))
                        msg.content = f"⚡  Found {n} passages — shortlisting the best ones..."
                        await msg.update()
                        chunks = event.get("chunks", [])

                    elif phase == "generating":
                        msg.content = "✍️  Crafting your answer..."
                        await msg.update()

                    elif phase == "done":
                        data = event

                    elif phase == "error":
                        msg.content = f"⚠️ {event.get('msg', 'Something went wrong.')}"
                        await msg.update()
                        return

    except httpx.TimeoutException:
        msg.content = "⚠️ Request timed out. Try again."
        await msg.update()
        return
    except Exception as e:
        msg.content = f"⚠️ Error: {e}"
        await msg.update()
        return

    if not data:
        msg.content = "⚠️ No response received."
        await msg.update()
        return

    t_ret  = data["latency_retrieval_s"]
    t_llm  = data["latency_llm_s"]
    t_tot  = data["latency_total_s"]
    answer = data["answer"]

    perf_footer     = build_perf_footer(t_ret, t_llm, t_tot, data["chunks"])
    sources_content = build_sources_content(data["chunks"])

    elements = []
    if data["chunks"]:
        elements.append(cl.Text(
            name=f"📚 Sources  ·  {len(data['chunks'])} passages retrieved",
            content=sources_content,
            display="inline",
        ))

    for img in data.get("images", [])[:6]:
        img_path = img.get("path", "") if isinstance(img, dict) else img
        caption  = img.get("caption", "") if isinstance(img, dict) else ""
        if img_path and os.path.exists(img_path):
            basename = os.path.basename(img_path)
            try:
                page_num = basename.split("page_")[1].split("_img_")[0]
                fallback = f"Page {page_num}"
            except IndexError:
                fallback = basename
            elements.append(
                cl.Image(path=img_path, name=caption if caption else fallback, display="inline")
            )

    # ── Page preview action buttons — one per unique (collection, page) ───────
    seen_keys = set()
    actions   = []
    for chunk in data["chunks"]:
        collection = chunk.get("collection", "")
        page       = chunk.get("page")
        source     = chunk.get("source", "")
        key        = f"{collection}:{page}"
        if collection and isinstance(page, int) and key not in seen_keys:
            seen_keys.add(key)
            actions.append(
                cl.Action(
                    name="view_page",
                    payload={"collection": collection, "page": page, "source": source},
                    label=f"📄 {source}, p.{page}",
                )
            )

    await msg.remove()
    await cl.Message(
        content=answer + perf_footer,
        elements=elements,
        actions=actions,
    ).send()


@cl.action_callback("view_page")
async def on_view_page(action: cl.Action):
    """Fetch and display the PDF page (±1) for the selected chunk."""
    collection = action.payload["collection"]
    page_num   = action.payload["page"]
    source     = action.payload.get("source", "")

    pages_to_fetch = [p for p in [page_num - 1, page_num, page_num + 1] if p > 0]

    elements = []
    async with httpx.AsyncClient(timeout=30) as client:
        for p in pages_to_fetch:
            url = f"{API_URL}/page/{collection}/{p}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    label = (
                        f"◀ Page {p}" if p < page_num
                        else (f"▶ Page {p}" if p > page_num else f"Page {p}  ← selected")
                    )
                    elements.append(
                        cl.Image(content=resp.content, name=label, display="inline")
                    )
            except Exception:
                pass

    if elements:
        await cl.Message(
            content=f"**PDF preview** — {source}, p.{page_num}",
            elements=elements,
        ).send()
    else:
        await cl.Message(content="⚠️ Could not load page preview.").send()
