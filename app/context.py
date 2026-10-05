from dataclasses import dataclass

import tiktoken
from openinference.semconv.trace import SpanAttributes

from app.tracing import tracer_provider
from config import settings
from db.models import Chunk
from db.session import SessionLocal

tracer = tracer_provider.get_tracer(__name__)

enc = tiktoken.encoding_for_model("text-embedding-3-small")

HEADING_PATH_SEP = " > "


@dataclass
class ContextBlock:
    source_file: str
    section_title: str
    text: str
    chunk_ids: list[int]


def _parent_title(section_title: str) -> str | None:
    # "doc > H1 > H2" -> "doc > H1". Returns None when there is no parent heading
    # ("doc > H1", or old chunks without a path): the window then spans adjacent
    # chunks of the whole file, still capped by the token budget.
    parts = section_title.split(HEADING_PATH_SEP)
    if len(parts) <= 2:
        return None
    return HEADING_PATH_SEP.join(parts[:-1])


def _load_files(source_files: set[str]) -> dict[str, list[Chunk]]:
    # One query for every file the hits come from, instead of one query per hit.
    session = SessionLocal()
    try:
        rows = (
            session.query(Chunk)
            .filter(Chunk.source_file.in_(source_files), Chunk.is_active.is_(True))
            .order_by(Chunk.source_file, Chunk.chunk_index)
            .all()
        )
    finally:
        session.close()
    by_file: dict[str, list[Chunk]] = {}
    for c in rows:
        by_file.setdefault(c.source_file, []).append(c)
    return by_file


def _siblings(file_chunks: list[Chunk], hit: Chunk) -> list[Chunk]:
    parent = _parent_title(hit.section_title)
    if parent is None:
        return file_chunks
    prefix = parent + HEADING_PATH_SEP
    return [c for c in file_chunks if c.section_title == parent or c.section_title.startswith(prefix)]


def _window(siblings: list[Chunk], hit: Chunk, used: set[int], max_tokens: int) -> list[Chunk]:
    # Grow a contiguous window outward from the hit, alternating previous/next neighbor.
    # A direction stops at a chunk that is already used elsewhere or doesn't fit the budget.
    pos = next(i for i, c in enumerate(siblings) if c.id == hit.id)
    lo = hi = pos
    budget = max_tokens - len(enc.encode(hit.text))
    open_dirs = {-1, 1}
    while open_dirs:
        for step in sorted(open_dirs):
            idx = lo - 1 if step == -1 else hi + 1
            if not 0 <= idx < len(siblings) or siblings[idx].id in used:
                open_dirs.discard(step)
                continue
            cost = len(enc.encode(siblings[idx].text))
            if cost > budget:
                open_dirs.discard(step)
                continue
            budget -= cost
            if step == -1:
                lo = idx
            else:
                hi = idx
    return siblings[lo:hi + 1]


def expand(hits: list[Chunk]) -> list[ContextBlock]:
    """Small-to-big: turn each retrieved chunk into a block with its adjacent chunks (same parent section, or same file when the docs are flat).

    One block per hit, in hit order, so citation [N] still matches source N. A chunk that
    already appears in an earlier block is not repeated (the hit itself is always kept).
    """
    with tracer.start_as_current_span("expand_context") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        span.set_attribute(SpanAttributes.INPUT_VALUE, f"{len(hits)} chunks")

        by_file = _load_files({hit.source_file for hit in hits})
        used = {hit.id for hit in hits}
        blocks = []
        for hit in hits:
            siblings = _siblings(by_file.get(hit.source_file, []), hit)
            window = _window(siblings, hit, used, settings.context_block_max_tokens)
            used.update(c.id for c in window)
            blocks.append(ContextBlock(
                source_file=hit.source_file,
                section_title=hit.section_title,
                text="\n\n".join(c.text for c in window),
                chunk_ids=[c.id for c in window],
            ))

        added = sum(len(b.chunk_ids) for b in blocks) - len(hits)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(blocks)} blocks, {added} neighbor chunks added")
        return blocks


def to_context(hits: list[Chunk]) -> list[ContextBlock]:
    if settings.context_expand_enabled:
        return expand(hits)
    return [ContextBlock(c.source_file, c.section_title, c.text, [c.id]) for c in hits]
