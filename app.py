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


def speed_label(total: float) -> str:
    if total < 3:
        return "🟢"
    elif total < 7:
        return "🟡"
    return "🔴"


def build_sources_block(chunks: list[dict]) -> str:
    """
    Render retrieved chunks as a markdown block embedded directly in the message.
    Each chunk is shown with its page number and the exact text from the book.
    In Chainlit 2.x this is the most reliable way to show expandable source content.
    """
    lines = ["\n\n---\n### 📚 Retrieved Sources\n"]
    for i, chunk in enumerate(chunks, 1):
        page = chunk["page"]
        content = chunk["content"].strip()
        lines.append(f"**[{i}] Page {page}**")
        lines.append(f"> {content.replace(chr(10), chr(10) + '> ')}")
        lines.append("")
    return "\n".join(lines)


@cl.on_chat_start
async def on_chat_start():
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

    cl.user_session.set("pipeline", pipeline)

    await cl.Message(
        content=(
            f"## Fischer's Mastery of Surgery — RAG Assistant\n"
            f"**Pipeline:** `{pipeline}` · **Model:** `GPT-4o`\n\n"
            f"Ask any surgical question. Each answer shows the answer, "
            f"exact source chunks from the book with page numbers, and latency."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    question = message.content.strip()
    if not question:
        return

    async with cl.Step(name="Retrieving & generating...", show_input=False) as step:
        try:
            resp = httpx.post(
                f"{API_URL}/query",
                json={"question": question},
                timeout=90,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            step.output = "Timed out"
            await cl.Message(content="⚠️ Request timed out.").send()
            return
        except Exception as e:
            step.output = str(e)
            await cl.Message(content=f"⚠️ Error: {e}").send()
            return

        t_ret = data["latency_retrieval_s"]
        t_llm = data["latency_llm_s"]
        t_tot = data["latency_total_s"]
        step.output = (
            f"{len(data['chunks'])} chunks retrieved in {t_ret:.2f}s · "
            f"LLM answered in {t_llm:.2f}s"
        )

    pages_str = "  ·  ".join(f"p.{p}" for p in data["pages"])

    perf_line = (
        f"\n\n---\n"
        f"{speed_label(t_tot)} `{t_tot:.2f}s` total "
        f"· retrieval `{t_ret:.2f}s` · LLM `{t_llm:.2f}s`  \n"
        f"📄 Pages referenced: **{pages_str}**"
    )

    sources_block = build_sources_block(data["chunks"])

    await cl.Message(
        content=data["answer"] + perf_line + sources_block
    ).send()
