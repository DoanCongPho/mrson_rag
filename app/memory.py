import re

import tiktoken
from openinference.semconv.trace import SpanAttributes
from sqlalchemy.orm import Session

from app.llm import client
from app.tracing import tracer_provider
from config import settings
from db.models import Conversation, Message
from db.session import SessionLocal

tracer = tracer_provider.get_tracer(__name__)

enc = tiktoken.encoding_for_model("gpt-4o-mini")

# The answer's own "Nguồn tham khảo:" list and [N] markers point at the sources of *that*
# turn; replayed in a later prompt they would collide with the new [N] numbering.
_SOURCES_SECTION = re.compile(r"\n[^\n]*Nguồn tham khảo.*", re.IGNORECASE | re.DOTALL)
_CITATION = re.compile(r"\s?\[\d+\]")


def truncate_tokens(text: str, max_tokens: int) -> str:
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens]).rstrip() + " …"


def trim_assistant(text: str, max_tokens: int) -> str:
    text = _SOURCES_SECTION.sub("", text)
    text = _CITATION.sub("", text).strip()
    return truncate_tokens(text, max_tokens)


def load_history(db: Session, conversation_id: int, turns: int | None = None) -> list[Message]:
    """The last `turns` exchanges (user + assistant) of a chat, oldest first.

    Call before saving the new question, so it is not part of its own history.
    """
    turns = settings.history_turns if turns is None else turns
    if turns <= 0:
        return []
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(turns * 2)
        .all()
    )
    return list(reversed(rows))


def history_messages(history: list[Message], max_tokens: int | None = None) -> list[dict]:
    """Chat turns for the OpenAI messages list, with long answers trimmed."""
    max_tokens = settings.history_message_max_tokens if max_tokens is None else max_tokens
    out = []
    for m in history:
        if m.role == "assistant":
            out.append({"role": "assistant", "content": trim_assistant(m.content, max_tokens)})
        else:
            out.append({"role": "user", "content": truncate_tokens(m.content, max_tokens)})
    return out


def history_as_text(history: list[Message], max_tokens: int) -> str:
    """Compact transcript for the router, which only needs enough to resolve references."""
    lines = []
    for m in history:
        who = "Learner" if m.role == "user" else "Assistant"
        content = trim_assistant(m.content, max_tokens) if m.role == "assistant" else truncate_tokens(m.content, max_tokens)
        lines.append(f"{who}: {content}")
    return "\n".join(lines)


SUMMARY_SYSTEM_PROMPT = """You maintain a running summary of a tutoring chat between an IELTS learner and an assistant that teaches from a teacher's course materials.

Merge the EXISTING SUMMARY with the NEW MESSAGES into one updated summary, written in Vietnamese, at most {max_words} words, as short bullet points. Keep:
- what the learner is working on (mode, cue card / question / topic, their goal),
- techniques and concepts already explained (by name, e.g. VALUE LINE, ZOOM IN),
- the learner's own answers, examples and recurring mistakes,
- open questions or what the learner asked to do next.
Drop greetings, small talk and long explanations (keep only their key point). Do not invent anything. Output only the summary."""


def _messages_to_fold(db: Session, conversation: Conversation) -> list[Message]:
    """Messages that already left the history window but are not in the summary yet."""
    window = settings.history_turns * 2
    rows = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation.id,
            Message.id > (conversation.summary_until_message_id or 0),
        )
        .order_by(Message.id)
        .all()
    )
    return rows[:-window] if window > 0 else rows


def update_summary(conversation_id: int) -> None:
    """Fold messages that left the window into conversations.summary (runs as a background task).

    Waits until SUMMARY_BATCH_TURNS exchanges have left the window, so it costs one LLM
    call every few turns. The update only applies if nobody else advanced the summary
    meanwhile (no row lock is held during the LLM call).
    """
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            return
        to_fold = _messages_to_fold(db, conversation)
        if len(to_fold) < settings.summary_batch_turns * 2:
            return

        previous_until = conversation.summary_until_message_id
        transcript = history_as_text(to_fold, settings.history_message_max_tokens)
        with tracer.start_as_current_span("summarize") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            span.set_attribute(SpanAttributes.INPUT_VALUE, f"{len(to_fold)} messages")
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT.format(max_words=settings.summary_max_words)},
                        {"role": "user", "content": f"EXISTING SUMMARY:\n{conversation.summary or '(none)'}\n\nNEW MESSAGES:\n{transcript}"},
                    ],
                    temperature=0,
                )
            except Exception:
                span.set_attribute("summarize.failed", True)
                return  # retried on the next message
            summary = (response.choices[0].message.content or "").strip()
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, summary)
        if not summary:
            return

        updated = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.summary_until_message_id.is_(None)
                if previous_until is None
                else Conversation.summary_until_message_id == previous_until,
            )
            .update(
                {Conversation.summary: summary, Conversation.summary_until_message_id: to_fold[-1].id},
                synchronize_session=False,
            )
        )
        db.commit() if updated else db.rollback()
