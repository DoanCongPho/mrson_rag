import tiktoken
from ingestion.loader import paragraph_features

enc = tiktoken.encoding_for_model("text-embedding-3-small")


def chunk_paragraphs(source_file: str, max_tokens: int = 400) -> list[dict]:
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
            current_paras.append(p["text"])

    if current_title is not None:
        sections.append({
            "section_title": current_title,
            "paragraphs": current_paras,
        })

    chunks = []
    chunk_index = 0

    for section in sections:
        current_chunk = []
        current_tokens = 0

        for para in section["paragraphs"]:
            paragraph_tokens = len(enc.encode(para))

            if current_chunk and current_tokens + paragraph_tokens > max_tokens:
                chunks.append({
                    "source_file": source_file,
                    "section_title": section["section_title"],
                    "chunk_index": chunk_index,
                    "text": "\n\n".join(current_chunk),
                })

                chunk_index += 1
                current_chunk = []
                current_tokens = 0

            current_chunk.append(para)
            current_tokens += paragraph_tokens

        if current_chunk:
            chunks.append({
                "source_file": source_file,
                "section_title": section["section_title"],
                "chunk_index": chunk_index,
                "text": "\n\n".join(current_chunk),
            })
            chunk_index += 1

    return chunks



if __name__ == "__main__":
    chunks = chunk_paragraphs("word_files/heading_already_files/ONE STORY, MANY CUE CARDS.docx")
    print(f"{len(chunks)} chunks\n")
    for c in chunks:
        print(f"[{c['section_title']}] chunk_index={c['chunk_index']} tokens~{len(enc.encode(c['text']))}")
        print(f"   {c['text']}")
        print()
