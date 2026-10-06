import re

import tiktoken
from sqlalchemy.orm import Session

from config import settings
from db.models import Message

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
