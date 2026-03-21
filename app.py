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

import asyncio
import json
import os
import httpx
import chainlit as cl
from chainlit.input_widget import Select

API_URL = "http://localhost:8000"


def speed_label(total: float) -> str:
    if total < 3:
        return "🟢"
    elif total < 7:
        return "🟡"
    return "🔴"


PIPELINE_BADGE = {
    "multi-book-hyde": "🏆 HyDE",
    "multi-book-fast": "⚡ Fast",
    "free":            "🔓 Free",
}


def build_perf_footer(
    t_ret: float, t_llm: float, t_tot: float,
    chunks: list[dict], pipeline: str = "",
    t_hyde: float = 0, t_embed: float = 0,
    t_search: float = 0, t_rerank: float = 0,
) -> str:
    seen = set()
    cites = []
    for c in chunks:
        label = f"{c['source']} p.{c['page']}" if c.get("source") else f"p.{c['page']}"
        if label not in seen:
            seen.add(label)
            cites.append(label)
    sources_str = "  ·  ".join(cites)
    badge = PIPELINE_BADGE.get(pipeline, f"`{pipeline}`") if pipeline else ""

    # Build sub-timing breakdown for retrieval
    sub = []
    if t_hyde > 0:
        sub.append(f"HyDE {t_hyde:.2f}s")
    if t_embed > 0:
        sub.append(f"embed {t_embed:.2f}s")
    if t_search > 0:
        sub.append(f"search {t_search:.2f}s")
    if t_rerank > 0:
        sub.append(f"rerank {t_rerank:.2f}s")
    sub_str = f" _(↳ {' · '.join(sub)})_" if sub else ""

    badge_str = f"  ·  {badge}" if badge else ""
    return (
        f"\n\n---\n"
        f"{speed_label(t_tot)} **{t_tot:.2f}s** total  ·  "
        f"📥 retrieval **{t_ret:.2f}s**{sub_str}  ·  "
        f"🤖 LLM **{t_llm:.2f}s**{badge_str}\n\n"
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


PIPELINE_LABELS = {
    "hyde": "🏆 HyDE — Best quality (~10s). Generates a hypothetical answer first, uses it to find better chunks.",
    "fast": "⚡ Fast — Skips HyDE (~5s). Embeds your query directly. Slightly lower recall.",
    "free": "🔓 Free — No RAG. GPT-4o answers from its own knowledge, no textbook grounding.",
}


@cl.on_settings_update
async def on_settings_update(settings: dict):
    mode = settings.get("pipeline_mode", "hyde")
    cl.user_session.set("pipeline_mode", mode)
    await cl.Message(content=f"**Mode changed:** {PIPELINE_LABELS[mode]}").send()


@cl.on_chat_start
async def on_chat_start():
    await cl.ChatSettings([
        Select(
            id="pipeline_mode",
            label="Pipeline Mode",
            values=["hyde", "fast", "free"],
            initial_value="hyde",
        )
    ]).send()
    cl.user_session.set("pipeline_mode", "hyde")

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
            f"## 🩺 ScrubRef\n"
            f"Searching across: {book_names}\n\n"
            f"**Pipeline:** `{pipeline}` · **Model:** `GPT-4o`\n\n"
            f"Ask anything. Answers are grounded in your textbooks with book name + page citations.\n\n"
            f"⚙️ Use the **settings gear** to switch pipeline mode:\n"
            f"- 🏆 **HyDE** — best quality, ~10s\n"
            f"- ⚡ **Fast** — only 3-4% less accurate, ~5s\n"
            f"- 🔓 **Free** — no textbook grounding, use for questions outside the books\n\n"
            f"💡 After each answer, click any **📄 page button** to see the exact PDF page with your chunk highlighted."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    question = message.content.strip()
    mode     = cl.user_session.get("pipeline_mode", "hyde")
    if not question:
        return

    free_mode = (mode == "free")
    use_hyde  = (mode == "hyde")

    msg = cl.Message(content="🧠  Thinking...")
    await msg.send()

    chunks = []
    data   = None

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{API_URL}/query/stream",
                json={"question": question, "free_mode": free_mode, "use_hyde": use_hyde},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])
                    phase = event["phase"]

                    if phase == "retrieving":
                        if mode == "free":
                            msg.content = "🧠  Asking GPT-4o directly..."
                        elif mode == "hyde":
                            msg.content = "🔬  Generating hypothetical passage + searching 4 textbooks..."
                        else:
                            msg.content = "⚡  Searching 4 textbooks..."
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

    perf_footer     = build_perf_footer(
        t_ret, t_llm, t_tot, data["chunks"], data.get("pipeline", ""),
        t_hyde=data.get("latency_hyde_s", 0),
        t_embed=data.get("latency_embed_s", 0),
        t_search=data.get("latency_search_s", 0),
        t_rerank=data.get("latency_rerank_s", 0),
    )
    sources_content = build_sources_content(data["chunks"])

    elements = []
    if data["chunks"]:
        elements.append(cl.Text(
            name=f"📚 Sources  ·  {len(data['chunks'])} passages retrieved",
            content=sources_content,
            display="inline",
        ))

    # Store chunks + images in session
    cl.user_session.set("last_chunks", data["chunks"])
    cl.user_session.set("last_images", data.get("images", []))

    # ── Action buttons ────────────────────────────────────────────────────────
    seen_keys = set()
    actions   = []

    # One page-preview button per unique (collection, page)
    for chunk in data["chunks"]:
        collection = chunk.get("collection", "")
        page       = chunk.get("page")
        source     = chunk.get("source", "")
        content    = chunk.get("content", "")
        key        = f"{collection}:{page}"
        if collection and isinstance(page, int) and key not in seen_keys:
            seen_keys.add(key)
            actions.append(
                cl.Action(
                    name="view_page",
                    payload={
                        "collection": collection,
                        "page":       page,
                        "source":     source,
                        "content":    content[:200],
                    },
                    label=f"📄 {source}, p.{page}",
                )
            )

    # Show figures button — only if there are any extracted images
    if data.get("images"):
        actions.append(
            cl.Action(
                name="show_figures",
                payload={},
                label=f"🖼️ Show figures ({len(data['images'])})",
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
    """
    Gallery view: fetch pages for ALL retrieved chunks in one message.
    The clicked chunk shows ±1 pages with yellow highlight on the selected page.
    All other chunks show their single page unadorned.
    All fetches run concurrently.
    """
    clicked_col     = action.payload["collection"]
    clicked_page    = action.payload["page"]
    clicked_source  = action.payload.get("source", "")
    clicked_content = action.payload.get("content", "")

    all_chunks = cl.user_session.get("last_chunks", [])

    # Build the ordered fetch list — selected chunk first (with ±1), then rest
    to_fetch = []   # (collection, page_num, highlight_text, label)
    seen     = set()

    # Selected chunk: ±1 pages, highlight on the exact page
    for p in [clicked_page - 1, clicked_page, clicked_page + 1]:
        if p > 0:
            key = f"{clicked_col}:{p}"
            seen.add(key)
            if p == clicked_page:
                label = f"★ {clicked_source}, p.{p}"
                to_fetch.append((clicked_col, p, clicked_content, label))
            else:
                arrow = "◀" if p < clicked_page else "▶"
                label = f"{arrow} {clicked_source}, p.{p}"
                to_fetch.append((clicked_col, p, "", label))

    # All other chunks: single page each, no highlight
    for chunk in all_chunks:
        col     = chunk.get("collection", "")
        page    = chunk.get("page")
        source  = chunk.get("source", "")
        key     = f"{col}:{page}"
        if not col or not isinstance(page, int) or key in seen:
            continue
        seen.add(key)
        to_fetch.append((col, page, "", f"{source}, p.{page}"))

    # Fetch all pages concurrently
    async def fetch_one(col, page_n, highlight, label):
        try:
            params = {"highlight": highlight} if highlight else {}
            resp = await client.get(f"{API_URL}/page/{col}/{page_n}", params=params)
            if resp.status_code == 200:
                return cl.Image(content=resp.content, name=label, display="inline")
        except Exception:
            pass
        return None

    async with httpx.AsyncClient(timeout=60) as client:
        results  = await asyncio.gather(*[fetch_one(*args) for args in to_fetch])

    elements = [r for r in results if r is not None]

    if elements:
        await cl.Message(
            content=(
                f"**📄 All source pages** · opened from **{clicked_source}, p.{clicked_page}**\n\n"
                f"★ = selected page (highlighted in yellow)  ·  scroll to browse all sources"
            ),
            elements=elements,
        ).send()
    else:
        await cl.Message(content="⚠️ Could not load page previews.").send()


@cl.action_callback("show_figures")
async def on_show_figures(action: cl.Action):
    """Show extracted book figures/diagrams from the last answer on demand."""
    images = cl.user_session.get("last_images", [])
    if not images:
        await cl.Message(content="No figures found for this answer.").send()
        return

    elements = []
    for img in images[:6]:
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

    if elements:
        await cl.Message(
            content=f"**🖼️ Figures from textbooks** · {len(elements)} image(s)",
            elements=elements,
        ).send()
    else:
        await cl.Message(content="⚠️ Figure files not found on disk.").send()
