"""
Book RAG Chat UI
Connects to the RAG backend API at localhost:8000

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

API_URL = "http://localhost:8000"

CATEGORY_LABELS = {
    "medical":      "🏥 Medical",
    "cs":           "💻 CS / Tech",
    "personal_dev": "📈 Personal Development",
}


def speed_label(total: float) -> str:
    if total < 3:
        return "🟢"
    elif total < 7:
        return "🟡"
    return "🔴"


def build_perf_footer(t_ret: float, t_llm: float, t_tot: float, pages: list) -> str:
    pages_str = "  ·  ".join(f"p.{p}" for p in pages)
    return (
        f"\n\n---\n"
        f"{speed_label(t_tot)} **{t_tot:.2f}s** total  ·  "
        f"📥 retrieval **{t_ret:.2f}s**  ·  "
        f"🤖 LLM **{t_llm:.2f}s**  ·  "
        f"📄 {pages_str}"
    )


def build_sources_content(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page = chunk["page"]
        content = chunk["content"].strip()
        quoted = content.replace("\n", "\n> ")
        parts.append(f"**[{i}] Page {page}**\n\n> {quoted}")
    return "\n\n---\n\n".join(parts)


@cl.set_chat_profiles
async def chat_profiles():
    try:
        resp = httpx.get(f"{API_URL}/books", timeout=5)
        books = resp.json()
    except Exception:
        books = [{
            "key": "fischer_surgery",
            "display_name": "Fischer's Mastery of Surgery",
            "description": "8th Edition — Vol 1 & 2. Comprehensive surgical reference.",
            "category": "medical",
            "icon": "🏥",
        }]

    profiles = []
    for book in books:
        category_label = CATEGORY_LABELS.get(book.get("category", ""), "📚 General")
        icon = book.get("icon", "📖")
        profiles.append(
            cl.ChatProfile(
                name=book["key"],
                markdown_description=(
                    f"**{icon} {book['display_name']}**  \n"
                    f"{book['description']}  \n"
                    f"*{category_label}*"
                ),
            )
        )
    return profiles


@cl.on_chat_start
async def on_chat_start():
    book_key = cl.user_session.get("chat_profile") or "fischer_surgery"
    cl.user_session.set("book_key", book_key)

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
        resp = httpx.get(f"{API_URL}/books", timeout=5)
        books_list = {b["key"]: b for b in resp.json()}
        book = books_list.get(book_key, {"display_name": book_key, "description": "", "icon": "📖"})
    except Exception:
        book = {"display_name": book_key, "description": "", "icon": "📖"}

    cl.user_session.set("pipeline", pipeline)

    await cl.Message(
        content=(
            f"## {book['icon']} {book['display_name']}\n"
            f"{book['description']}\n\n"
            f"**Pipeline:** `{pipeline}` · **Model:** `GPT-4o`\n\n"
            f"Ask anything. Answers are grounded in the book with page citations."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    question = message.content.strip()
    if not question:
        return

    book_key = cl.user_session.get("book_key", "fischer_surgery")

    # Single message that morphs through loading phases → final answer
    msg = cl.Message(content="🧠  Thinking...")
    await msg.send()

    chunks = []
    data = None

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{API_URL}/query/stream",
                json={"question": question, "book_key": book_key},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])
                    phase = event["phase"]

                    if phase == "retrieving":
                        msg.content = "📖  Searching through the book..."
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
    pages  = data["pages"]
    answer = data["answer"]

    perf_footer     = build_perf_footer(t_ret, t_llm, t_tot, pages)
    sources_content = build_sources_content(data["chunks"])

    elements = [
        cl.Text(
            name=f"📚 Knowledge source  ·  {len(data['chunks'])} passages retrieved",
            content=sources_content,
            display="inline",
        )
    ]

    for img in data.get("images", [])[:6]:
        img_path = img.get("path", "") if isinstance(img, dict) else img
        caption  = img.get("caption", "") if isinstance(img, dict) else ""
        if img_path and os.path.exists(img_path):
            # Extract page number from filename for a fallback label
            basename = os.path.basename(img_path)
            try:
                page_num = basename.split("page_")[1].split("_img_")[0]
                fallback = f"Page {page_num}"
            except IndexError:
                fallback = basename
            name = caption if caption else fallback
            elements.append(
                cl.Image(path=img_path, name=name, display="inline")
            )

    # Replace the loading message with the final answer
    await msg.remove()
    await cl.Message(
        content=answer + perf_footer,
        elements=elements,
    ).send()
