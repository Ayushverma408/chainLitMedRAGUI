"""
Fischer's Mastery of Surgery — Chat UI
Connects to the RAG backend API at localhost:8000

Run backend first:
    cd ../advanced-rag-poc
    venv/bin/uvicorn src.api:app --port 8000

Then run this:
    cd ../surgery-rag-ui
    chainlit run app.py
"""

import httpx
import chainlit as cl

API_URL = "http://localhost:8000"


def format_latency_bar(total: float) -> str:
    """Visual bar showing how fast the response was."""
    if total < 3:
        bar = "🟢 Fast"
    elif total < 7:
        bar = "🟡 Moderate"
    else:
        bar = "🔴 Slow"
    return bar


@cl.on_chat_start
async def on_chat_start():
    # Check backend is alive
    try:
        resp = httpx.get(f"{API_URL}/health", timeout=5)
        info = resp.json()
        pipeline = info.get("pipeline", "unknown")
    except Exception:
        await cl.Message(
            content="⚠️ **Backend not running.** Start it with:\n```\ncd advanced-rag-poc\nvenv/bin/uvicorn src.api:app --port 8000\n```"
        ).send()
        return

    cl.user_session.set("history", [])

    await cl.Message(
        content=(
            f"## Fischer's Mastery of Surgery\n"
            f"**AI Reference Assistant** · Pipeline: `{pipeline}` · Model: `GPT-4o`\n\n"
            f"Ask any surgical question. Each answer shows:\n"
            f"- 📄 Retrieved source chunks with page numbers (click to expand)\n"
            f"- ⏱ Retrieval + generation latency\n"
            f"- 🔍 Exact text from the book that grounded the answer"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    question = message.content.strip()
    if not question:
        return

    # Show spinner while waiting
    async with cl.Step(name="Searching Fischer's Surgery...", show_input=False) as step:
        try:
            resp = httpx.post(
                f"{API_URL}/query",
                json={"question": question},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            step.output = "Request timed out"
            await cl.Message(content="⚠️ Request timed out. Try a shorter question.").send()
            return
        except Exception as e:
            step.output = str(e)
            await cl.Message(content=f"⚠️ Error: {e}").send()
            return

        t_ret = data["latency_retrieval_s"]
        t_llm = data["latency_llm_s"]
        t_tot = data["latency_total_s"]
        step.output = (
            f"Retrieved {len(data['chunks'])} chunks in {t_ret:.2f}s · "
            f"Generated in {t_llm:.2f}s"
        )

    # Build source elements — one expandable card per chunk
    source_elements = []
    for chunk in data["chunks"]:
        page = chunk["page"]
        content = chunk["content"]
        source_elements.append(
            cl.Text(
                name=f"📄 Page {page}",
                content=(
                    f"**Fischer's Mastery of Surgery, 8th Ed — Page {page}**\n\n"
                    f"{content}"
                ),
                display="side",
            )
        )

    # Pages footer
    pages_str = "  ·  ".join(f"p.{p}" for p in data["pages"])
    speed = format_latency_bar(t_tot)

    footer = (
        f"\n\n---\n"
        f"{speed} · ⏱ `{t_tot:.2f}s` total "
        f"(retrieval `{t_ret:.2f}s` + LLM `{t_llm:.2f}s`)\n"
        f"📚 Sources: {pages_str}"
    )

    await cl.Message(
        content=data["answer"] + footer,
        elements=source_elements,
    ).send()
