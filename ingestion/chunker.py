import os
import unicodedata

import tiktoken
from ingestion.loader import paragraph_features

enc = tiktoken.encoding_for_model("text-embedding-3-small")

SUB_HEADING_MAX_WORDS = 6
HEADING_PATH_SEP = " > "


def _heading_level(style: str) -> int:
    digits = "".join(ch for ch in style if ch.isdigit())
    return int(digits) if digits else 1


def _is_heading(p: dict) -> bool:
    return p["style"].startswith("Heading")


def _doc_name(source_file: str) -> str:
    # "word_files/.../4. BUỔI 4 VALUE LINE.docx" -> "4. BUỔI 4 VALUE LINE"
    stem = os.path.splitext(os.path.basename(source_file))[0]
    return " ".join(unicodedata.normalize("NFC", stem).split())


# def _is_sub_heading(p: dict) -> bool:

#     if p["style"] == "Table":
#         return False
#     text = p["text"]
#     if not text.endswith(":"):
#         return False
#     return len(text.split()) <= SUB_HEADING_MAX_WORDS


def chunk_paragraphs(source_file: str, max_tokens: int = 512) -> list[dict]:
    paragraphs = paragraph_features(source_file)

    sections = []
    current_title = None
    current_paras = []
    heading_stack = []
    doc_name = _doc_name(source_file)

    for i, p in enumerate(paragraphs):
        if _is_heading(p):
            level = _heading_level(p["style"])
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()

            nxt = paragraphs[i + 1] if i + 1 < len(paragraphs) else None
            is_empty = nxt is None or _is_heading(nxt)
            if is_empty and (nxt is None or _heading_level(nxt["style"]) <= level):
                # Empty heading with no child headings: it isn't a parent of anything,
                # so keep its text as a paragraph of the parent section.
                parent_title = HEADING_PATH_SEP.join([doc_name] + [text for _, text in heading_stack])
                if current_title != parent_title:
                    if current_title is not None:
                        sections.append({
                            "section_title": current_title,
                            "paragraphs": current_paras,
                        })
                    current_title = parent_title
                    current_paras = []
                current_paras.append(p)
                continue

            if current_title is not None:
                sections.append({
                    "section_title": current_title,
                    "paragraphs": current_paras,
                })

            heading_stack.append((level, p["text"]))

            current_title = HEADING_PATH_SEP.join([doc_name] + [text for _, text in heading_stack])
            current_paras = []

        else:
            current_paras.append(p)

    if current_title is not None:
        sections.append({
            "section_title": current_title,
            "paragraphs": current_paras,
        })

    chunks = []
    chunk_index = 0

    def flush(section_title: str, paras: list[str]) -> dict:

        nonlocal chunk_index
        chunk = {
            "source_file": source_file,
            "section_title": section_title,
            "chunk_index": chunk_index,
            "text": section_title + "\n\n" + "\n\n".join(paras),
        }
        chunk_index += 1
        return chunk

    for section in sections:
        current_chunk = []
        current_tokens = 0

        for p in section["paragraphs"]:
            para = p["text"]
            paragraph_tokens = len(enc.encode(para))

            size_break = current_chunk and current_tokens + paragraph_tokens > max_tokens
            # sub_heading_break = current_chunk and len(current_chunk) > 1 and _is_sub_heading(p)

            # if size_break or sub_heading_break:
            if size_break:
                chunks.append(flush(section["section_title"], current_chunk))
                current_chunk = []
                current_tokens = 0

            current_chunk.append(para)
            current_tokens += paragraph_tokens

        if current_chunk:
            chunks.append(flush(section["section_title"], current_chunk))

    return chunks



if __name__ == "__main__":
    chunks = chunk_paragraphs("word_files/heading_already_files/ONE STORY, MANY CUE CARDS.docx")
    print(f"{len(chunks)} chunks\n")
    for c in chunks:
        print(f"[{c['section_title']}] chunk_index={c['chunk_index']} tokens~{len(enc.encode(c['text']))}")
        print(f"   {c['text']}")
        print()
