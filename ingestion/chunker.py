import tiktoken
from ingestion.loader import paragraph_features

enc = tiktoken.encoding_for_model("text-embedding-3-small")

SUB_HEADING_MAX_WORDS = 6


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

    for p in paragraphs:
        if p["style"].startswith("Heading"):

            if current_title is not None:
                sections.append({
                    "section_title": current_title,
                    "paragraphs": current_paras,
                })

            current_title = p["text"]
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
